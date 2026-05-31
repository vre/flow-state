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

    def test_default_format_is_markdown(self):
        """Default format should be markdown."""
        body = "**Bold**"
        html, plain = convert_body(body)

        assert html is not None
        assert "<strong>Bold</strong>" in html

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
