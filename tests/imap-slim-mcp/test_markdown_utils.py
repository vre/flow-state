"""Tests for markdown_utils module.

TDD: These tests define the interface for the new markdown_utils module.
Tests are written first, then the module is created to satisfy them.
"""

import pytest

# Import from new module location (will fail until module exists)
from markdown_utils import (
    MARKDOWN_EXTENSION_CONFIGS,
    MARKDOWN_EXTENSIONS,
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

    def test_consecutive_quote_lines_split_known_limitation(self):
        """Pinned so cut 1b changes it deliberately.

        preprocess_markdown inserts a blank line between consecutive '>' lines, so
        nl2br cannot make a quoted line break. Two paragraphs, one blockquote.
        """
        html, _ = convert_body("> first\n> second", "markdown")
        assert html.count("<blockquote>") == 1
        assert html.count("<p>") == 2


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
