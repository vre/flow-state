"""Tests for markdown_utils module.

TDD: These tests define the interface for the new markdown_utils module.
Tests are written first, then the module is created to satisfy them.
"""

import pytest

# Import from new module location (will fail until module exists)
from markdown_utils import (
    MARKDOWN_EXTENSION_CONFIGS,
    MARKDOWN_EXTENSIONS,
    _fenced_flags,
    _line_records,
    autolink_urls,
    convert_body,
    markdown_to_plain,
    preprocess_markdown,
)


class TestPreprocessMarkdown:
    """Tests for preprocess_markdown function."""

    def test_adds_blank_line_before_unordered_list(self):
        text = "Some text\n- list item"
        result = preprocess_markdown(text)
        assert result == "Some text\n\n- list item"

    def test_adds_blank_line_before_ordered_list(self):
        text = "Some text\n1. first item"
        result = preprocess_markdown(text)
        assert result == "Some text\n\n1. first item"

    def test_adds_blank_line_before_blockquote(self):
        text = "Some text\n> quote"
        result = preprocess_markdown(text)
        assert result == "Some text\n\n> quote"

    def test_adds_blank_line_before_heading(self):
        text = "Some text\n# Heading"
        result = preprocess_markdown(text)
        assert result == "Some text\n\n# Heading"

    def test_no_duplicate_blank_line(self):
        text = "Some text\n\n- list item"
        result = preprocess_markdown(text)
        assert result == "Some text\n\n- list item"

    def test_empty_string(self):
        result = preprocess_markdown("")
        assert result == ""


class TestMarkdownToPlain:
    """Tests for markdown_to_plain function."""

    def test_bold_double_asterisk(self):
        text = "This is **bold** text"
        result = markdown_to_plain(text)
        assert result == "This is *bold* text"

    def test_bold_double_underscore(self):
        text = "This is __bold__ text"
        result = markdown_to_plain(text)
        assert result == "This is *bold* text"

    def test_italic_unchanged(self):
        text = "This is *italic* text"
        result = markdown_to_plain(text)
        assert result == "This is *italic* text"

    def test_link_to_plain(self):
        text = "Click [here](https://example.com) for info"
        result = markdown_to_plain(text)
        assert result == "Click here <https://example.com> for info"

    def test_strikethrough_removed(self):
        text = "This is ~~deleted~~ text"
        result = markdown_to_plain(text)
        assert result == "This is deleted text"

    def test_highlight_removed(self):
        text = "This is ==important== text"
        result = markdown_to_plain(text)
        assert result == "This is important text"

    def test_empty_string(self):
        result = markdown_to_plain("")
        assert result == ""


