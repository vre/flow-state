#!/usr/bin/env python3
"""
Creates single final markdown file with summary and comment insights.
Usage: finalize_lite.py [--debug] <BASE_NAME> <OUTPUT_DIR>

Output: youtube - {title} ({video_id}).md
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from shared_types import FileSystem, RealFileSystem, clean_title_for_filename


class FinalizerLite:
    """Finalizes YouTube to Markdown Lite conversion."""

    def __init__(self, fs: FileSystem = RealFileSystem()):
        self.fs = fs

    def read_or_empty(self, path: Path) -> str:
        """Read file or return empty string."""
        if self.fs.exists(path):
            return self.fs.read_text(path).strip()
        return ""

    def strip_header(self, content: str, header: str) -> str:
        """Strip leading markdown header if present."""
        if content.startswith(header):
            return content[len(header):].lstrip()
        return content

    def finalize(self, base_name: str, output_dir: Path, debug: bool = False) -> Path:
        """Create final combined markdown file."""

        # Read components
        title = self.read_or_empty(output_dir / f"{base_name}_title.txt")
        metadata = self.read_or_empty(output_dir / f"{base_name}_metadata.md")
        summary = self.read_or_empty(output_dir / f"{base_name}_summary.md")
        comments = self.read_or_empty(output_dir / f"{base_name}_comment_insights.md")

        # Strip duplicate headers
        summary = self.strip_header(summary, "## Summary")
        comments = self.strip_header(comments, "## Comment Insights")

        # Build final content
        sections = ["## Video Info", "", metadata, ""]

        if summary:
            sections.extend(["## Summary", "", summary, ""])

        if comments:
            sections.extend(["## What Viewers Add", "", comments, ""])

        final_content = "\n".join(sections)

        # Create filename
        video_id = base_name.replace('youtube_', '')
        if title:
            cleaned_title = clean_title_for_filename(title)
            filename = f"youtube - {cleaned_title} ({video_id}).md"
        else:
            filename = f"{base_name}.md"

        output_path = output_dir / filename
        self.fs.write_text(output_path, final_content)
        print(f"Created: {filename}")

        # Also create raw transcript file for reference
        transcript_dedup = self.read_or_empty(output_dir / f"{base_name}_transcript_dedup.md")
        description = self.read_or_empty(output_dir / f"{base_name}_description.md")

        if transcript_dedup:
            if title:
                transcript_filename = f"youtube - {cleaned_title} - transcript ({video_id}).md"
            else:
                transcript_filename = f"{base_name}_transcript.md"

            transcript_content = f"## Description\n\n{description}\n\n## Transcript\n\n{transcript_dedup}"
            self.fs.write_text(output_dir / transcript_filename, transcript_content)
            print(f"Created: {transcript_filename}")

        # Cleanup unless debug
        if not debug:
            self.cleanup(base_name, output_dir)
        else:
            print("Debug mode: keeping intermediate files")

        return output_path

    def cleanup(self, base_name: str, output_dir: Path) -> None:
        """Remove intermediate work files."""
        work_files = [
            f"{base_name}_title.txt",
            f"{base_name}_name.txt",
            f"{base_name}_metadata.md",
            f"{base_name}_description.md",
            f"{base_name}_chapters.json",
            f"{base_name}_summary.md",
            f"{base_name}_transcript.vtt",
            f"{base_name}_transcript_dedup.md",
            f"{base_name}_transcript_no_timestamps.txt",
            f"{base_name}_comments.md",
            f"{base_name}_comments_prefiltered.md",
            f"{base_name}_comment_insights.md",
        ]

        for work_file in work_files:
            file_path = output_dir / work_file
            if self.fs.exists(file_path):
                self.fs.remove(file_path)

        print("Cleaned up intermediate files")


def main() -> None:
    """CLI entry point."""
    debug = False
    args = []
    for arg in sys.argv[1:]:
        if arg == '--debug':
            debug = True
        else:
            args.append(arg)

    if len(args) < 1:
        print("Usage: finalize_lite.py [--debug] <BASE_NAME> <OUTPUT_DIR>", file=sys.stderr)
        sys.exit(1)

    base_name = args[0]
    output_dir = Path(args[1]) if len(args) > 1 else Path(".")

    try:
        finalizer = FinalizerLite()
        finalizer.finalize(base_name, output_dir, debug)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
