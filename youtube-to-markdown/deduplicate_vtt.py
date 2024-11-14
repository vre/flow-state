#!/usr/bin/env python3
"""
Deduplicate VTT (removes duplicate lines from auto-generated captions)
Usage: python3 deduplicate_vtt.py <INPUT_VTT> <OUTPUT_MD>
Output format: [00:00:01.000] Text here
"""

import re
import sys
from pathlib import Path

from shared_types import FileSystem, RealFileSystem, FileOperationError


class VTTDeduplicator:
    """Deduplicates VTT transcript files."""

    def __init__(self, fs: FileSystem = RealFileSystem()):
        """
        Initialize deduplicator with dependencies.

        Args:
            fs: File system implementation
        """
        self.fs = fs

    def parse_vtt_line(self, line: str) -> tuple[str | None, str]:
        """
        Parse VTT line into timestamp and text components.

        Args:
            line: Raw line from VTT file

        Returns:
            Tuple of (timestamp, clean_text)
        """
        line = line.strip()

        # Skip headers
        if line.startswith('WEBVTT') or line.startswith('Kind:') or line.startswith('Language:'):
            return None, ""

        # Capture timestamp (start time only)
        if '-->' in line:
            timestamp = line.split('-->')[0].strip()
            return timestamp, ""

        # Clean HTML tags and entities
        if line:
            clean = re.sub('<[^>]*>', '', line)
            clean = clean.replace('&amp;', '&').replace('&gt;', '>').replace('&lt;', '<')
            return None, clean

        return None, ""

    def deduplicate_vtt(self, input_path: Path, output_path: Path) -> int:
        """
        Deduplicate VTT file and save as markdown.

        Args:
            input_path: Path to input VTT file
            output_path: Path to output markdown file

        Returns:
            Number of lines written

        Raises:
            FileOperationError: If file operations fail
        """
        if not self.fs.exists(input_path):
            raise FileOperationError(f"{input_path} not found")

        seen = set()
        current_timestamp = None
        output_lines = []

        # Read and process VTT file
        content = self.fs.read_text(input_path)
        for line in content.split('\n'):
            timestamp, text = self.parse_vtt_line(line)

            # Update current timestamp
            if timestamp:
                current_timestamp = timestamp
                continue

            # Process text with deduplication
            if text and current_timestamp and text not in seen:
                output_lines.append(f'[{current_timestamp}] {text}')
                seen.add(text)

        # Validate output
        if not output_lines:
            raise FileOperationError(f"No text extracted from {input_path}")

        # Write to output file
        self.fs.write_text(output_path, '\n'.join(output_lines))

        # Verify file was created
        if not self.fs.exists(output_path):
            raise FileOperationError(f"Failed to create {output_path}")

        print(f"SUCCESS: {output_path} ({len(output_lines)} lines)")
        return len(output_lines)


def main() -> None:
    """CLI entry point."""
    if len(sys.argv) != 3:
        print("Usage: python3 deduplicate_vtt.py <INPUT_VTT> <OUTPUT_MD>", file=sys.stderr)
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    try:
        deduplicator = VTTDeduplicator()
        deduplicator.deduplicate_vtt(input_path, output_path)
    except Exception as e:
        print(f"ERROR: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