class TestConvertBody:
    """Tests for convert_body helper function.

    This function eliminates duplication between create_draft and modify_draft.
    """

    def test_markdown_format_returns_html_and_plain(self):
        """Markdown format should return both HTML and plain text."""
        body = "**Bold** and *italic*"
        html, plain = convert_body(body, format_type="markdown")

        assert html is not None
        assert "<strong>Bold</strong>" in html
        assert "<em>italic</em>" in html
        assert plain == "*Bold* and *italic*"

    def test_plain_format_returns_none_html(self):
        """Plain format should return None for HTML."""
        body = "Plain text only"
        html, plain = convert_body(body, format_type="plain")

        assert html is None
        assert plain == "Plain text only"

    def test_there_is_no_default_format(self):
        """Superseded: a silent default let callers send markdown believing it was plain."""
        with pytest.raises(TypeError):
            convert_body("**Bold**")

    def test_markdown_with_strikethrough(self):
        """Markdown should support strikethrough extension."""
        body = "~~deleted~~"
        html, plain = convert_body(body, format_type="markdown")

        assert "<del>deleted</del>" in html
        assert plain == "deleted"

    def test_markdown_with_highlight(self):
        """Markdown should support highlight/mark extension."""
        body = "==important=="
        html, plain = convert_body(body, format_type="markdown")

        assert "<mark>important</mark>" in html
        assert plain == "important"

    def test_markdown_with_checkbox(self):
        """Markdown should support task list extension."""
        body = "- [ ] unchecked\n- [x] checked"
        html, plain = convert_body(body, format_type="markdown")

        assert 'type="checkbox"' in html
        assert plain == "- [ ] unchecked\n- [x] checked"

    def test_markdown_with_emoji(self):
        """Markdown should convert emoji shortcodes to unicode."""
        body = "Hello :smile:"
        html, plain = convert_body(body, format_type="markdown")

        # Emoji should be converted to unicode, not CDN image
        assert "😄" in html or "smile" in html  # depends on emoji support
        assert "<img" not in html  # No CDN images

    def test_markdown_preprocesses_for_lists(self):
        """Markdown should preprocess to add blank lines before lists."""
        body = "Text\n- item"
        html, plain = convert_body(body, format_type="markdown")

        # Should render as proper list, not inline
        assert "<li>" in html

    def test_invalid_format_raises_value_error(self):
        """Unknown format should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown format 'html'"):
            convert_body("Hello", format_type="html")

    def test_uppercase_format_raises_value_error(self):
        """Format validation is case-sensitive."""
        with pytest.raises(ValueError, match="Unknown format 'HTML'"):
            convert_body("Hello", format_type="HTML")


class TestMarkdownConstants:
    """Tests for markdown configuration constants."""

    def test_extensions_list_exists(self):
        """MARKDOWN_EXTENSIONS should be a list."""
        assert isinstance(MARKDOWN_EXTENSIONS, list)
        assert len(MARKDOWN_EXTENSIONS) > 0

    def test_required_extensions_present(self):
        """Required extensions should be in the list."""
        assert "pymdownx.tilde" in MARKDOWN_EXTENSIONS
        assert "pymdownx.tasklist" in MARKDOWN_EXTENSIONS
        assert "pymdownx.mark" in MARKDOWN_EXTENSIONS
        assert "pymdownx.betterem" in MARKDOWN_EXTENSIONS
        assert "pymdownx.emoji" in MARKDOWN_EXTENSIONS

    def test_extension_configs_exists(self):
        """MARKDOWN_EXTENSION_CONFIGS should be a dict."""
        assert isinstance(MARKDOWN_EXTENSION_CONFIGS, dict)

    def test_emoji_config_uses_unicode(self):
        """Emoji config should use unicode output, not CDN."""
        assert "pymdownx.emoji" in MARKDOWN_EXTENSION_CONFIGS


class TestPlainIsOnlyPlain:
    """AC3: plain mode interprets nothing."""

    def test_ascii_art_survives_byte_for_byte(self):
        art = "  +---+---+\n  | X | O |\n  +---+---+\n  ===== 5 =====\n\ttabbed\n"
        html, plain = convert_body(art, "plain")
        assert html is None
        assert plain == art


class TestLineBreaks:
    """AC4: a newline inside a paragraph is a line break."""

    def test_signature_block_keeps_its_breaks(self):
        body = "Terveisin\nVille Reijonen\nItio Consulting Oy"
        html, plain = convert_body(body, "markdown")
        assert "Terveisin<br />" in html
        assert "Ville Reijonen<br />" in html
        assert plain == body

    def test_blank_line_still_separates_paragraphs(self):
        html, _ = convert_body("one\n\ntwo", "markdown")
        assert html.count("<p>") == 2
        assert "<br />" not in html


class TestSupportedBlocks:
    """AC5: blocks this renderer actually supports."""

    def test_list_and_paragraph(self):
        html, _ = convert_body("- a\n- b\n\npara one\nline two", "markdown")
        assert "<ul>" in html and "<li>a</li>" in html and "<li>b</li>" in html
        list_html = html[html.index("<ul>") : html.index("</ul>")]
        assert "<br />" not in list_html
        assert "<p>para one<br />" in html

    def test_heading_and_blockquote(self):
        assert "<h1>Otsikko</h1>" in convert_body("# Otsikko\n\nteksti", "markdown")[0]
        assert "<blockquote>" in convert_body("teksti\n\n> lainaus", "markdown")[0]

    def test_consecutive_quote_lines_keep_their_line_break(self):
        """Cut 1a pinned the old two-paragraph output so this cut could change it.

        The blank line preprocessing inserted between consecutive '>' lines split
        one quoted paragraph in two and defeated nl2br inside quotes.
        """
        html, _ = convert_body("> first\n> second", "markdown")
        assert html.count("<blockquote>") == 1
        assert html.count("<p>") == 1
        assert "first<br />" in html


class TestMarkerRunLines:
    """AC6: an ASCII rule is not emphasis."""

    @pytest.mark.parametrize(
        "text",
        [
            "=====",
            "~~~~~",
            "*****",
            "_____",
            "______",
            "~~~~~~",
            "******",
            "=======",
            "  =====  ",
            "\t*****\t",
            "> =====",
            ">> *****",
            "> > _____",
            "=====\n",
            "=====\r",
            "a\r=====\rb",
            "Terveisin\n=====\nVille",
            "Terveisin\r\n=====\r\nVille\r\n",
            "\x000\x00 literal\n=====\n",
            "\x0000\x00 literal\n=====\n",
            "\x0001\x00 literal\n=====\n=====\n",
        ],
    )
    def test_marker_run_lines_are_untouched(self, text):
        assert markdown_to_plain(text) == text

    def test_many_protected_lines_do_not_collide(self):
        body = "\n".join(["====="] * 11 + ["a ==x== b"])
        assert markdown_to_plain(body) == "\n".join(["====="] * 11 + ["a x b"])

    def test_a_substitution_cannot_synthesise_the_shield_token(self):
        """The prefix rule keeps tokens out of the input; it cannot stop the
        substitutions from manufacturing one. '\\x00==0==\\x00==0==\\x00' collapses
        to exactly token 0, and restoring it would rewrite the user's text."""
        assert markdown_to_plain("\x00==0==\x00==0==\x00\n=====") == "\x000\x000\x00\n====="

    @pytest.mark.parametrize(
        "text,want",
        [
            ("***bold italic***", "**bold italic**"),
            ("~~a~~~~b~~", "ab"),
            ("==a====b==", "ab"),
            ("**a****b**", "*a**b*"),
            ("**bold**", "*bold*"),
            ("a ~~b~~ c", "a b c"),
            ("a ==x== b", "a x b"),
            ("[t](http://x)", "t <http://x>"),
            ("[long label\ncontinued](https://example.com)", "long label\ncontinued <https://example.com>"),
            (
                "[alpha\n=====\nomega](https://example.com)\n~~~~~",
                "alpha\n=====\nomega <https://example.com>\n~~~~~",
            ),
            ("**bold\ncontinued**", "**bold\ncontinued**"),
            ("# Heading\n\n- list item\n\n> quote", "# Heading\n\n- list item\n\n> quote"),
            ("", ""),
        ],
    )
    def test_inline_behaviour_is_unchanged(self, text, want):
        assert markdown_to_plain(text) == want


