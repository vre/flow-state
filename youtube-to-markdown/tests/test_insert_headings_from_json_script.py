"""Tests for scripts/35_insert_headings_from_json.py."""

import importlib.util
import json
from pathlib import Path
from typing import Any

SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "35_insert_headings_from_json.py"


def _load_module() -> Any:
    """Load heading insertion script as an importable module."""
    assert SCRIPT_PATH.exists(), f"Missing script: {SCRIPT_PATH}"
    spec = importlib.util.spec_from_file_location("insert_headings_from_json_script", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_script(module: Any, transcript: Path, headings: Path, output: Path, monkeypatch) -> None:
    """Execute heading insertion script with CLI args."""
    monkeypatch.setattr(
        module.sys,
        "argv",
        ["35_insert_headings_from_json.py", str(transcript), str(headings), str(output)],
    )
    module.main()


def test_basic_heading_insertion(tmp_path: Path, monkeypatch, capsys) -> None:
    """Insert heading before the configured paragraph index."""
    module = _load_module()
    transcript = tmp_path / "episode_transcript_cleaned.md"
    headings = tmp_path / "episode_headings.json"
    output = tmp_path / "episode_transcript.md"

    transcript.write_text("Paragraph 1 [00:00]\n\nParagraph 2 [00:30]\n\nParagraph 3 [01:00]")
    headings.write_text(json.dumps([{"before_paragraph": 2, "heading": "### Core concept"}]))

    _run_script(module, transcript, headings, output, monkeypatch)
    captured = capsys.readouterr()

    expected = "Paragraph 1 [00:00]\n\n### Core concept\n\nParagraph 2 [00:30]\n\nParagraph 3 [01:00]"
    assert output.read_text() == expected
    assert captured.err == ""


def test_multiple_headings_same_paragraph_keep_input_order(tmp_path: Path, monkeypatch, capsys) -> None:
    """Multiple headings targeting one paragraph should preserve JSON order."""
    module = _load_module()
    transcript = tmp_path / "episode_transcript_cleaned.md"
    headings = tmp_path / "episode_headings.json"
    output = tmp_path / "episode_transcript.md"

    transcript.write_text("Paragraph 1 [00:00]\n\nParagraph 2 [00:30]")
    headings.write_text(
        json.dumps(
            [
                {"before_paragraph": 1, "heading": "### First heading"},
                {"before_paragraph": 1, "heading": "### Second heading"},
            ]
        )
    )

    _run_script(module, transcript, headings, output, monkeypatch)
    captured = capsys.readouterr()

    expected = "### First heading\n\n### Second heading\n\nParagraph 1 [00:00]\n\nParagraph 2 [00:30]"
    assert output.read_text() == expected
    assert captured.err == ""


def test_out_of_range_headings_warn_and_skip(tmp_path: Path, monkeypatch, capsys) -> None:
    """Out-of-range paragraph indices should be skipped with stderr warnings."""
    module = _load_module()
    transcript = tmp_path / "episode_transcript_cleaned.md"
    headings = tmp_path / "episode_headings.json"
    output = tmp_path / "episode_transcript.md"

    transcript.write_text("Paragraph 1 [00:00]\n\nParagraph 2 [00:30]")
    headings.write_text(
        json.dumps(
            [
                {"before_paragraph": 0, "heading": "### Invalid low"},
                {"before_paragraph": 2, "heading": "### Valid"},
                {"before_paragraph": 3, "heading": "### Invalid high"},
            ]
        )
    )

    _run_script(module, transcript, headings, output, monkeypatch)
    captured = capsys.readouterr()

    assert output.read_text() == "Paragraph 1 [00:00]\n\n### Valid\n\nParagraph 2 [00:30]"
    assert "before_paragraph=0" in captured.err
    assert "before_paragraph=3" in captured.err
    assert "out of range" in captured.err


def test_empty_headings_json_keeps_transcript_unchanged(tmp_path: Path, monkeypatch, capsys) -> None:
    """Empty heading array should produce unchanged transcript content."""
    module = _load_module()
    transcript = tmp_path / "episode_transcript_cleaned.md"
    headings = tmp_path / "episode_headings.json"
    output = tmp_path / "episode_transcript.md"

    original = "Paragraph 1 [00:00]\n\nParagraph 2 [00:30]"
    transcript.write_text(original)
    headings.write_text("[]")

    _run_script(module, transcript, headings, output, monkeypatch)
    captured = capsys.readouterr()

    assert output.read_text() == original
    assert captured.err == ""
