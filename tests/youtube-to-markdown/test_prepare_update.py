"""Tests for prepare_update module."""

import pytest
from pathlib import Path
from prepare_update import (
    parse_count,
    compare_counts,
    compare_strings,
    detect_issues,
    generate_recommendation,
)


class TestParseCount:
    """Tests for parse_count function."""

    def test_parse_billions(self):
        assert parse_count("1.5B") == 1_500_000_000
        assert parse_count("1B") == 1_000_000_000
        assert parse_count("2.7B") == 2_700_000_000

    def test_parse_millions(self):
        assert parse_count("2.2M") == 2_200_000
        assert parse_count("1M") == 1_000_000
        assert parse_count("10.5M") == 10_500_000

    def test_parse_thousands(self):
        assert parse_count("71K") == 71_000
        assert parse_count("1.5K") == 1_500
        assert parse_count("500K") == 500_000

    def test_parse_plain_numbers(self):
        assert parse_count("500") == 500
        assert parse_count("1234") == 1234

    def test_parse_comma_separated(self):
        assert parse_count("1,234,567") == 1234567
        assert parse_count("10,000") == 10000

    def test_parse_none_values(self):
        assert parse_count(None) is None
        assert parse_count("N/A") is None


class TestCompareCounts:
    """Tests for compare_counts function."""

    def test_no_change(self):
        result = compare_counts(1000, 1000)
        assert result["changed"] is False
        assert result["significant"] is False

    def test_small_increase(self):
        result = compare_counts(1000, 1200)
        assert result["changed"] is True
        assert result["significant"] is False  # 20% < 50%

    def test_significant_increase(self):
        result = compare_counts(1000, 2000)
        assert result["changed"] is True
        assert result["significant"] is True  # 100% > 50%

    def test_decrease_not_significant(self):
        result = compare_counts(2000, 1000)
        assert result["changed"] is True
        assert result["significant"] is False  # Decrease never significant

    def test_none_values(self):
        result = compare_counts(None, 1000)
        assert result["changed"] is True
        assert result["significant"] is False


class TestCompareStrings:
    """Tests for compare_strings function."""

    def test_no_change(self):
        result = compare_strings("hello", "hello")
        assert result["changed"] is False

    def test_changed(self):
        result = compare_strings("old", "new")
        assert result["changed"] is True

    def test_none_values(self):
        result = compare_strings(None, "new")
        assert result["changed"] is True


class TestDetectIssues:
    """Tests for detect_issues function."""

    def test_summary_v1_detected(self):
        existing = {"summary_v1": True}
        changes = {}
        issues = detect_issues(existing, changes)
        assert any("summary_v1" in issue for issue in issues)

    def test_comments_v1_detected(self):
        existing = {"comments_v1": True}
        changes = {}
        issues = detect_issues(existing, changes)
        assert any("comments_v1" in issue for issue in issues)

    def test_significant_comment_increase(self):
        existing = {}
        changes = {"comment_count": {"old": 100, "new": 500, "changed": True, "significant": True}}
        issues = detect_issues(existing, changes)
        assert any("comment_count increased" in issue for issue in issues)

    def test_title_changed(self):
        existing = {}
        changes = {"title": {"old": "Old", "new": "New", "changed": True}}
        issues = detect_issues(existing, changes)
        assert any("title changed" in issue for issue in issues)

    def test_chapters_added(self):
        existing = {}
        changes = {"chapters": {"old": 0, "new": 5, "changed": True}}
        issues = detect_issues(existing, changes)
        assert any("chapters added" in issue for issue in issues)

    def test_summary_issues_reported(self):
        existing = {"summary_issues": ["empty_video_section", "missing_tldr"]}
        changes = {}
        issues = detect_issues(existing, changes)
        assert any("summary_invalid" in issue for issue in issues)

    def test_no_issues(self):
        existing = {"summary_v1": False, "comments_v1": False}
        changes = {"views": {"old": 1000, "new": 1100, "changed": True, "significant": False}}
        issues = detect_issues(existing, changes)
        assert len(issues) == 0


class TestGenerateRecommendation:
    """Tests for generate_recommendation function."""

    def test_summary_v1_upgrade(self):
        existing = {"summary_v1": True, "summary_file": "/path/summary.md"}
        changes = {}
        issues = ["summary_v1: outdated format"]
        rec = generate_recommendation(existing, changes, issues)
        assert rec["action"] == "update_summary"
        assert "/path/summary.md" in rec["files_to_backup"]

    def test_comments_v1_upgrade(self):
        existing = {
            "summary_v1": False,
            "comments_v1": True,
            "comment_file": "/path/comments.md",
        }
        changes = {}
        issues = ["comments_v1: outdated format"]
        rec = generate_recommendation(existing, changes, issues)
        assert rec["action"] == "update_comments"
        assert "/path/comments.md" in rec["files_to_backup"]

    def test_significant_comment_increase(self):
        existing = {
            "summary_v1": False,
            "comments_v1": False,
            "comment_file": "/path/comments.md",
        }
        changes = {"comment_count": {"old": 100, "new": 500, "changed": True, "significant": True}}
        issues = ["comment_count increased significantly"]
        rec = generate_recommendation(existing, changes, issues)
        assert rec["action"] == "update_comments"

    def test_metadata_only(self):
        existing = {
            "summary_v1": False,
            "comments_v1": False,
            "summary_file": "/path/summary.md",
        }
        changes = {
            "views": {"old": 1000, "new": 1500, "changed": True, "significant": False},
            "likes": {"old": 100, "new": 120, "changed": True, "significant": False},
        }
        issues = []
        rec = generate_recommendation(existing, changes, issues)
        assert rec["action"] == "metadata_only"
        assert rec["files_to_backup"] == []

    def test_extend_with_comments(self):
        existing = {
            "summary_v1": False,
            "summary_file": "/path/summary.md",
            "comment_file": None,
        }
        changes = {"views": {"changed": False}}
        issues = []
        rec = generate_recommendation(existing, changes, issues)
        assert rec["action"] == "extend"
        assert rec["suggested_output"] == "D"

    def test_no_recommendation_needed(self):
        existing = {
            "summary_v1": False,
            "comments_v1": False,
            "summary_file": "/path/summary.md",
            "transcript_file": "/path/transcript.md",
            "comment_file": "/path/comments.md",
        }
        changes = {
            "views": {"changed": False},
            "likes": {"changed": False},
            "comment_count": {"changed": False},
        }
        issues = []
        rec = generate_recommendation(existing, changes, issues)
        assert rec["action"] == "none"

    def test_title_change_triggers_full_refresh(self):
        existing = {
            "summary_v1": False,
            "comments_v1": False,
            "summary_file": "/path/summary.md",
        }
        changes = {"title": {"old": "Old Title", "new": "New Title", "changed": True}}
        issues = ["title changed"]
        rec = generate_recommendation(existing, changes, issues)
        assert rec["action"] == "full_refresh"
