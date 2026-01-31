"""VTT transcript deduplication library."""

import re
from pathlib import Path

from lib.content_safety import wrap_untrusted_content
from lib.shared_types import FileOperationError, FileSystem, RealFileSystem


class VTTDeduplicator:
    """Deduplicates VTT transcript files."""

    def __init__(self, fs: FileSystem = RealFileSystem()):
        self.fs = fs

    def parse_vtt_line(self, line: str) -> tuple[str | None, str]:
        line = line.strip()

        if line.startswith("WEBVTT") or line.startswith("Kind:") or line.startswith("Language:"):
            return None, ""

        if "-->" in line:
            timestamp = line.split("-->")[0].strip()
            return timestamp, ""

        if line:
            clean = re.sub("<[^>]*>", "", line)
            clean = clean.replace("&amp;", "&").replace("&gt;", ">").replace("&lt;", "<")
            return None, clean

        return None, ""

    def deduplicate_vtt(self, input_path: Path, output_path: Path, no_timestamps_path: Path | None = None) -> int:
        if not self.fs.exists(input_path):
            raise FileOperationError(f"{input_path} not found")

        seen = set()
        current_timestamp = None
        output_lines = []

        content = self.fs.read_text(input_path)
        for line in content.split("\n"):
            timestamp, text = self.parse_vtt_line(line)

            if timestamp:
                current_timestamp = timestamp
                continue

            if text and current_timestamp and text not in seen:
                output_lines.append(f"[{current_timestamp}] {text}")
                seen.add(text)

        if not output_lines:
            raise FileOperationError(f"No text extracted from {input_path}")

        self.fs.write_text(output_path, "\n".join(output_lines))

        if not self.fs.exists(output_path):
            raise FileOperationError(f"Failed to create {output_path}")

        if no_timestamps_path:
            plain_lines = [line[15:] for line in output_lines]
            plain_text = "\n".join(plain_lines)
            # Wrap in safety delimiters to defend against prompt injection
            safe_transcript = wrap_untrusted_content(plain_text, "transcript")
            self.fs.write_text(no_timestamps_path, safe_transcript)

        print(f"SUCCESS: {output_path} ({len(output_lines)} lines)")
        return len(output_lines)
