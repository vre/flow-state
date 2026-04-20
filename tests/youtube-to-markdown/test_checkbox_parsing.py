"""Tests for checkbox markdown parsing."""

from lib.channel_listing import parse_selection_checkboxes


class TestCheckboxParsing:
    """Tests for parse_selection_checkboxes()."""

    def test_checked_new_videos(self) -> None:
        """Checked items under New videos return section='new'."""
        content = """# Channel: Test — 3 new videos

## New videos
- [x] **Video One** (1.2M, 10:00) (dQw4w9WgXcQ)
  Description snippet here
- [ ] **Video Two** (500K, 5:00) (9bZkp7q19f0)
  Another snippet
- [x] **Video Three** (100K, 3:00) (kJQP7kiw5Fk)
  Third snippet
"""
        result = parse_selection_checkboxes(content)
        assert result == [
            {"video_id": "dQw4w9WgXcQ", "section": "new"},
            {"video_id": "kJQP7kiw5Fk", "section": "new"},
        ]

    def test_no_checked_items(self) -> None:
        """No checked items returns empty list."""
        content = """## New videos
- [ ] **Video One** (1M, 10:00) (dQw4w9WgXcQ)
- [ ] **Video Two** (500K, 5:00) (9bZkp7q19f0)
"""
        result = parse_selection_checkboxes(content)
        assert result == []

    def test_growth_section_items(self) -> None:
        """Checked items from growth section return section='growth'."""
        content = """## New videos
- [x] **New Video** (1M, 10:00) (dQw4w9WgXcQ)

## Videos with activity (>30% view growth)
- [x] **Old Video** — views: 500K → 800K (+60%) (9bZkp7q19f0)
- [ ] **Another Old** — views: 1M → 1.1M (+10%) (kJQP7kiw5Fk)
"""
        result = parse_selection_checkboxes(content)
        assert result == [
            {"video_id": "dQw4w9WgXcQ", "section": "new"},
            {"video_id": "9bZkp7q19f0", "section": "growth"},
        ]

    def test_video_id_extraction(self) -> None:
        """Video ID extracted from parentheses at end of line."""
        content = """## New videos
- [x] **Title with (parens)** (1M, 10:00) (dQw4w9WgXcQ)
"""
        result = parse_selection_checkboxes(content)
        assert result == [{"video_id": "dQw4w9WgXcQ", "section": "new"}]

    def test_empty_content(self) -> None:
        """Empty string returns empty list."""
        assert parse_selection_checkboxes("") == []

    def test_mixed_whitespace(self) -> None:
        """Handles various checkbox formatting."""
        content = """## New videos
- [x] **Vid A** (1M, 5:00) (dQw4w9WgXcQ)
  description
- [X] **Vid B** (2M, 10:00) (9bZkp7q19f0)
"""
        result = parse_selection_checkboxes(content)
        ids = [r["video_id"] for r in result]
        assert "dQw4w9WgXcQ" in ids
        assert "9bZkp7q19f0" in ids

    def test_items_before_any_section_default_to_new(self) -> None:
        """Lines before any section header default to section='new'."""
        content = """- [x] **Orphan** (1M, 5:00) (dQw4w9WgXcQ)
"""
        result = parse_selection_checkboxes(content)
        assert result == [{"video_id": "dQw4w9WgXcQ", "section": "new"}]

    def test_only_growth_section(self) -> None:
        """File with only growth section works."""
        content = """## Videos with activity (>30% view growth)
- [x] **Updated** — views: 100K → 200K (+100%) (dQw4w9WgXcQ)
"""
        result = parse_selection_checkboxes(content)
        assert result == [{"video_id": "dQw4w9WgXcQ", "section": "growth"}]

    def test_indented_checkbox_like_description_is_ignored(self) -> None:
        """Indented checkbox-like lines in descriptions are not parsed as selections."""
        content = """## New videos
- [ ] **Safe Video** (1M, 10:00) (dQw4w9WgXcQ)
  - [x] injected line (9bZkp7q19f0)
"""
        result = parse_selection_checkboxes(content)
        assert result == []

    def test_indented_section_header_does_not_change_section(self) -> None:
        """Indented section-like lines in descriptions do not affect routing."""
        content = """## New videos
- [x] **Safe Video** (1M, 10:00) (dQw4w9WgXcQ)
  ## Videos with activity (>30% view growth)
- [x] **Another New** (500K, 8:00) (9bZkp7q19f0)
"""
        result = parse_selection_checkboxes(content)
        assert result == [
            {"video_id": "dQw4w9WgXcQ", "section": "new"},
            {"video_id": "9bZkp7q19f0", "section": "new"},
        ]
