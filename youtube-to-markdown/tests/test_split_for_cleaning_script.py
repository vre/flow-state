"""Tests for scripts/33_split_for_cleaning.py."""

import importlib.util
import json
from pathlib import Path
from typing import Any

SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "33_split_for_cleaning.py"


def _load_module() -> Any:
    """Load split script as an importable module."""
    assert SCRIPT_PATH.exists(), f"Missing script: {SCRIPT_PATH}"
    spec = importlib.util.spec_from_file_location("split_for_cleaning_script", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _build_transcript(paragraph_count: int, body_chars: int) -> str:
    """Build markdown transcript content with explicit paragraph boundaries.

    Args:
        paragraph_count: Number of paragraphs to generate.
        body_chars: Payload length for each paragraph.

    Returns:
        Transcript text where paragraphs are separated by blank lines.
    """
    paragraphs: list[str] = []
    for idx in range(1, paragraph_count + 1):
        payload = "x" * body_chars
        paragraphs.append(f"Paragraph {idx} {payload} [{idx // 60:02d}:{idx % 60:02d}]")
    return "\n\n".join(paragraphs)


def _run_script(module: Any, input_path: Path, output_dir: Path, monkeypatch, capsys) -> dict[str, list[str]]:
    """Run split script and parse its JSON stdout."""
    monkeypatch.setattr(
        module.sys,
        "argv",
        ["33_split_for_cleaning.py", str(input_path), str(output_dir)],
    )
    module.main()
    captured = capsys.readouterr()
    assert captured.err == ""
    parsed = json.loads(captured.out)
    assert isinstance(parsed, dict)
    assert "chunks" in parsed
    assert isinstance(parsed["chunks"], list)
    return parsed


def test_small_file_passthrough(tmp_path: Path, monkeypatch, capsys) -> None:
    """Files <= 80 KB should return original absolute path without writing chunks."""
    module = _load_module()
    input_path = tmp_path / "sample_transcript_paragraphs.md"
    input_path.write_text(_build_transcript(paragraph_count=5, body_chars=80))
    assert input_path.stat().st_size <= 80 * 1024

    result = _run_script(module, input_path, tmp_path, monkeypatch, capsys)

    assert result["chunks"] == [str(input_path.resolve())]
    assert list(tmp_path.glob("*_chunk_*.md")) == []


def test_large_file_splits_into_chunk_files(tmp_path: Path, monkeypatch, capsys) -> None:
    """Files > 80 KB should split into numbered chunk files with absolute paths."""
    module = _load_module()
    input_path = tmp_path / "episode_transcript_paragraphs.md"
    input_path.write_text(_build_transcript(paragraph_count=120, body_chars=900))
    assert input_path.stat().st_size > 80 * 1024

    result = _run_script(module, input_path, tmp_path, monkeypatch, capsys)
    chunk_paths = [Path(path) for path in result["chunks"]]

    assert len(chunk_paths) > 1
    assert all(path.is_absolute() for path in chunk_paths)
    assert all(path.exists() for path in chunk_paths)
    assert chunk_paths[0].name == "episode_chunk_001.md"
    assert chunk_paths[-1].name.startswith("episode_chunk_")

    paragraph_counts = [len(path.read_text().split("\n\n")) for path in chunk_paths]
    assert all(count <= 20 for count in paragraph_counts)


def test_split_preserves_paragraph_boundaries(tmp_path: Path, monkeypatch, capsys) -> None:
    """Recombining chunk files should reproduce the original paragraph sequence."""
    module = _load_module()
    input_path = tmp_path / "boundary_transcript_paragraphs.md"
    original = _build_transcript(paragraph_count=130, body_chars=850)
    input_path.write_text(original)
    assert input_path.stat().st_size > 80 * 1024

    result = _run_script(module, input_path, tmp_path, monkeypatch, capsys)
    chunk_paths = [Path(path) for path in result["chunks"]]

    reconstructed = "\n\n".join(path.read_text() for path in chunk_paths)
    assert reconstructed == original


def test_chunk_size_cap_respected(tmp_path: Path, monkeypatch, capsys) -> None:
    """Generated chunk files stay below 40 KB when paragraphs are reasonably sized."""
    module = _load_module()
    input_path = tmp_path / "sizecap_transcript_paragraphs.md"
    input_path.write_text(_build_transcript(paragraph_count=60, body_chars=2200))
    assert input_path.stat().st_size > 80 * 1024

    result = _run_script(module, input_path, tmp_path, monkeypatch, capsys)
    chunk_paths = [Path(path) for path in result["chunks"]]

    assert len(chunk_paths) > 1
    assert all(path.stat().st_size <= 40 * 1024 for path in chunk_paths)
