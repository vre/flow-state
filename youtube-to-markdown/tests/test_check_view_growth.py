"""Tests for check_view_growth in lib/channel_listing.py."""

from pathlib import Path

from lib.channel_listing import check_view_growth


def _make_summary(title: str, views: str) -> str:
    """Build minimal summary file content with views metadata."""
    return f"""# Video

**Title:** [{title}](https://youtube.com/watch?v=abc)

- **Engagement:** {views} views · 100 likes · 50 comments

- **Published:** 2025-01-01 | Extracted: 2025-01-15

## Summary

### TL;DR
Test summary.
"""


def _make_existing_video(video_id: str, view_count: int) -> dict:
    return {
        "video_id": video_id,
        "title": f"Video {video_id}",
        "views": "1M",
        "view_count": view_count,
        "duration": "10:00",
        "url": f"https://youtube.com/watch?v={video_id}",
    }


class TestCheckViewGrowth:
    """Tests for check_view_growth()."""

    def test_growth_above_threshold(self, tmp_path: Path) -> None:
        """Videos with >30% view growth are flagged."""
        # Stored: 1M, current: 1.5M → 50% growth
        summary = _make_summary("Test Video", "1M")
        (tmp_path / "youtube - Test Video (vid1).md").write_text(summary)

        existing = [_make_existing_video("vid1", 1_500_000)]
        result = check_view_growth(existing, tmp_path, threshold=0.3)

        assert len(result) == 1
        assert result[0]["video_id"] == "vid1"
        assert result[0]["growth_pct"] > 30
        assert result[0]["has_growth"] is True

    def test_growth_below_threshold(self, tmp_path: Path) -> None:
        """Videos with <30% growth are not flagged."""
        # Stored: 1M, current: 1.1M → 10% growth
        summary = _make_summary("Test Video", "1M")
        (tmp_path / "youtube - Test Video (vid1).md").write_text(summary)

        existing = [_make_existing_video("vid1", 1_100_000)]
        result = check_view_growth(existing, tmp_path, threshold=0.3)

        assert len(result) == 0

    def test_no_stored_views(self, tmp_path: Path) -> None:
        """Videos without stored views are skipped."""
        summary = _make_summary("Test Video", "N/A")
        (tmp_path / "youtube - Test Video (vid1).md").write_text(summary)

        existing = [_make_existing_video("vid1", 1_000_000)]
        result = check_view_growth(existing, tmp_path, threshold=0.3)

        assert len(result) == 0

    def test_no_summary_file(self, tmp_path: Path) -> None:
        """Videos without summary files are skipped."""
        existing = [_make_existing_video("vid1", 1_000_000)]
        result = check_view_growth(existing, tmp_path, threshold=0.3)

        assert len(result) == 0

    def test_zero_stored_views(self, tmp_path: Path) -> None:
        """Videos with 0 stored views are skipped (avoid division by zero)."""
        summary = _make_summary("Test Video", "0")
        (tmp_path / "youtube - Test Video (vid1).md").write_text(summary)

        existing = [_make_existing_video("vid1", 1_000_000)]
        result = check_view_growth(existing, tmp_path, threshold=0.3)

        assert len(result) == 0

    def test_multiple_videos(self, tmp_path: Path) -> None:
        """Mixed: one with growth, one without."""
        s1 = _make_summary("Growing", "100K")
        s2 = _make_summary("Stable", "1M")
        (tmp_path / "youtube - Growing (vid1).md").write_text(s1)
        (tmp_path / "youtube - Stable (vid2).md").write_text(s2)

        existing = [
            _make_existing_video("vid1", 200_000),  # 100% growth
            _make_existing_video("vid2", 1_050_000),  # 5% growth
        ]
        result = check_view_growth(existing, tmp_path, threshold=0.3)

        assert len(result) == 1
        assert result[0]["video_id"] == "vid1"

    def test_result_fields(self, tmp_path: Path) -> None:
        """Result dict has all required fields."""
        summary = _make_summary("Test", "500K")
        (tmp_path / "youtube - Test (vid1).md").write_text(summary)

        existing = [_make_existing_video("vid1", 1_000_000)]
        result = check_view_growth(existing, tmp_path, threshold=0.3)

        assert len(result) == 1
        r = result[0]
        assert "video_id" in r
        assert "title" in r
        assert "stored_views" in r
        assert "current_views" in r
        assert "growth_pct" in r
        assert "has_growth" in r

    def test_custom_threshold(self, tmp_path: Path) -> None:
        """Custom threshold works correctly."""
        summary = _make_summary("Test", "1M")
        (tmp_path / "youtube - Test (vid1).md").write_text(summary)

        # 15% growth — below 0.3 default but above 0.1
        existing = [_make_existing_video("vid1", 1_150_000)]

        result_default = check_view_growth(existing, tmp_path, threshold=0.3)
        assert len(result_default) == 0

        result_low = check_view_growth(existing, tmp_path, threshold=0.1)
        assert len(result_low) == 1

    def test_date_prefixed_summary_filename_supported(self, tmp_path: Path) -> None:
        """Date-prefixed summary filenames are found and analyzed."""
        summary = _make_summary("Test Video", "1M")
        (tmp_path / "2026-02-05 - youtube - Test Video (dQw4w9WgXcQ).md").write_text(summary)

        existing = [_make_existing_video("dQw4w9WgXcQ", 1_500_000)]
        result = check_view_growth(existing, tmp_path, threshold=0.3)

        assert len(result) == 1
        assert result[0]["video_id"] == "dQw4w9WgXcQ"

    def test_exact_threshold_not_included_with_compact_stored_views(self, tmp_path: Path) -> None:
        """Exact threshold (30.0%) is excluded even with compact stored count format."""
        summary = _make_summary("Test Video", "1.5M")
        (tmp_path / "youtube - Test Video (dQw4w9WgXcQ).md").write_text(summary)

        # Stored: 1,500,000. Current: 1,950,000 -> exactly 30% growth.
        existing = [_make_existing_video("dQw4w9WgXcQ", 1_950_000)]
        result = check_view_growth(existing, tmp_path, threshold=0.3)

        assert result == []

    def test_comma_formatted_stored_views_parsed_correctly(self, tmp_path: Path) -> None:
        """Stored views in comma format are parsed and compared correctly."""
        summary = _make_summary("Test Video", "2,183,167")
        (tmp_path / "youtube - Test Video (dQw4w9WgXcQ).md").write_text(summary)

        existing = [_make_existing_video("dQw4w9WgXcQ", 3_000_000)]
        result = check_view_growth(existing, tmp_path, threshold=0.3)

        assert len(result) == 1
        assert result[0]["video_id"] == "dQw4w9WgXcQ"
