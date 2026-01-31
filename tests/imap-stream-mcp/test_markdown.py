"""Tests for markdown processing functions."""

from markdown_utils import markdown_to_plain, preprocess_markdown


class TestPreprocessMarkdown:
    """Tests for preprocess_markdown function."""

    def test_adds_blank_line_before_unordered_list(self):
        """Test blank line is added before unordered list."""
        text = "Some text\n- list item"
        result = preprocess_markdown(text)
        assert result == "Some text\n\n- list item"

    def test_adds_blank_line_before_ordered_list(self):
        """Test blank line is added before ordered list."""
        text = "Some text\n1. first item"
        result = preprocess_markdown(text)
        assert result == "Some text\n\n1. first item"

    def test_adds_blank_line_before_blockquote(self):
        """Test blank line is added before blockquote."""
        text = "Some text\n> quote"
        result = preprocess_markdown(text)
        assert result == "Some text\n\n> quote"

    def test_adds_blank_line_before_heading(self):
        """Test blank line is added before heading."""
        text = "Some text\n# Heading"
        result = preprocess_markdown(text)
        assert result == "Some text\n\n# Heading"

    def test_adds_blank_line_before_code_block(self):
        """Test blank line is added before code block (opening and closing)."""
        text = "Some text\n```python\ncode\n```"
        result = preprocess_markdown(text)
        # Note: closing ``` also treated as block start
        assert result == "Some text\n\n```python\ncode\n\n```"

    def test_no_duplicate_blank_line_if_already_exists(self):
        """Test no extra blank line if one already exists."""
        text = "Some text\n\n- list item"
        result = preprocess_markdown(text)
        assert result == "Some text\n\n- list item"

    def test_handles_multiple_block_elements(self):
        """Test multiple block elements get blank lines."""
        text = "Text\n- item\nMore text\n1. numbered"
        result = preprocess_markdown(text)
        assert result == "Text\n\n- item\nMore text\n\n1. numbered"

    def test_handles_asterisk_list(self):
        """Test asterisk-style unordered list."""
        text = "Some text\n* list item"
        result = preprocess_markdown(text)
        assert result == "Some text\n\n* list item"

    def test_handles_plus_list(self):
        """Test plus-style unordered list."""
        text = "Some text\n+ list item"
        result = preprocess_markdown(text)
        assert result == "Some text\n\n+ list item"

    def test_preserves_existing_formatting(self):
        """Test existing blank lines are preserved."""
        text = "Para 1\n\nPara 2\n\n- list"
        result = preprocess_markdown(text)
        assert result == "Para 1\n\nPara 2\n\n- list"

    def test_empty_string(self):
        """Test empty input."""
        result = preprocess_markdown("")
        assert result == ""

    def test_only_block_element(self):
        """Test input starting with block element."""
        text = "- just a list item"
        result = preprocess_markdown(text)
        assert result == "- just a list item"

    def test_nested_list_items(self):
        """Test nested list items do NOT get blank lines between them.

        Implementation tracks prev_was_list_item to avoid adding blank
        lines between consecutive list items (including nested ones).
        """
        text = "- item\n  - nested"
        result = preprocess_markdown(text)
        # No blank line between list items
        assert result == "- item\n  - nested"


class TestMarkdownToPlain:
    """Tests for markdown_to_plain function."""

    def test_bold_double_asterisk(self):
        """Test **bold** -> *bold*."""
        text = "This is **bold** text"
        result = markdown_to_plain(text)
        assert result == "This is *bold* text"

    def test_bold_double_underscore(self):
        """Test __bold__ -> *bold*."""
        text = "This is __bold__ text"
        result = markdown_to_plain(text)
        assert result == "This is *bold* text"

    def test_italic_unchanged(self):
        """Test *italic* stays *italic*."""
        text = "This is *italic* text"
        result = markdown_to_plain(text)
        assert result == "This is *italic* text"

    def test_link_to_plain(self):
        """Test [text](url) -> text <url>."""
        text = "Click [here](https://example.com) for info"
        result = markdown_to_plain(text)
        assert result == "Click here <https://example.com> for info"

    def test_strikethrough_removed(self):
        """Test ~~strike~~ -> strike."""
        text = "This is ~~deleted~~ text"
        result = markdown_to_plain(text)
        assert result == "This is deleted text"

    def test_highlight_removed(self):
        """Test ==highlight== -> highlight."""
        text = "This is ==important== text"
        result = markdown_to_plain(text)
        assert result == "This is important text"

    def test_multiple_formatting(self):
        """Test multiple formatting in same text."""
        text = "**Bold** and *italic* and ~~strike~~ and ==highlight=="
        result = markdown_to_plain(text)
        assert result == "*Bold* and *italic* and strike and highlight"

    def test_link_with_special_chars(self):
        """Test link with special characters in URL."""
        text = "[Search](https://google.com/search?q=test&page=1)"
        result = markdown_to_plain(text)
        assert result == "Search <https://google.com/search?q=test&page=1>"

    def test_multiple_links(self):
        """Test multiple links in text."""
        text = "[One](http://one.com) and [Two](http://two.com)"
        result = markdown_to_plain(text)
        assert result == "One <http://one.com> and Two <http://two.com>"

    def test_empty_string(self):
        """Test empty input."""
        result = markdown_to_plain("")
        assert result == ""

    def test_no_formatting(self):
        """Test text without formatting passes through."""
        text = "Plain text without any formatting"
        result = markdown_to_plain(text)
        assert result == "Plain text without any formatting"

    def test_bold_italic_combined(self):
        """Test ***bold italic*** handling."""
        # ***text*** becomes **text** after first pass, then *text*
        # Actually: ***text*** -> *text* (inner ** removed first)
        text = "This is ***bold italic*** text"
        result = markdown_to_plain(text)
        # **(.+?)** matches the inner part: *bold italic*
        # Result: *bold italic* -> unchanged since it's single asterisk
        assert result == "This is **bold italic** text"

    def test_preserves_other_content(self):
        """Test headings, lists, etc. are preserved."""
        text = "# Heading\n\n- list item\n\n> quote"
        result = markdown_to_plain(text)
        assert result == "# Heading\n\n- list item\n\n> quote"

    def test_checkboxes_preserved(self):
        """Test checkbox syntax is preserved."""
        text = "- [ ] unchecked\n- [x] checked"
        result = markdown_to_plain(text)
        assert result == "- [ ] unchecked\n- [x] checked"
