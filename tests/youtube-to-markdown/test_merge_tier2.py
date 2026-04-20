"""Tests for comment merge (tier 2 → prefiltered)."""

from lib.comment_merge import merge_kept_comments, parse_compact, parse_keep_list
from lib.content_safety import wrap_untrusted_content


class TestParseCompact:
    def test_parses_single_line(self) -> None:
        line = "[5|@alice|10 likes] This is a comment"
        result = parse_compact(line)
        assert len(result) == 1
        assert result[0] == {"index": 5, "author": "alice", "likes": 10, "text": "This is a comment"}

    def test_parses_multiple_lines(self) -> None:
        content = "[1|@alice|5 likes] Hello\n[3|@bob|2 likes] World"
        result = parse_compact(content)
        assert len(result) == 2
        assert result[0]["index"] == 1
        assert result[1]["index"] == 3

    def test_empty_input(self) -> None:
        assert parse_compact("") == []

    def test_likes_with_special_chars_in_text(self) -> None:
        line = "[1|@user|3 likes] Text with [brackets] and |pipes|"
        result = parse_compact(line)
        assert result[0]["text"] == "Text with [brackets] and |pipes|"


class TestParseKeepList:
    def test_basic(self) -> None:
        assert parse_keep_list("KEEP: 17, 45, 51") == [17, 45, 51]

    def test_without_prefix(self) -> None:
        assert parse_keep_list("17, 45, 51") == [17, 45, 51]

    def test_single_number(self) -> None:
        assert parse_keep_list("KEEP: 5") == [5]

    def test_empty(self) -> None:
        assert parse_keep_list("") == []
        assert parse_keep_list("KEEP:") == []

    def test_trailing_period(self) -> None:
        assert parse_keep_list("KEEP: 5.") == [5]

    def test_non_numeric_tokens_skipped(self) -> None:
        assert parse_keep_list("KEEP: 5, abc, 10") == [5, 10]

    def test_trailing_comma(self) -> None:
        assert parse_keep_list("KEEP: 5, 10,") == [5, 10]

    def test_lowercase_keep_prefix(self) -> None:
        assert parse_keep_list("Keep: 2, 3") == [2, 3]

    def test_multiline_ignores_trailing_explanation(self) -> None:
        assert parse_keep_list("KEEP: 17, 45, 51\nReason: these are good") == [17, 45, 51]


class TestMergeKeptComments:
    def test_appends_kept_comments(self) -> None:
        prefiltered = "### 1. @alice (10 likes)\n\nGreat video\n"
        candidates = [
            {"index": 5, "author": "bob", "likes": 2, "text": "Nice"},
            {"index": 8, "author": "carol", "likes": 1, "text": "Meh"},
        ]
        result = merge_kept_comments(prefiltered, candidates, [5])
        assert "@bob" in result
        assert "@carol" not in result

    def test_renumbers_sequentially(self) -> None:
        prefiltered = "### 1. @alice (10 likes)\n\nHello\n"
        candidates = [{"index": 5, "author": "bob", "likes": 2, "text": "World"}]
        result = merge_kept_comments(prefiltered, candidates, [5])
        assert "### 1. @alice" in result
        assert "### 2. @bob" in result
        assert "### 5." not in result

    def test_empty_keep_list(self) -> None:
        prefiltered = "### 1. @alice (10 likes)\n\nHello\n"
        result = merge_kept_comments(prefiltered, [], [])
        assert result == prefiltered

    def test_preserves_existing_prefiltered(self) -> None:
        prefiltered = "### 1. @alice (10 likes)\n\nHello\n\n### 2. @bob (5 likes)\n\nWorld\n"
        candidates = [{"index": 8, "author": "carol", "likes": 1, "text": "Added"}]
        result = merge_kept_comments(prefiltered, candidates, [8])
        assert "### 1. @alice" in result
        assert "### 2. @bob" in result
        assert "### 3. @carol" in result

    def test_renumber_does_not_match_inside_comment_text(self) -> None:
        prefiltered = "### 1. @alice (10 likes)\n\nSee section ### 3. for details\n"
        candidates = [{"index": 5, "author": "bob", "likes": 2, "text": "OK"}]
        result = merge_kept_comments(prefiltered, candidates, [5])
        # The "### 3." inside comment text must NOT be renumbered
        assert "### 3. for details" in result
        assert "### 1. @alice" in result
        assert "### 2. @bob" in result

    def test_body_text_not_modified_plain(self) -> None:
        prefiltered = "### 1. @alice (10 likes)\n\n### 99. not a header\n"
        candidates = [{"index": 5, "author": "bob", "likes": 2, "text": "OK"}]
        result = merge_kept_comments(prefiltered, candidates, [5])
        assert "### 99. not a header" in result
        assert "### 1. @alice" in result
        assert "### 2. @bob" in result

    def test_body_text_not_modified_with_at_sign(self) -> None:
        # Body line mimicking header format: "### N. @..." must NOT be altered
        # Numbering gap is acceptable — body text integrity is what matters
        prefiltered = "### 1. @alice (10 likes)\n\n### 99. @not_a_header\n"
        candidates = [{"index": 5, "author": "bob", "likes": 2, "text": "OK"}]
        result = merge_kept_comments(prefiltered, candidates, [5])
        assert "### 99. @not_a_header" in result  # body preserved
        assert "### 1. @alice" in result
        assert "@bob" in result  # bob appended (number may have gap)

    def test_duplicate_keep_indices_deduplicated(self) -> None:
        prefiltered = "### 1. @alice (10 likes)\n\nHello\n"
        candidates = [{"index": 5, "author": "bob", "likes": 2, "text": "World"}]
        result = merge_kept_comments(prefiltered, candidates, [5, 5])
        assert result.count("@bob") == 1


class TestSafetyWrapperIntegration:
    def test_merged_content_wrapped_in_safety_tags(self) -> None:
        prefiltered = "### 1. @alice (10 likes)\n\nHello\n"
        candidates = [{"index": 5, "author": "bob", "likes": 2, "text": "World"}]
        result = merge_kept_comments(prefiltered, candidates, [5])
        wrapped = wrap_untrusted_content(result, "comments")
        assert "<untrusted_comments_content>" in wrapped
        assert "</untrusted_comments_content>" in wrapped
        assert "### 1. @alice" in wrapped
        assert "### 2. @bob" in wrapped

    def test_empty_keep_wrapped_in_safety_tags(self) -> None:
        prefiltered = "### 1. @alice (10 likes)\n\nHello\n"
        wrapped = wrap_untrusted_content(prefiltered, "comments")
        assert "<untrusted_comments_content>" in wrapped
        assert "@alice" in wrapped


class TestParseCompactWarnings:
    def test_malformed_lines_skipped_with_warning(self, capsys) -> None:
        content = "[1|@alice|5 likes] Hello\ngarbage line\n[3|@bob|2 likes] World"
        result = parse_compact(content)
        assert len(result) == 2
        captured = capsys.readouterr()
        assert "WARNING" in captured.out
        assert "1 malformed" in captured.out
