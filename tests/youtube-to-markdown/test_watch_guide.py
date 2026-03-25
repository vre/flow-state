"""Tests for watch guide and transcript fallback behavior."""

from pathlib import Path

import pytest
from lib.assembler import Finalizer
from lib.check_existing import find_existing_files
from lib.intermediate_files import get_all_work_files, get_transcript_work_files
from lib.prepare_update import VideoUnavailableError, prepare_update


def _write_templates(template_dir: Path) -> None:
    """Create minimal templates used by Finalizer methods."""
    template_dir.mkdir(parents=True, exist_ok=True)
    (template_dir / "transcript.md").write_text("## Description\n\n{description}\n\n## Transcription\n\n{transcription}\n")
    (template_dir / "watch_guide.md").write_text("## Watch Guide\n\n{watch_guide}\n")


def test_watch_guide_work_files_are_transcript_specific() -> None:
    """Transcript cleanup includes watch guide marker and intermediate watch guide files."""
    base_name = "youtube_vid"
    transcript_files = get_transcript_work_files(base_name)
    assert f"{base_name}_watch_guide.md" in transcript_files
    assert f"{base_name}_watch_guide_requested.flag" in transcript_files
    assert f"{base_name}_watch_guide.md" in get_all_work_files(base_name)


@pytest.mark.parametrize(
    ("polished", "dedup", "legacy", "expected"),
    [
        ("Polished", "Dedup", "Legacy", "Polished"),
        ("", "Dedup", "Legacy", "Dedup"),
        ("", "", "Legacy", "Legacy"),
    ],
)
def test_assemble_transcript_content_fallback_chain(
    tmp_path: Path,
    polished: str,
    dedup: str,
    legacy: str,
    expected: str,
) -> None:
    """assemble_transcript_content falls back polished -> dedup -> legacy."""
    finalizer = Finalizer()
    base_name = "youtube_vid"

    (tmp_path / f"{base_name}_description.md").write_text("Desc")
    (tmp_path / f"{base_name}_transcript.md").write_text(polished)
    (tmp_path / f"{base_name}_transcript_dedup.md").write_text(dedup)
    (tmp_path / f"{base_name}_transcript_no_timestamps.txt").write_text(legacy)

    out = finalizer.assemble_transcript_content(
        "{description}\n{transcription}",
        base_name,
        tmp_path,
    )
    assert out == f"Desc\n{expected}"


def test_find_existing_summary_excludes_watch_guide_file(tmp_path: Path) -> None:
    """find_existing_summary should ignore transcript/comments/watch guide suffix files."""
    finalizer = Finalizer()
    video_id = "abc123"

    summary = tmp_path / f"Main ({video_id}).md"
    watch_guide = tmp_path / f"Main - watch guide ({video_id}).md"
    transcript = tmp_path / f"Main - transcript ({video_id}).md"
    comments = tmp_path / f"Main - comments ({video_id}).md"

    for p in [watch_guide, transcript, comments, summary]:
        p.write_text("x")

    found = finalizer.find_existing_summary(video_id, tmp_path)
    assert found == summary


def test_save_raw_transcript_prefers_dedup_file(tmp_path: Path) -> None:
    """_save_raw_transcript stores dedup transcript when available."""
    finalizer = Finalizer()
    base_name = "youtube_vid"
    template_dir = tmp_path / "templates"
    _write_templates(template_dir)

    (tmp_path / f"{base_name}_description.md").write_text("Desc")
    (tmp_path / f"{base_name}_transcript_dedup.md").write_text("[00:00:01.000] Dedup")
    (tmp_path / f"{base_name}_transcript_no_timestamps.txt").write_text("Legacy")

    path = finalizer._save_raw_transcript(
        base_name,
        tmp_path,
        template_dir,
        cleaned_title="Title",
        video_id="vid",
        upload_date="2026-02-25",
    )

    assert path is not None
    assert path.name == "2026-02-25 - Title - transcript (vid).md"
    assert "[00:00:01.000] Dedup" in path.read_text()


