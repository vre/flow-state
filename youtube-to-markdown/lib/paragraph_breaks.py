"""Deterministic paragraph break planning for timestamped transcripts."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from lib.shared_types import FileOperationError, FileSystem, RealFileSystem

DEFAULT_TARGET_CHARS = 500
TIMESTAMP_RE = re.compile(r"^\[(?:(\d{2}):)?(\d{2}):(\d{2})\.(\d{3})\]\s?(.*)$")
SENTENCE_END_RE = re.compile(r".*[.?!][\"')\\]]*$")


@dataclass(frozen=True)
class TranscriptCue:
    """One transcript line with parsed timing metadata."""

    line_number: int
    timestamp_seconds: float | None
    text: str


class ParagraphBreakPlanner:
    """Plan paragraph break points for `31_format_transcript.py`."""

    def __init__(self, fs: FileSystem = RealFileSystem(), target_chars: int = DEFAULT_TARGET_CHARS):
        self.fs = fs
        self.target_chars = target_chars

    def compute_break_points(self, transcript_path: Path, chapters_path: Path | None) -> list[int]:
        """Compute sorted paragraph end line numbers for a transcript."""
        cues = self._load_transcript(transcript_path)
        chapter_starts = self._resolve_chapter_start_lines(cues, chapters_path)
        paragraph_starts = self._plan_paragraph_starts(cues, chapter_starts)
        return self._to_break_points(paragraph_starts, cues[-1].line_number)

    def _load_transcript(self, transcript_path: Path) -> list[TranscriptCue]:
        """Load timestamped transcript lines preserving source line numbering."""
        if not self.fs.exists(transcript_path):
            raise FileOperationError(f"{transcript_path} not found")

        content = self.fs.read_text(transcript_path)
        raw_lines = content.splitlines()
        if not raw_lines:
            raise FileOperationError(f"No transcript lines found in {transcript_path}")

        cues = [self._parse_transcript_line(index, line) for index, line in enumerate(raw_lines, start=1)]
        if not any(cue.text or cue.timestamp_seconds is not None for cue in cues):
            raise FileOperationError(f"No transcript lines found in {transcript_path}")
        return cues

    def _parse_transcript_line(self, line_number: int, line: str) -> TranscriptCue:
        """Parse one deduplicated transcript line."""
        match = TIMESTAMP_RE.match(line.strip())
        if not match:
            return TranscriptCue(line_number=line_number, timestamp_seconds=None, text=line.strip())

        hours_raw, minutes_raw, seconds_raw, millis_raw, text = match.groups()
        hours = int(hours_raw or 0)
        minutes = int(minutes_raw)
        seconds = int(seconds_raw)
        millis = int(millis_raw)
        total_seconds = hours * 3600 + minutes * 60 + seconds + millis / 1000
        return TranscriptCue(
            line_number=line_number,
            timestamp_seconds=total_seconds,
            text=text.strip(),
        )

    def _resolve_chapter_start_lines(self, cues: list[TranscriptCue], chapters_path: Path | None) -> list[int]:
        """Resolve chapter start times to transcript line numbers."""
        chapters = self._load_chapters(chapters_path)
        chapter_starts: set[int] = set()

        for chapter in chapters:
            matching_cue = next(
                (cue for cue in cues if cue.timestamp_seconds is not None and cue.timestamp_seconds >= chapter),
                None,
            )
            if matching_cue is None or matching_cue.line_number == 1:
                continue
            chapter_starts.add(matching_cue.line_number)

        return sorted(chapter_starts)

    def _load_chapters(self, chapters_path: Path | None) -> list[float]:
        """Load chapter start times from yt-dlp JSON output."""
        if chapters_path is None or not self.fs.exists(chapters_path):
            return []

        try:
            payload = json.loads(self.fs.read_text(chapters_path))
        except json.JSONDecodeError as exc:
            raise FileOperationError(f"Invalid chapter JSON in {chapters_path}: {exc}") from exc

        if not isinstance(payload, list):
            raise FileOperationError(f"Expected chapter list in {chapters_path}")

        starts: list[float] = []
        for entry in payload:
            if not isinstance(entry, dict):
                continue
            start_time = entry.get("start_time")
            if isinstance(start_time, int | float):
                starts.append(float(start_time))

        return sorted(set(starts))

    def _plan_paragraph_starts(self, cues: list[TranscriptCue], chapter_starts: list[int]) -> list[int]:
        """Plan paragraph starts, keeping chapter starts mandatory."""
        last_line = cues[-1].line_number
        mandatory_starts = [1, *chapter_starts]
        paragraph_starts: list[int] = [1]

        for index, segment_start in enumerate(mandatory_starts):
            segment_end = mandatory_starts[index + 1] - 1 if index + 1 < len(mandatory_starts) else last_line
            current_start = segment_start

            while True:
                break_line = self._find_break_line(cues, current_start, segment_end)
                if break_line is None:
                    break

                next_start = break_line + 1
                if next_start > segment_end:
                    break

                paragraph_starts.append(next_start)
                current_start = next_start

            if index + 1 < len(mandatory_starts):
                next_mandatory = mandatory_starts[index + 1]
                if paragraph_starts[-1] != next_mandatory:
                    paragraph_starts.append(next_mandatory)

        return sorted(set(paragraph_starts))

    def _find_break_line(self, cues: list[TranscriptCue], start_line: int, end_line: int) -> int | None:
        """Find the best paragraph end line within one segment."""
        if start_line >= end_line:
            return None

        candidates: list[tuple[int, int]] = []
        fallback_line: int | None = None
        char_count = 0
        has_text = False

        for cue in cues[start_line - 1 : end_line]:
            if cue.text:
                if has_text:
                    char_count += 1
                char_count += len(cue.text)
                has_text = True

            if cue.line_number >= end_line:
                continue

            if char_count >= self.target_chars and fallback_line is None:
                fallback_line = cue.line_number

            if cue.text and SENTENCE_END_RE.match(cue.text):
                candidates.append((cue.line_number, char_count))

        if char_count <= self.target_chars:
            return None

        eligible_candidates = [item for item in candidates if item[0] < end_line]
        if eligible_candidates:
            return min(
                eligible_candidates,
                key=lambda item: (abs(item[1] - self.target_chars), item[0]),
            )[0]

        return fallback_line

    def _to_break_points(self, paragraph_starts: list[int], last_line: int) -> list[int]:
        """Convert paragraph starts into paragraph end line numbers."""
        break_points = sorted({start - 1 for start in paragraph_starts if start > 1})
        break_points.append(last_line)
        return sorted(set(break_points))
