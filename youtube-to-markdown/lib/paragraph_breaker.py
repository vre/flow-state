"""Paragraph break application library."""

import re
from dataclasses import dataclass
from pathlib import Path

from lib.shared_types import FileOperationError, FileSystem, RealFileSystem


@dataclass
class ParsedLine:
    """Represents a parsed transcript line."""

    timestamp: str | None
    text: str


def extract_video_id_from_path(file_path: Path) -> str | None:
    """Extract video ID from file path with pattern youtube_{VIDEO_ID}_*."""
    match = re.match(r"youtube_([a-zA-Z0-9_-]+)_", file_path.name)
    return match.group(1) if match else None


class ParagraphBreaker:
    """Applies paragraph breaks to transcript."""

    def __init__(self, fs: FileSystem = RealFileSystem(), video_id: str | None = None):
        self.fs = fs
        self.video_id = video_id

    def parse_break_points(self, break_points_str: str) -> set[int]:
        try:
            return {int(x.strip()) for x in break_points_str.split(",")}
        except ValueError as e:
            raise ValueError(f"Invalid break points format: {e}") from e

    def convert_timestamp_to_link(self, timestamp: str) -> str:
        if not self.video_id:
            return timestamp

        match = re.match(r"\[(\d{2}):(\d{2}):(\d{2})\.\d{3}\]", timestamp)
        if match:
            hours, minutes, seconds = map(int, match.groups())
            total_seconds = hours * 3600 + minutes * 60 + seconds
            display_time = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            match = re.match(r"\[(\d{2}):(\d{2})\.\d{3}\]", timestamp)
            if match:
                minutes, seconds = map(int, match.groups())
                total_seconds = minutes * 60 + seconds
                display_time = f"{minutes:02d}:{seconds:02d}"
            else:
                return timestamp

        youtube_url = f"https://youtube.com/watch?v={self.video_id}&t={total_seconds}s"
        return f"[[{display_time}]]({youtube_url})"

    def parse_transcript_line(self, line: str) -> ParsedLine:
        if line.startswith("[") and len(line) > 15:
            timestamp = line[:14]
            text = line[15:]
            return ParsedLine(timestamp=timestamp, text=text)
        return ParsedLine(timestamp=None, text=line)

    def apply_breaks(self, input_path: Path, output_path: Path, break_points: set[int]) -> int:
        if not self.fs.exists(input_path):
            raise FileOperationError(f"{input_path} not found")

        content = self.fs.read_text(input_path)
        lines = content.split("\n")
        parsed_lines = [self.parse_transcript_line(line) for line in lines]

        paragraphs = []
        current_paragraph = []
        paragraph_start_timestamp = None

        for i, parsed in enumerate(parsed_lines, start=1):
            if parsed.timestamp and not paragraph_start_timestamp:
                paragraph_start_timestamp = parsed.timestamp

            if parsed.text:
                current_paragraph.append(parsed.text)

            if i in break_points or i == len(parsed_lines):
                if current_paragraph and paragraph_start_timestamp:
                    paragraph_text = " ".join(current_paragraph)
                    timestamp_link = self.convert_timestamp_to_link(paragraph_start_timestamp)
                    paragraphs.append(f"{paragraph_text} {timestamp_link}")
                    current_paragraph = []
                    paragraph_start_timestamp = None

        if not paragraphs:
            raise FileOperationError(f"No paragraphs created from {input_path}")

        output_content = "\n\n".join(paragraphs) + "\n\n"
        self.fs.write_text(output_path, output_content)

        print(f"SUCCESS: Created {len(paragraphs)} paragraphs -> {output_path}")
        return len(paragraphs)
