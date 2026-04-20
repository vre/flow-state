"""Tests for heatmap extraction in YouTubeDataExtractor."""

import json
from pathlib import Path
from unittest.mock import MagicMock

from lib.youtube_extractor import YouTubeDataExtractor


def _make_extractor(written_files: dict | None = None) -> YouTubeDataExtractor:
    """Create extractor with mock filesystem."""
    fs = MagicMock()
    if written_files is not None:
        fs.write_text.side_effect = lambda path, content: written_files.update({str(path): content})
    return YouTubeDataExtractor(fs=fs, cmd=MagicMock())


class TestCreateHeatmapFile:
    def test_writes_heatmap_json(self, tmp_path: Path) -> None:
        written: dict = {}
        extractor = _make_extractor(written)
        raw_data = {
            "heatmap": [
                {"start_time": 0.0, "end_time": 5.0, "value": 0.3},
                {"start_time": 5.0, "end_time": 10.0, "value": 0.8},
            ]
        }

        result = extractor.create_heatmap_file(raw_data, "youtube_abc123", tmp_path)

        assert result == tmp_path / "youtube_abc123_heatmap.json"
        content = json.loads(written[str(result)])
        assert len(content) == 2
        assert content[1]["value"] == 0.8

    def test_returns_none_when_no_heatmap(self, tmp_path: Path) -> None:
        extractor = _make_extractor()
        assert extractor.create_heatmap_file({}, "youtube_abc123", tmp_path) is None

    def test_returns_none_for_empty_heatmap(self, tmp_path: Path) -> None:
        extractor = _make_extractor()
        assert extractor.create_heatmap_file({"heatmap": []}, "youtube_abc123", tmp_path) is None

    def test_returns_none_for_none_heatmap(self, tmp_path: Path) -> None:
        extractor = _make_extractor()
        assert extractor.create_heatmap_file({"heatmap": None}, "youtube_abc123", tmp_path) is None