def test_save_watch_guide_creates_file_and_links_first_duplicate(
    tmp_path: Path,
) -> None:
    """Non-empty plain markdown watch guide is saved to final output file."""
    finalizer = Finalizer()
    base_name = "youtube_vid"
    template_dir = tmp_path / "templates"
    _write_templates(template_dir)

    watch_guide_content = "## Watch Route\n\n- [00:12](https://www.youtube.com/watch?v=vid&t=12s) Start here"
    (tmp_path / f"{base_name}_watch_guide.md").write_text(watch_guide_content)

    out = finalizer._save_watch_guide(
        base_name=base_name,
        output_dir=tmp_path,
        template_dir=template_dir,
        cleaned_title="Title",
        video_id="vid",
        upload_date="2026-02-25",
    )

    assert out is not None
    content = out.read_text()
    assert watch_guide_content in content


def test_finalize_transcript_only_calls_save_watch_guide(monkeypatch, tmp_path: Path) -> None:
    """finalize_transcript_only invokes _save_watch_guide."""
    finalizer = Finalizer()
    base_name = "youtube_vid"
    template_dir = tmp_path / "templates"
    _write_templates(template_dir)
    (template_dir / "transcript.md").write_text("{description}\n{transcription}")

    (tmp_path / f"{base_name}_title.txt").write_text("Title")
    (tmp_path / f"{base_name}_upload_date.txt").write_text("2026-02-25")
    (tmp_path / f"{base_name}_description.md").write_text("Desc")
    (tmp_path / f"{base_name}_transcript.md").write_text("Transcript body")

    captured: dict[str, bool] = {"called": False}

    def _fake_save_watch_guide(
        base_name: str,
        output_dir: Path,
        template_dir: Path,
        cleaned_title: str | None,
        video_id: str,
        upload_date: str | None,
    ) -> None:
        captured["called"] = True

    monkeypatch.setattr(finalizer, "_save_watch_guide", _fake_save_watch_guide)

    output_path = finalizer.finalize_transcript_only(base_name, tmp_path, template_dir, debug=True)

    assert output_path.name == "2026-02-25 - Title - transcript (vid).md"
    assert captured["called"]


def test_save_watch_guide_empty_file_skips_output(tmp_path: Path) -> None:
    """Empty watch guide file skips final file creation."""
    finalizer = Finalizer()
    base_name = "youtube_vid"
    template_dir = tmp_path / "templates"
    _write_templates(template_dir)

    (tmp_path / f"{base_name}_watch_guide.md").write_text("  \n\n")

    out = finalizer._save_watch_guide(
        base_name=base_name,
        output_dir=tmp_path,
        template_dir=template_dir,
        cleaned_title="Title",
        video_id="vid",
        upload_date="2026-02-25",
    )

    assert out is None
    assert not (tmp_path / "2026-02-25 - Title - watch guide (vid).md").exists()


def test_save_watch_guide_missing_file_skips_output(tmp_path: Path) -> None:
    """Missing watch guide file skips final file creation."""
    finalizer = Finalizer()
    base_name = "youtube_vid"
    template_dir = tmp_path / "templates"
    _write_templates(template_dir)

    out = finalizer._save_watch_guide(
        base_name=base_name,
        output_dir=tmp_path,
        template_dir=template_dir,
        cleaned_title="Title",
        video_id="vid",
        upload_date="2026-02-25",
    )

    assert out is None
    assert not (tmp_path / "2026-02-25 - Title - watch guide (vid).md").exists()


def test_find_existing_files_classifies_watch_guide(tmp_path: Path) -> None:
    """find_existing_files returns watch_guide_file separately."""
    video_id = "abc123"
    (tmp_path / f"Main ({video_id}).md").write_text("summary")
    (tmp_path / f"Main - transcript ({video_id}).md").write_text("transcript")
    (tmp_path / f"Main - comments ({video_id}).md").write_text("comments")
    watch = tmp_path / f"Main - watch guide ({video_id}).md"
    watch.write_text("watch")

    result = find_existing_files(video_id, tmp_path)

    assert result["watch_guide_file"] == str(watch)
    assert result["summary_file"].endswith(f"Main ({video_id}).md")


