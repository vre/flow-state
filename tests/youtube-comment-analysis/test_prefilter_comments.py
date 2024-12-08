"""Tests for prefilter_comments.py."""

import pytest
from prefilter_comments import (
    parse_comments,
    filter_comments,
    format_comments,
    MAX_COMMENTS,
)


class TestParseComments:
    """Tests for parse_comments function."""

    def test_parse_single_comment(self):
        """Test parsing a single comment."""
        content = "### 1. @user1 (42 likes)\n\nThis is a comment\n"
        result = parse_comments(content)

        assert len(result) == 1
        assert result[0]['author'] == 'user1'
        assert result[0]['likes'] == 42
        assert result[0]['text'] == 'This is a comment'

    def test_parse_multiple_comments(self):
        """Test parsing multiple comments."""
        content = (
            "### 1. @user1 (100 likes)\n\nFirst comment\n"
            "### 2. @user2 (50 likes)\n\nSecond comment\n"
            "### 3. @user3 (25 likes)\n\nThird comment\n"
        )
        result = parse_comments(content)

        assert len(result) == 3
        assert result[0]['author'] == 'user1'
        assert result[1]['author'] == 'user2'
        assert result[2]['author'] == 'user3'

    def test_parse_comment_with_singular_like(self):
        """Test parsing comment with '1 like' (singular)."""
        content = "### 1. @user1 (1 like)\n\nSingle like comment\n"
        result = parse_comments(content)

        assert len(result) == 1
        assert result[0]['likes'] == 1

    def test_parse_multiline_comment(self):
        """Test parsing comment with multiple lines."""
        content = "### 1. @user1 (10 likes)\n\nLine one\nLine two\nLine three\n"
        result = parse_comments(content)

        assert len(result) == 1
        assert "Line one" in result[0]['text']
        assert "Line two" in result[0]['text']
        assert "Line three" in result[0]['text']

    def test_parse_empty_content(self):
        """Test parsing empty content."""
        result = parse_comments("")
        assert len(result) == 0

    def test_parse_zero_likes(self):
        """Test parsing comment with zero likes."""
        content = "### 1. @user1 (0 likes)\n\nNo likes comment\n"
        result = parse_comments(content)

        assert len(result) == 1
        assert result[0]['likes'] == 0


class TestFilterComments:
    """Tests for filter_comments function."""

    def test_filter_keeps_long_comments(self):
        """Test that comments with >=20 chars are kept regardless of likes."""
        comments = [
            {'author': 'user1', 'likes': 0, 'text': 'This is a long enough comment'},
        ]
        result = filter_comments(comments)

        assert len(result) == 1

    def test_filter_keeps_popular_comments(self):
        """Test that comments with >=2 likes are kept regardless of length."""
        comments = [
            {'author': 'user1', 'likes': 5, 'text': 'Short'},
        ]
        result = filter_comments(comments)

        assert len(result) == 1

    def test_filter_removes_short_and_unpopular(self):
        """Test that short AND unpopular comments are removed."""
        comments = [
            {'author': 'user1', 'likes': 0, 'text': 'Short'},
            {'author': 'user2', 'likes': 1, 'text': 'Also short'},
        ]
        result = filter_comments(comments)

        assert len(result) == 0

    def test_filter_respects_max_comments(self):
        """Test that max_comments limit is respected."""
        comments = [
            {'author': f'user{i}', 'likes': 100 - i, 'text': 'This is a valid comment'}
            for i in range(10)
        ]
        result = filter_comments(comments, max_comments=5)

        assert len(result) == 5

    def test_filter_default_max_is_200(self):
        """Test that default max is MAX_COMMENTS (200)."""
        comments = [
            {'author': f'user{i}', 'likes': 10, 'text': 'This is a valid comment'}
            for i in range(300)
        ]
        result = filter_comments(comments)

        assert len(result) == MAX_COMMENTS

    def test_filter_preserves_order(self):
        """Test that comment order is preserved (already sorted by yt-dlp)."""
        comments = [
            {'author': 'user1', 'likes': 100, 'text': 'First comment here'},
            {'author': 'user2', 'likes': 50, 'text': 'Second comment here'},
            {'author': 'user3', 'likes': 25, 'text': 'Third comment here'},
        ]
        result = filter_comments(comments)

        assert result[0]['author'] == 'user1'
        assert result[1]['author'] == 'user2'
        assert result[2]['author'] == 'user3'

    def test_filter_edge_case_exactly_20_chars(self):
        """Test comment with exactly 20 characters."""
        comments = [
            {'author': 'user1', 'likes': 0, 'text': '12345678901234567890'},  # exactly 20
        ]
        result = filter_comments(comments)

        assert len(result) == 1

    def test_filter_edge_case_exactly_2_likes(self):
        """Test comment with exactly 2 likes."""
        comments = [
            {'author': 'user1', 'likes': 2, 'text': 'Short'},
        ]
        result = filter_comments(comments)

        assert len(result) == 1


class TestFormatComments:
    """Tests for format_comments function."""

    def test_format_single_comment(self):
        """Test formatting a single comment."""
        comments = [{'author': 'user1', 'likes': 42, 'text': 'Test comment'}]
        result = format_comments(comments)

        assert "### 1. @user1 (42 likes)" in result
        assert "Test comment" in result

    def test_format_multiple_comments(self):
        """Test formatting multiple comments with renumbering."""
        comments = [
            {'author': 'user1', 'likes': 100, 'text': 'First'},
            {'author': 'user2', 'likes': 50, 'text': 'Second'},
        ]
        result = format_comments(comments)

        assert "### 1. @user1 (100 likes)" in result
        assert "### 2. @user2 (50 likes)" in result

    def test_format_empty_list(self):
        """Test formatting empty list."""
        result = format_comments([])
        assert result == ''

    def test_format_preserves_multiline_text(self):
        """Test that multiline text is preserved."""
        comments = [{'author': 'user1', 'likes': 10, 'text': 'Line1\nLine2\nLine3'}]
        result = format_comments(comments)

        assert "Line1\nLine2\nLine3" in result
