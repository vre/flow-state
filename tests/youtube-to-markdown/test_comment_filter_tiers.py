"""Tests for comment_filter tier split functions."""

from lib.comment_filter import (
    calculate_likes_p75,
    format_compact,
    split_tiers,
)


def _make_comment(author: str, likes: int, text: str, index: int) -> dict:
    return {"author": author, "likes": likes, "text": text, "index": index}


def _make_comments(specs: list[tuple[int, int]]) -> list[dict]:
    """Create comments from (likes, text_length) specs."""
    return [_make_comment(f"user{i}", likes, "x" * length, i) for i, (likes, length) in enumerate(specs, 1)]


class TestCalculateLikesP75:
    def test_basic_distribution(self) -> None:
        comments = _make_comments([(1, 50), (2, 50), (3, 50), (10, 50)])
        assert calculate_likes_p75(comments) == 3

    def test_all_same_likes(self) -> None:
        comments = _make_comments([(5, 50)] * 10)
        assert calculate_likes_p75(comments) == 5

    def test_single_comment(self) -> None:
        comments = _make_comments([(42, 50)])
        assert calculate_likes_p75(comments) == 42

    def test_empty_list(self) -> None:
        assert calculate_likes_p75([]) == 0

    def test_large_distribution(self) -> None:
        # 100 comments with likes 1-100, p75 should be ~75
        comments = _make_comments([(i, 50) for i in range(1, 101)])
        p75 = calculate_likes_p75(comments)
        assert 74 <= p75 <= 76


class TestSplitTiers:
    def test_split_by_likes_threshold(self) -> None:
        comments = _make_comments([(100, 50), (50, 50), (10, 50), (1, 50)])
        tier1, tier2 = split_tiers(comments, likes_threshold=50, skip_threshold=0)
        assert len(tier1) == 2  # 100, 50
        assert len(tier2) == 2  # 10, 1

    def test_split_by_length_threshold(self) -> None:
        comments = _make_comments([(1, 500), (1, 100)])
        tier1, tier2 = split_tiers(comments, likes_threshold=999, length_threshold=400, skip_threshold=0)
        assert len(tier1) == 1  # 500 chars
        assert len(tier2) == 1  # 100 chars

    def test_split_combined_or_logic(self) -> None:
        comments = _make_comments([(100, 50), (1, 500), (1, 50)])
        tier1, tier2 = split_tiers(comments, likes_threshold=50, length_threshold=400, skip_threshold=0)
        assert len(tier1) == 2  # high likes OR long text
        assert len(tier2) == 1  # low likes AND short text

    def test_split_auto_p75_when_none(self) -> None:
        # 4 comments: p75 of [1, 2, 3, 10] = 3
        comments = _make_comments([(1, 50), (2, 50), (3, 50), (10, 50)])
        tier1, tier2 = split_tiers(comments, likes_threshold=None, skip_threshold=0)
        # tier1: likes >= 3 → comments with 3 and 10 likes
        assert len(tier1) == 2
        assert all(c["likes"] >= 3 for c in tier1)

    def test_split_preserves_original_index(self) -> None:
        comments = _make_comments([(100, 50), (1, 50), (50, 50)])
        tier1, tier2 = split_tiers(comments, likes_threshold=50, skip_threshold=0)
        assert tier1[0]["index"] == 1
        assert tier1[1]["index"] == 3
        assert tier2[0]["index"] == 2


class TestFormatCompact:
    def test_compact_format_structure(self) -> None:
        comments = [_make_comment("alice", 5, "Hello world", 1)]
        result = format_compact(comments)
        assert result == "[1|@alice|5 likes] Hello world"

    def test_compact_singular_like(self) -> None:
        comments = [_make_comment("alice", 1, "Hello", 1)]
        result = format_compact(comments)
        assert "|1 like]" in result
        assert "|1 likes]" not in result

    def test_compact_no_blank_lines(self) -> None:
        comments = [
            _make_comment("a", 1, "Line one", 1),
            _make_comment("b", 2, "Line two", 2),
        ]
        result = format_compact(comments)
        assert "\n\n" not in result
        assert len(result.strip().split("\n")) == 2

    def test_compact_newlines_in_text_collapsed(self) -> None:
        comments = [_make_comment("a", 1, "Line one\n\nLine two", 1)]
        result = format_compact(comments)
        assert "\n" not in result.split("\n")[0].split("] ", 1)[1]

    def test_compact_empty_list(self) -> None:
        assert format_compact([]) == ""


class TestSkipTierSplit:
    def test_80_or_fewer_all_go_to_tier1(self) -> None:
        comments = _make_comments([(i, 50) for i in range(80)])
        tier1, tier2 = split_tiers(comments, skip_threshold=80)
        assert len(tier1) == 80
        assert len(tier2) == 0

    def test_81_comments_triggers_split(self) -> None:
        # 81 comments with likes 1-81, p75 ~ 61 → ~20 in tier1, ~61 in tier2
        comments = _make_comments([(i, 50) for i in range(1, 82)])
        tier1, tier2 = split_tiers(comments, skip_threshold=80)
        assert len(tier1) + len(tier2) == 81
        assert len(tier2) > 0  # Split actually happened
        assert max(c["likes"] for c in tier2) < min(c["likes"] for c in tier1)
