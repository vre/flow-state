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


@pytest.mark.parametrize(
    ("heading", "expected"),
    [
        ("What's Next?", "whats-next"),
        ("Too   many   spaces", "too-many-spaces"),
        ("", "section"),
    ],
)
def test_slugify_heading_edge_cases(heading: str, expected: str) -> None:
    """_slugify_heading handles punctuation, spacing, and empty headings."""
    assert Finalizer._slugify_heading(heading) == expected


def test_watch_guide_work_file_is_not_transcript_specific() -> None:
    """Watch guide intermediate file belongs to all-work cleanup, not transcript-only cleanup."""
    base_name = "youtube_vid"
    assert f"{base_name}_watch_guide.md" not in get_transcript_work_files(base_name)
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

    summary = tmp_path / f"youtube - Main ({video_id}).md"
    watch_guide = tmp_path / f"youtube - Main - watch guide ({video_id}).md"
    transcript = tmp_path / f"youtube - Main - transcript ({video_id}).md"
    comments = tmp_path / f"youtube - Main - comments ({video_id}).md"

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
    assert path.name == "2026-02-25 - youtube - Title - transcript (vid).md"
    assert "[00:00:01.000] Dedup" in path.read_text()


@pytest.mark.parametrize(
    "verdict_line",
    [
        "WATCH: visual content",
        "SKIM: partial visual content",
    ],
)
def test_save_watch_guide_creates_file_and_links_first_duplicate(
    tmp_path: Path,
    verdict_line: str,
) -> None:
    """WATCH/SKIM verdicts create file and link first matching duplicate heading."""
    finalizer = Finalizer()
    base_name = "youtube_vid"
    template_dir = tmp_path / "templates"
    _write_templates(template_dir)

    transcript_filename = "2026-02-25 - youtube - Title - transcript (vid).md"
    transcript_path = tmp_path / transcript_filename
    transcript_path.write_text("## Transcription\n\n### Intro\n\n### Repeat\n\n### Repeat\n\n")

    (tmp_path / f"{base_name}_watch_guide.md").write_text(f"{verdict_line}\n\nFocus section\n→ Repeat\nTypo section\n→ Repeet\n")

    out = finalizer._save_watch_guide(
        base_name=base_name,
        output_dir=tmp_path,
        template_dir=template_dir,
        cleaned_title="Title",
        video_id="vid",
        upload_date="2026-02-25",
        transcript_filename=transcript_filename,
    )

    assert out is not None
    content = out.read_text()
    assert "Transcript: [Repeat](2026-02-25 - youtube - Title - transcript (vid).md#repeat)" in content
    # unresolved heading kept as plain text
    assert "→ Repeet" in content


def test_save_watch_guide_read_only_skips_file(tmp_path: Path) -> None:
    """READ-ONLY verdict skips watch guide file creation."""
    finalizer = Finalizer()
    base_name = "youtube_vid"
    template_dir = tmp_path / "templates"
    _write_templates(template_dir)

    (tmp_path / f"{base_name}_watch_guide.md").write_text("READ-ONLY: summary sufficient\n")

    out = finalizer._save_watch_guide(
        base_name=base_name,
        output_dir=tmp_path,
        template_dir=template_dir,
        cleaned_title="Title",
        video_id="vid",
        upload_date="2026-02-25",
        transcript_filename="2026-02-25 - youtube - Title - transcript (vid).md",
    )

    assert out is None
    assert not (tmp_path / "2026-02-25 - youtube - Title - watch guide (vid).md").exists()


def test_save_watch_guide_unparseable_verdict_skips_file(tmp_path: Path) -> None:
    """Unparseable first line is treated as READ-ONLY and skipped."""
    finalizer = Finalizer()
    base_name = "youtube_vid"
    template_dir = tmp_path / "templates"
    _write_templates(template_dir)

    (tmp_path / f"{base_name}_watch_guide.md").write_text("MAYBE: undecided\n")

    out = finalizer._save_watch_guide(
        base_name=base_name,
        output_dir=tmp_path,
        template_dir=template_dir,
        cleaned_title="Title",
        video_id="vid",
        upload_date="2026-02-25",
        transcript_filename="2026-02-25 - youtube - Title - transcript (vid).md",
    )

    assert out is None
    assert not (tmp_path / "2026-02-25 - youtube - Title - watch guide (vid).md").exists()


def test_find_existing_files_classifies_watch_guide(tmp_path: Path) -> None:
    """find_existing_files returns watch_guide_file separately."""
    video_id = "abc123"
    (tmp_path / f"youtube - Main ({video_id}).md").write_text("summary")
    (tmp_path / f"youtube - Main - transcript ({video_id}).md").write_text("transcript")
    (tmp_path / f"youtube - Main - comments ({video_id}).md").write_text("comments")
    watch = tmp_path / f"youtube - Main - watch guide ({video_id}).md"
    watch.write_text("watch")

    result = find_existing_files(video_id, tmp_path)

    assert result["watch_guide_file"] == str(watch)
    assert result["summary_file"].endswith(f"youtube - Main ({video_id}).md")


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