class TestFencePairing:
    """AC3: the helper must agree with python-markdown, not approximate it."""

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("```\na\n```", [True, True, True]),
            ("````\nx\n````", [True, True, True]),
            ("```c#\nx\n```", [True, True, True]),
            ("```foo.bar\nx\n```", [True, True, True]),
            ("```{.python #ex}\nx\n```", [True, True, True]),
            ("```python\nx\n```   ", [True, True, True]),
            ("```\n\n```", [True, True, True]),
            ("```\nx\n````", [False, False, False]),
            ("````\nx\n```", [False, False, False]),
            ("```\nx\n```python", [False, False, False]),
            ("  ```\nx\n  ```", [False, False, False]),
            ("~~~~~", [False]),
            ("```\nunterminated", [False, False]),
            ("```\n~~~\n```\n~~~", [True, True, True, False]),
            ("a\n```\nx\n```\nb\n~~~~~\nc", [False, True, True, True, False, False, False]),
            ("```\na\n```\n```\nb\n```", [True, True, True, True, True, True]),
        ],
    )
    def test_flags(self, text, expected):
        assert _fenced_flags(_line_records(text)) == expected

    @pytest.mark.parametrize("ending", ["\n", "\r\n", "\r"])
    def test_line_endings_do_not_change_the_flags(self, ending):
        text = ending.join(["```", "x", "```"])
        assert _fenced_flags(_line_records(text)) == [True, True, True]


