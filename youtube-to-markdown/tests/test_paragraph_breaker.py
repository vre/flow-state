"""Regression tests for ParagraphBreaker timestamp link formatting."""

import importlib.util
from pathlib import Path
from typing import Any

import pytest

MODULE_PATH = Path(__file__).parent.parent / "lib" / "paragraph_breaker.py"


def _load_module() -> Any:
    spec = importlib.util.spec_from_file_location("paragraph_breaker", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def breaker_cls() -> type:
    """Load ParagraphBreaker class from lib module."""
    module = _load_module()
    return module.ParagraphBreaker


class TestConvertTimestampToLink:
    """Timestamp links must be standard markdown [text](url), always HH:MM:SS."""

    def test_hh_mm_ss_format(self, breaker_cls: type) -> None:
        pb = breaker_cls(video_id="abc123")
        result = pb.convert_timestamp_to_link("[01:23:45.000]")
        assert result == "[01:23:45](https://youtube.com/watch?v=abc123&t=5025s)"

    def test_mm_ss_gets_hh_prefix(self, breaker_cls: type) -> None:
        pb = breaker_cls(video_id="abc123")
        result = pb.convert_timestamp_to_link("[02:15.000]")
        assert result == "[00:02:15](https://youtube.com/watch?v=abc123&t=135s)"

    def test_zero_timestamp(self, breaker_cls: type) -> None:
        pb = breaker_cls(video_id="abc123")
        result = pb.convert_timestamp_to_link("[00:00:00.000]")
        assert result == "[00:00:00](https://youtube.com/watch?v=abc123&t=0s)"

    def test_no_double_brackets(self, breaker_cls: type) -> None:
        """Regression: [[timestamp]](url) broke Obsidian rendering."""
        pb = breaker_cls(video_id="abc123")
        result = pb.convert_timestamp_to_link("[00:05:30.000]")
        assert result.startswith("[00:")
        assert "[[" not in result

    def test_no_video_id_returns_raw(self, breaker_cls: type) -> None:
        pb = breaker_cls(video_id="")
        result = pb.convert_timestamp_to_link("[01:00:00.000]")
        assert result == "[01:00:00.000]"

    def test_invalid_format_returns_raw(self, breaker_cls: type) -> None:
        pb = breaker_cls(video_id="abc123")
        result = pb.convert_timestamp_to_link("not a timestamp")
        assert result == "not a timestamp"