def test_finalize_full_injects_watch_links_into_transcript(tmp_path: Path) -> None:
    """finalize_full injects watch-guide video links under matching transcript headings."""
    finalizer = Finalizer()
    base_name = "youtube_vid"
    template_dir = tmp_path / "templates"
    template_dir.mkdir(parents=True, exist_ok=True)
    (template_dir / "summary.md").write_text("{quick_summary}\n{metadata}\n{summary}")
    (template_dir / "transcript.md").write_text("## Description\n\n{description}\n\n## Transcription\n\n{transcription}\n")
    (template_dir / "comments.md").write_text("{comments}")
    (template_dir / "watch_guide.md").write_text("{watch_guide}")

    (tmp_path / f"{base_name}_title.txt").write_text("Title")
    (tmp_path / f"{base_name}_upload_date.txt").write_text("2026-02-25")
    (tmp_path / f"{base_name}_quick_summary.md").write_text("Quick")
    (tmp_path / f"{base_name}_metadata.md").write_text("Meta")
    (tmp_path / f"{base_name}_summary_tight.md").write_text("Summary")
    (tmp_path / f"{base_name}_description.md").write_text("Desc")
    (tmp_path / f"{base_name}_transcript.md").write_text("### Topic One\n\nParagraph one.\n")
    (tmp_path / f"{base_name}_comments_prefiltered.md").write_text("Comments")
    (tmp_path / f"{base_name}_watch_guide.md").write_text(
        "WATCH: visual demo\n\n## Highlights\n\n- [00:12](https://www.youtube.com/watch?v=vid&t=12s) Start here\n→ Topic One\n"
    )

    _, transcript_path, _ = finalizer.finalize_full(base_name, tmp_path, template_dir, debug=True)

    transcript = transcript_path.read_text()
    assert "▶ [00:12](https://www.youtube.com/watch?v=vid&t=12s) Start here" in transcript


def test_prepare_update_includes_watch_guide_for_exists(monkeypatch, tmp_path: Path) -> None:
    """prepare_update includes watch_guide in existing_files for EXISTS path."""
    monkeypatch.setattr(
        "lib.prepare_update.check_existing",
        lambda video_url, output_dir: {
            "exists": True,
            "summary_file": "summary.md",
            "transcript_file": "transcript.md",
            "comment_file": "comments.md",
            "watch_guide_file": "watch.md",
            "stored_metadata": {"title": "T", "views": "1M", "likes": "1K", "comments": "100", "published": "2026-01-01"},
            "comments_state": "v2",
            "summary_issues": [],
            "summary_v1": False,
        },
    )
    monkeypatch.setattr(
        "lib.prepare_update.fetch_current_metadata",
        lambda video_url, output_dir: {"title": "T", "views": 1_000_000, "likes": 1_000, "comments": 100},
    )

    result = prepare_update("https://youtube.com/watch?v=abc123", tmp_path)

    assert result["status"] == "EXISTS"
    assert result["existing_files"]["watch_guide"] == "watch.md"


def test_prepare_update_includes_watch_guide_for_unavailable(monkeypatch, tmp_path: Path) -> None:
    """prepare_update includes watch_guide in existing_files for UNAVAILABLE path."""
    monkeypatch.setattr(
        "lib.prepare_update.check_existing",
        lambda video_url, output_dir: {
            "exists": True,
            "summary_file": "summary.md",
            "transcript_file": "transcript.md",
            "comment_file": "comments.md",
            "watch_guide_file": "watch.md",
            "stored_metadata": {"published": "2026-01-01"},
        },
    )

    def _raise(video_url: str, output_dir: Path) -> dict:
        raise VideoUnavailableError("Video unavailable")

    monkeypatch.setattr("lib.prepare_update.fetch_current_metadata", _raise)

    result = prepare_update("https://youtube.com/watch?v=abc123", tmp_path)

    assert result["status"] == "UNAVAILABLE"
    assert result["existing_files"]["watch_guide"] == "watch.md"


def test_cleanup_analysis_files_removes_only_chunk_analysis_files(tmp_path: Path) -> None:
    """cleanup_analysis_files removes chunk analysis files and preserves other files."""
    finalizer = Finalizer()
    base_name = "youtube_vid"

    removable_a = tmp_path / f"{base_name}_chunk_001_analysis.md"
    removable_b = tmp_path / f"{base_name}_chunk_002_analysis.md"
    keep_single = tmp_path / f"{base_name}_analysis.md"
    keep_other = tmp_path / f"{base_name}_chunk_001_cleaned.md"

    removable_a.write_text("a")
    removable_b.write_text("b")
    keep_single.write_text("single")
    keep_other.write_text("cleaned")

    finalizer.cleanup_analysis_files(base_name, tmp_path)

    assert not removable_a.exists()
    assert not removable_b.exists()
    assert keep_single.exists()
    assert keep_other.exists()