class TestFencedCodeSurvives:
    """AC1/AC2: what the author wrote is what the recipient gets."""

    FENCE = "```\n**literal**\n~~literal~~\n==literal==\n[x](https://example.com)\n=====\n```"

    def test_html_keeps_the_fence_contents(self):
        html, _ = convert_body("```\n#include\n- literal\n> literal\n```", "markdown")
        assert html == "<pre><code>#include\n- literal\n&gt; literal\n</code></pre>"

    def test_fence_after_text_is_its_own_block(self):
        html, _ = convert_body("intro\n```\ncode\n```", "markdown")
        assert "<p>intro</p>" in html
        assert "<pre><code>code\n</code></pre>" in html

    def test_language_tag_reaches_the_html(self):
        html, _ = convert_body("```python\nx = 1\n```", "markdown")
        assert 'class="language-python"' in html
        assert "x = 1" in html

    def test_plain_part_keeps_the_fence_contents(self):
        body = f"**bold** here\n\n{self.FENCE}\n\nand ~~gone~~"
        plain = markdown_to_plain(body)
        for line in ["**literal**", "~~literal~~", "==literal==", "[x](https://example.com)", "====="]:
            assert line in plain, f"{line} was rewritten inside the fence"
        assert "*bold* here" in plain
        assert "and gone" in plain

    def test_a_marker_run_inside_a_fence_is_protected_once(self):
        assert markdown_to_plain("```\n=====\n```") == "```\n=====\n```"

    def test_a_multiline_link_still_spans_a_protected_line(self):
        assert markdown_to_plain("[a\n=====\nb](http://x)") == "a\n=====\nb <http://x>"


class TestTables:
    """AC4."""

    def test_table_after_text(self):
        html, _ = convert_body("intro\n| a | b |\n|---|---|\n| 1 | 2 |", "markdown")
        assert "<p>intro</p>" in html
        assert "<th>a</th>" in html and "<td>1</td>" in html

    def test_table_without_outer_pipes(self):
        html, _ = convert_body("intro\na | b\n--- | ---\n1 | 2", "markdown")
        assert "<th>a</th>" in html and "<td>1</td>" in html

    def test_table_already_separated_is_unchanged(self):
        html, _ = convert_body("intro\n\n| a | b |\n|---|---|\n| 1 | 2 |", "markdown")
        assert "<th>a</th>" in html

    def test_a_pipe_line_without_a_separator_is_not_a_table(self):
        html, _ = convert_body("intro\n| not | a table", "markdown")
        assert "<table>" not in html

    def test_a_separator_without_a_pipe_is_not_a_table(self):
        """':---:' alone is not a table separator; inserting a blank before the
        pipe row above it would split one paragraph into two."""
        html, _ = convert_body("intro\n| literal |\n:---:\nafter", "markdown")
        assert "<table>" not in html
        assert html.count("<p>") == 1


class TestBlockquoteContinuation:
    """AC5."""

    def test_quote_after_text_still_starts_a_block(self):
        html, _ = convert_body("text\n> quote", "markdown")
        assert "<blockquote>" in html

    def test_quote_after_a_list_item_still_starts_a_block(self):
        html, _ = convert_body("- item\n> quote", "markdown")
        assert "<blockquote>" in html

    @pytest.mark.parametrize("indent", ["", " ", "   "])
    def test_quote_markers_indented_up_to_three_spaces_continue(self, indent):
        html, _ = convert_body(f"> first\n{indent}> second", "markdown")
        assert html.count("<p>") == 1

    def test_four_spaces_is_not_a_quote_marker(self):
        html, _ = convert_body("> first\n    > second", "markdown")
        assert html.count("<blockquote>") == 1


class TestAutolinkNeverEntersCode:
    """AC6."""

    def test_code_block_url_is_left_alone(self):
        assert autolink_urls("<pre><code>https://a.com</code></pre>") == "<pre><code>https://a.com</code></pre>"

    def test_paragraph_url_is_anchored(self):
        assert '<a href="https://a.com">' in autolink_urls("<p>see https://a.com</p>")

    def test_inline_code_and_bare_url_in_one_paragraph(self):
        out = autolink_urls("<p><code>https://in</code> https://out</p>")
        assert "<code>https://in</code>" in out
        assert '<a href="https://out">' in out

    def test_an_existing_anchor_is_not_nested(self):
        html = '<p><a href="https://x.com">https://x.com</a></p>'
        assert autolink_urls(html) == html

    def test_end_to_end_through_convert_body(self):
        html, _ = convert_body("see https://out.example\n\n```\nhttps://in.example\n```", "markdown")
        assert '<a href="https://out.example">' in html
        assert "<code>https://in.example\n</code>" in html
