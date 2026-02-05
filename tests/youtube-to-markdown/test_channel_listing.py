"""Tests for lib/channel_listing.py."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "youtube-to-markdown"))
from lib.channel_listing import (
    _normalize_channel_url,
    parse_channel_entry,
    parse_channel_metadata,
    match_existing_videos,
    check_comment_growth,
    find_output_dir,
    suggest_output_dir,
)


SAMPLE_FLAT_ENTRY = {
    "id": "BHdbsHFs2P0",
    "title": "The Hairy Ball Theorem",
    "view_count": 1946655,
    "duration": 1780.0,
    "duration_string": "29:40",
    "url": "https://www.youtube.com/watch?v=BHdbsHFs2P0",
    "original_url": "https://www.youtube.com/watch?v=BHdbsHFs2P0",
    "webpage_url": "https://www.youtube.com/watch?v=BHdbsHFs2P0",
    "description": "Some description",
    "channel_is_verified": True,
    "playlist_channel": "3Blue1Brown",
    "playlist_channel_id": "UCYO_jab_esuFRV4b17AJtAw",
    "playlist_uploader_id": "@3blue1brown",
    "playlist_count": 147,
    "playlist_title": "3Blue1Brown - Videos",
    "playlist_webpage_url": "https://www.youtube.com/@3blue1brown/videos",
    "playlist_autonumber": 1,
    "n_entries": 147,
    "_type": "url",
}

SAMPLE_FLAT_ENTRY_MINIMAL = {
    "id": "xyz789",
    "title": "Minimal Video",
    "url": "https://www.youtube.com/watch?v=xyz789",
}


class TestNormalizeChannelUrl:
    """Tests for _normalize_channel_url."""

    def test_already_has_videos(self):
        assert _normalize_channel_url("https://www.youtube.com/@chan/videos") == "https://www.youtube.com/@chan/videos"

    def test_bare_channel(self):
        assert _normalize_channel_url("https://www.youtube.com/@chan") == "https://www.youtube.com/@chan/videos"

    def test_trailing_slash(self):
        assert _normalize_channel_url("https://www.youtube.com/@chan/") == "https://www.youtube.com/@chan/videos"

    def test_shorts_tab(self):
        assert _normalize_channel_url("https://www.youtube.com/@chan/shorts") == "https://www.youtube.com/@chan/videos"

    def test_live_tab(self):
        assert _normalize_channel_url("https://www.youtube.com/@chan/live") == "https://www.youtube.com/@chan/videos"

    def test_channel_id_format(self):
        assert _normalize_channel_url("https://www.youtube.com/channel/UC123") == "https://www.youtube.com/channel/UC123/videos"

    def test_community_tab(self):
        assert _normalize_channel_url("https://www.youtube.com/@chan/community") == "https://www.youtube.com/@chan/videos"

    def test_playlists_tab(self):
        assert _normalize_channel_url("https://www.youtube.com/@chan/playlists") == "https://www.youtube.com/@chan/videos"

    def test_streams_tab(self):
        assert _normalize_channel_url("https://www.youtube.com/@chan/streams") == "https://www.youtube.com/@chan/videos"


class TestParseChannelEntry:
    """Tests for parse_channel_entry."""

    def test_full_entry(self):
        result = parse_channel_entry(SAMPLE_FLAT_ENTRY)
        assert result["video_id"] == "BHdbsHFs2P0"
        assert result["title"] == "The Hairy Ball Theorem"
        assert result["views"] == "1.9M"
        assert result["duration"] == "29:40"
        assert result["url"] == "https://www.youtube.com/watch?v=BHdbsHFs2P0"

    def test_minimal_entry(self):
        result = parse_channel_entry(SAMPLE_FLAT_ENTRY_MINIMAL)
        assert result["video_id"] == "xyz789"
        assert result["title"] == "Minimal Video"
        assert result["views"] == "N/A"
        assert result["duration"] == "N/A"
        assert result["url"] == "https://www.youtube.com/watch?v=xyz789"

    def test_zero_views(self):
        entry = {**SAMPLE_FLAT_ENTRY_MINIMAL, "view_count": 0}
        result = parse_channel_entry(entry)
        assert result["views"] == "0"

    def test_small_view_count(self):
        entry = {**SAMPLE_FLAT_ENTRY_MINIMAL, "view_count": 500}
        result = parse_channel_entry(entry)
        assert result["views"] == "500"


class TestParseChannelMetadata:
    """Tests for parse_channel_metadata."""

    def test_full_entry(self):
        result = parse_channel_metadata(SAMPLE_FLAT_ENTRY)
        assert result["name"] == "3Blue1Brown"
        assert result["id"] == "UCYO_jab_esuFRV4b17AJtAw"
        assert result["url"] == "https://www.youtube.com/@3blue1brown/videos"
        assert result["total_videos"] == 147
        assert result["verified"] is True

    def test_minimal_entry(self):
        result = parse_channel_metadata(SAMPLE_FLAT_ENTRY_MINIMAL)
        assert result["name"] is None
        assert result["id"] is None
        assert result["total_videos"] is None
        assert result["verified"] is False


class TestMatchExistingVideos:
    """Tests for match_existing_videos."""

    def test_no_existing_videos(self, tmp_path):
        videos = [
            {"video_id": "abc123", "title": "Video A", "views": "1K", "duration": "10:00", "url": "https://youtube.com/watch?v=abc123"},
        ]
        new, existing = match_existing_videos(videos, tmp_path)
        assert len(new) == 1
        assert len(existing) == 0
        assert new[0]["video_id"] == "abc123"

    def test_existing_video_in_root(self, tmp_path):
        # Create a summary file with metadata
        summary = tmp_path / "youtube - Test Video (abc123).md"
        summary.write_text(
            "## Video\n\n"
            "- **Title:** [Test Video](https://youtube.com/watch?v=abc123) · 10:00\n"
            "- **Channel:** [Chan](https://youtube.com/c/chan) (1K subscribers)\n"
            "- **Engagement:** 1K views · 100 likes · 50 comments\n"
            "- **Published:** 2025-01-01 | Extracted: 2025-06-01\n"
        )
        videos = [
            {"video_id": "abc123", "title": "Test Video", "views": "1K", "duration": "10:00", "url": "https://youtube.com/watch?v=abc123"},
            {"video_id": "def456", "title": "New Video", "views": "2K", "duration": "05:00", "url": "https://youtube.com/watch?v=def456"},
        ]
        new, existing = match_existing_videos(videos, tmp_path)
        assert len(new) == 1
        assert new[0]["video_id"] == "def456"
        assert len(existing) == 1
        assert existing[0]["video_id"] == "abc123"
        assert existing[0]["stored_comments"] == "50"

    def test_existing_video_in_subdir(self, tmp_path):
        subdir = tmp_path / "3Blue1Brown (UCYO)"
        subdir.mkdir()
        summary = subdir / "youtube - Test Video (abc123).md"
        summary.write_text(
            "## Video\n\n"
            "- **Title:** [Test](https://youtube.com/watch?v=abc123) · 10:00\n"
            "- **Channel:** [C](https://youtube.com/c/c) (1K subscribers)\n"
            "- **Engagement:** 5K views · 200 likes · 120 comments\n"
            "- **Published:** 2025-01-01 | Extracted: 2025-06-01\n"
        )
        videos = [
            {"video_id": "abc123", "title": "Test", "views": "5K", "duration": "10:00", "url": "https://youtube.com/watch?v=abc123"},
        ]
        new, existing = match_existing_videos(videos, tmp_path)
        assert len(new) == 0
        assert len(existing) == 1
        assert existing[0]["stored_comments"] == "120"

    def test_ignores_backup_files(self, tmp_path):
        summary = tmp_path / "youtube - Test (abc123).md"
        summary.write_text(
            "## Video\n\n"
            "- **Title:** [Test](https://youtube.com/watch?v=abc123) · 10:00\n"
            "- **Channel:** [C](https://youtube.com/c/c) (1K subscribers)\n"
            "- **Engagement:** 1K views · 50 likes · 30 comments\n"
            "- **Published:** 2025-01-01 | Extracted: 2025-06-01\n"
        )
        backup = tmp_path / "youtube - Test (abc123)_backup_20250601_120000.md"
        backup.write_text("old content")

        videos = [
            {"video_id": "abc123", "title": "Test", "views": "1K", "duration": "10:00", "url": "https://youtube.com/watch?v=abc123"},
        ]
        new, existing = match_existing_videos(videos, tmp_path)
        assert len(existing) == 1

    def test_empty_video_list(self, tmp_path):
        new, existing = match_existing_videos([], tmp_path)
        assert new == []
        assert existing == []

    def test_old_metadata_format(self, tmp_path):
        """Old format: Views/Likes line instead of Engagement line."""
        summary = tmp_path / "youtube - Old (old123).md"
        summary.write_text(
            "## Video\n\n"
            "- **Title:** [Old](https://youtube.com/watch?v=old123) · 10:00\n"
            "- **Views:** 5,000 | Likes: 200 | Duration: 10:00\n"
        )
        videos = [
            {"video_id": "old123", "title": "Old", "views": "5K", "duration": "10:00", "url": "https://youtube.com/watch?v=old123"},
        ]
        new, existing = match_existing_videos(videos, tmp_path)
        assert len(existing) == 1
        # Old format doesn't have comments field
        assert existing[0]["stored_comments"] is None


class TestCheckCommentGrowth:
    """Tests for check_comment_growth."""

    def test_significant_growth(self, tmp_path):
        """25% growth should be flagged."""
        summary = tmp_path / "youtube - Test (vid1).md"
        summary.write_text(
            "## Video\n\n"
            "- **Title:** [Test](https://youtube.com/watch?v=vid1) · 10:00\n"
            "- **Channel:** [C](https://youtube.com/c/c) (1K subscribers)\n"
            "- **Engagement:** 5K views · 200 likes · 1.2K comments\n"
            "- **Published:** 2025-01-01 | Extracted: 2025-06-01\n"
        )
        current_counts = {"vid1": 1500}
        results = check_comment_growth(current_counts, tmp_path)
        assert len(results) == 1
        assert results[0]["needs_refresh"] is True
        assert results[0]["growth_pct"] == pytest.approx(25.0, abs=1.0)

    def test_below_threshold(self, tmp_path):
        """5% growth should NOT be flagged."""
        summary = tmp_path / "youtube - Test (vid2).md"
        summary.write_text(
            "## Video\n\n"
            "- **Title:** [Test](https://youtube.com/watch?v=vid2) · 10:00\n"
            "- **Channel:** [C](https://youtube.com/c/c) (1K subscribers)\n"
            "- **Engagement:** 5K views · 200 likes · 1K comments\n"
            "- **Published:** 2025-01-01 | Extracted: 2025-06-01\n"
        )
        current_counts = {"vid2": 1050}
        results = check_comment_growth(current_counts, tmp_path)
        assert len(results) == 1
        assert results[0]["needs_refresh"] is False

    def test_exactly_10_percent(self, tmp_path):
        """Exactly 10% should NOT be flagged (>10% required)."""
        summary = tmp_path / "youtube - Test (vid3).md"
        summary.write_text(
            "## Video\n\n"
            "- **Title:** [Test](https://youtube.com/watch?v=vid3) · 10:00\n"
            "- **Channel:** [C](https://youtube.com/c/c) (1K subscribers)\n"
            "- **Engagement:** 5K views · 200 likes · 1K comments\n"
            "- **Published:** 2025-01-01 | Extracted: 2025-06-01\n"
        )
        current_counts = {"vid3": 1100}
        results = check_comment_growth(current_counts, tmp_path)
        assert results[0]["needs_refresh"] is False

    def test_11_percent_growth(self, tmp_path):
        """11% growth should be flagged."""
        summary = tmp_path / "youtube - Test (vid4).md"
        summary.write_text(
            "## Video\n\n"
            "- **Title:** [Test](https://youtube.com/watch?v=vid4) · 10:00\n"
            "- **Channel:** [C](https://youtube.com/c/c) (1K subscribers)\n"
            "- **Engagement:** 5K views · 200 likes · 1K comments\n"
            "- **Published:** 2025-01-01 | Extracted: 2025-06-01\n"
        )
        current_counts = {"vid4": 1110}
        results = check_comment_growth(current_counts, tmp_path)
        assert results[0]["needs_refresh"] is True

    def test_no_stored_comments(self, tmp_path):
        """Video without stored comment count should not crash."""
        summary = tmp_path / "youtube - Test (vid5).md"
        summary.write_text(
            "## Video\n\n"
            "- **Title:** [Test](https://youtube.com/watch?v=vid5) · 10:00\n"
            "- **Views:** 5,000 | Likes: 200 | Duration: 10:00\n"
        )
        current_counts = {"vid5": 500}
        results = check_comment_growth(current_counts, tmp_path)
        assert len(results) == 1
        assert results[0]["stored_comments"] is None
        assert results[0]["needs_refresh"] is False

    def test_multiple_videos(self, tmp_path):
        for vid_id, comments in [("a1", "100"), ("b2", "200")]:
            f = tmp_path / f"youtube - Vid ({vid_id}).md"
            f.write_text(
                "## Video\n\n"
                f"- **Title:** [Vid](https://youtube.com/watch?v={vid_id}) · 10:00\n"
                f"- **Channel:** [C](https://youtube.com/c/c) (1K subscribers)\n"
                f"- **Engagement:** 5K views · 50 likes · {comments} comments\n"
                f"- **Published:** 2025-01-01 | Extracted: 2025-06-01\n"
            )
        current_counts = {"a1": 150, "b2": 210}
        results = check_comment_growth(current_counts, tmp_path)
        assert len(results) == 2
        # a1: 100 → 150 = 50% growth
        r_a1 = next(r for r in results if r["video_id"] == "a1")
        assert r_a1["needs_refresh"] is True
        # b2: 200 → 210 = 5% growth
        r_b2 = next(r for r in results if r["video_id"] == "b2")
        assert r_b2["needs_refresh"] is False


class TestFindOutputDir:
    """Tests for find_output_dir."""

    def test_no_matching_subdir(self, tmp_path):
        result = find_output_dir(tmp_path, "UC_some_id")
        assert result is None

    def test_matching_subdir(self, tmp_path):
        subdir = tmp_path / "Channel Name (UC_some_id)"
        subdir.mkdir()
        result = find_output_dir(tmp_path, "UC_some_id")
        assert result == subdir

    def test_partial_match_ignored(self, tmp_path):
        subdir = tmp_path / "UC_some_id_extended"
        subdir.mkdir()
        result = find_output_dir(tmp_path, "UC_some_id")
        # Should still match because channel_id is contained
        assert result == subdir

    def test_files_ignored(self, tmp_path):
        """Files with channel ID in name should not match."""
        f = tmp_path / "UC_some_id.txt"
        f.write_text("not a dir")
        result = find_output_dir(tmp_path, "UC_some_id")
        assert result is None


class TestSuggestOutputDir:

    def test_basic(self, tmp_path):
        result = suggest_output_dir(tmp_path, "3Blue1Brown", "UCYO_jab")
        assert result == tmp_path / "3Blue1Brown (UCYO_jab)"

    def test_special_chars_in_name(self, tmp_path):
        result = suggest_output_dir(tmp_path, "Channel: Name/Test", "UC123")
        name = result.name
        assert "/" not in name
        assert ":" not in name
