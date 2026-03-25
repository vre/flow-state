"""Tests for deterministic transcript paragraph break planning."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from lib.paragraph_breaker import ParagraphBreaker
from lib.paragraph_breaks import ParagraphBreakPlanner
from lib.shared_types import FileOperationError


def _build_line(timestamp: str, label: str, filler_length: int = 88) -> str:
    """Create one timestamped transcript line ending with sentence punctuation."""
    filler = "x" * filler_length
    return f"[{timestamp}] {label} {filler}."


class TestParagraphBreakPlanner:
    """Deterministic paragraph break planning behavior."""

    def test_exact_chapter_boundary_starts_new_paragraph(self, mock_fs) -> None:
        """Exact chapter timestamps should start a new paragraph on that cue."""
        planner = ParagraphBreakPlanner(fs=mock_fs)
        formatter = ParagraphBreaker(fs=mock_fs)
        transcript_path = Path("/input.md")
        chapters_path = Path("/chapters.json")
        output_path = Path("/output.md")

        transcript = "\n".join(
            [
                _build_line("00:00:00.000", "Intro one"),
                _build_line("00:00:05.000", "Intro two"),
                _build_line("00:00:10.000", "Intro three"),
                _build_line("00:00:15.000", "Intro four"),
                _build_line("00:00:20.000", "Main chapter starts"),
                _build_line("00:00:25.000", "Main chapter continues"),
            ]
        )
        chapters = [
            {"start_time": 0, "end_time": 20, "title": "Intro"},
            {"start_time": 20, "end_time": 40, "title": "Main"},
        ]

        mock_fs.write_text(transcript_path, transcript)
        mock_fs.write_text(chapters_path, json.dumps(chapters))

        break_points = planner.compute_break_points(transcript_path, chapters_path)
        paragraph_count = formatter.apply_breaks(transcript_path, output_path, set(break_points))
        paragraphs = [part.strip() for part in mock_fs.read_text(output_path).split("\n\n") if part.strip()]

        assert break_points == [4, 6]
        assert paragraph_count == 2
        assert paragraphs[1].startswith("Main chapter starts")
        assert "[00:00:20.000]" in paragraphs[1]

    def test_non_exact_chapter_boundary_uses_first_following_line(self, mock_fs) -> None:
        """Non-exact chapter start should map to the next transcript cue."""
        planner = ParagraphBreakPlanner(fs=mock_fs)
        transcript_path = Path("/input.md")
        chapters_path = Path("/chapters.json")

        transcript = "\n".join(
            [
                _build_line("00:00:00.000", "Intro one"),
                _build_line("00:00:05.000", "Intro two"),
                _build_line("00:00:10.000", "Intro three"),
                _build_line("00:00:15.000", "Intro four"),
                _build_line("00:00:20.000", "Bridge"),
                _build_line("00:00:25.000", "Chapter two starts"),
            ]
        )
        chapters = [
            {"start_time": 0, "end_time": 21, "title": "Intro"},
            {"start_time": 21, "end_time": 40, "title": "Main"},
        ]

        mock_fs.write_text(transcript_path, transcript)
        mock_fs.write_text(chapters_path, json.dumps(chapters))

        assert planner.compute_break_points(transcript_path, chapters_path) == [5, 6]

    def test_without_chapters_uses_sentence_endings_near_target(self, mock_fs) -> None:
        """Missing chapters file should fall back to sentence-end breaks near target size."""
        planner = ParagraphBreakPlanner(fs=mock_fs)
        transcript_path = Path("/input.md")

        transcript = "\n".join(
            [
                _build_line("00:00:00.000", "Sentence 1"),
                _build_line("00:00:05.000", "Sentence 2"),
                _build_line("00:00:10.000", "Sentence 3"),
                _build_line("00:00:15.000", "Sentence 4"),
                _build_line("00:00:20.000", "Sentence 5"),
                _build_line("00:00:25.000", "Sentence 6"),
                _build_line("00:00:30.000", "Sentence 7"),
                _build_line("00:00:35.000", "Sentence 8"),
            ]
        )
        mock_fs.write_text(transcript_path, transcript)

        assert planner.compute_break_points(transcript_path, Path("/missing.json")) == [5, 8]

    def test_empty_chapters_file_uses_sentence_endings_near_target(self, mock_fs) -> None:
        """Empty chapter arrays should behave like missing chapter metadata."""
        planner = ParagraphBreakPlanner(fs=mock_fs)
        transcript_path = Path("/input.md")
        chapters_path = Path("/chapters.json")

        transcript = "\n".join(
            [
                _build_line("00:00:00.000", "Sentence 1"),
                _build_line("00:00:05.000", "Sentence 2"),
                _build_line("00:00:10.000", "Sentence 3"),
                _build_line("00:00:15.000", "Sentence 4"),
                _build_line("00:00:20.000", "Sentence 5"),
                _build_line("00:00:25.000", "Sentence 6"),
                _build_line("00:00:30.000", "Sentence 7"),
                _build_line("00:00:35.000", "Sentence 8"),
            ]
        )
        mock_fs.write_text(transcript_path, transcript)
        mock_fs.write_text(chapters_path, "[]")

        assert planner.compute_break_points(transcript_path, chapters_path) == [5, 8]

    def test_short_transcript_returns_final_line_only(self, mock_fs) -> None:
        """Short transcripts should remain one paragraph."""
        planner = ParagraphBreakPlanner(fs=mock_fs)
        transcript_path = Path("/input.md")

        transcript = "\n".join(
            [
                _build_line("00:00:00.000", "Short one", filler_length=20),
                _build_line("00:00:05.000", "Short two", filler_length=20),
            ]
        )
        mock_fs.write_text(transcript_path, transcript)

        assert planner.compute_break_points(transcript_path, None) == [2]

    def test_empty_input_raises_file_operation_error(self, mock_fs) -> None:
        """Empty transcript input should fail explicitly."""
        planner = ParagraphBreakPlanner(fs=mock_fs)
        transcript_path = Path("/input.md")
        mock_fs.write_text(transcript_path, "")

        with pytest.raises(FileOperationError, match="No transcript lines"):
            planner.compute_break_points(transcript_path, None)
