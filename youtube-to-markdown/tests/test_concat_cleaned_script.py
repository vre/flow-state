"""Tests for scripts/34_concat_cleaned.py."""

import importlib.util
from pathlib import Path
from typing import Any

SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "34_concat_cleaned.py"


def _load_module() -> Any:
    """Load concat script as an importable module."""
    assert SCRIPT_PATH.exists(), f"Missing script: {SCRIPT_PATH}"
    spec = importlib.util.spec_from_file_location("concat_cleaned_script", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_script(module: Any, args: list[Path], monkeypatch) -> None:
    """Execute concat script with provided argv paths."""
    monkeypatch.setattr(
        module.sys,
        "argv",
        ["34_concat_cleaned.py", *[str(path) for path in args]],
    )
    module.main()


def test_single_chunk_passthrough_and_cleanup(tmp_path: Path, monkeypatch) -> None:
    """Single chunk input should write equivalent output and clean chunk artifacts."""
    module = _load_module()
    chunk_cleaned = tmp_path / "episode_chunk_001_cleaned.md"
    chunk_raw = tmp_path / "episode_chunk_001.md"
    output_path = tmp_path / "episode_transcript_cleaned.md"

    chunk_cleaned.write_text("Paragraph A [00:00]\n\nParagraph B [00:30]\n")
    chunk_raw.write_text("Raw chunk input")

    _run_script(module, [chunk_cleaned, output_path], monkeypatch)

    assert output_path.read_text() == "Paragraph A [00:00]\n\nParagraph B [00:30]"
    assert not chunk_cleaned.exists()
    assert not chunk_raw.exists()


def test_multiple_chunks_concatenate_without_duplicate_newlines(tmp_path: Path, monkeypatch) -> None:
    """Chunk boundaries should be joined with exactly one blank line separator."""
    module = _load_module()
    chunk1_cleaned = tmp_path / "episode_chunk_001_cleaned.md"
    chunk2_cleaned = tmp_path / "episode_chunk_002_cleaned.md"
    output_path = tmp_path / "episode_transcript_cleaned.md"

    (tmp_path / "episode_chunk_001.md").write_text("Original 1")
    (tmp_path / "episode_chunk_002.md").write_text("Original 2")
    chunk1_cleaned.write_text("Paragraph A [00:00]\n\nParagraph B [00:30]\n\n")
    chunk2_cleaned.write_text("\n\nParagraph C [01:00]\n\nParagraph D [01:30]")

    _run_script(module, [chunk1_cleaned, chunk2_cleaned, output_path], monkeypatch)

    expected = "Paragraph A [00:00]\n\nParagraph B [00:30]\n\nParagraph C [01:00]\n\nParagraph D [01:30]"
    content = output_path.read_text()
    assert content == expected
    assert "\n\n\n" not in content


def test_cleanup_handles_missing_counterpart(tmp_path: Path, monkeypatch) -> None:
    """Cleanup should delete existing chunk artifacts and ignore missing counterparts."""
    module = _load_module()
    chunk1_cleaned = tmp_path / "episode_chunk_001_cleaned.md"
    chunk2_cleaned = tmp_path / "episode_chunk_002_cleaned.md"
    output_path = tmp_path / "episode_transcript_cleaned.md"

    chunk1_cleaned.write_text("Paragraph 1 [00:00]")
    chunk2_cleaned.write_text("Paragraph 2 [00:30]")
    (tmp_path / "episode_chunk_001.md").write_text("Original 1")
    # episode_chunk_002.md intentionally absent

    _run_script(module, [chunk1_cleaned, chunk2_cleaned, output_path], monkeypatch)

    assert output_path.exists()
    assert not chunk1_cleaned.exists()
    assert not chunk2_cleaned.exists()
    assert not (tmp_path / "episode_chunk_001.md").exists()
