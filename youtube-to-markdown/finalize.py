#!/usr/bin/env python3
"""
Creates final markdown files from template and component files, cleans up intermediate work files.

Usage: finalize.py [options] <BASE_NAME> <OUTPUT_DIR>

Options:
  --summary-only     Create only summary file
  --transcript-only  Create only transcript file
  --comments-only    Create only comments file
  --summary-comments Create summary and comments files
  --debug            Keep intermediate work files

Default (no mode flag): Create summary, transcript, and comments files (Full mode)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from shared_types import FileSystem, RealFileSystem, clean_title_for_filename, FileOperationError


class Finalizer:
    """Finalizes YouTube to Markdown conversion."""

    def __init__(self, fs: FileSystem = RealFileSystem()):
        """Initialize finalizer with dependencies."""
        self.fs = fs

    def read_template(self, script_dir: Path, template_name: str) -> str:
        """Read template file."""
        template_file = script_dir / template_name
        if not self.fs.exists(template_file):
            raise FileOperationError(f"{template_file} not found")
        return self.fs.read_text(template_file)

    def read_component_or_empty(self, path: Path) -> str:
        """Read component file or return empty string if not found."""
        if self.fs.exists(path):
            return self.fs.read_text(path)
        return ""

    def strip_leading_header(self, content: str, header: str) -> str:
        """Strip leading markdown header if present."""
        stripped = content.strip()
        if stripped.startswith(header):
            stripped = stripped[len(header):].lstrip()
        return stripped

    def get_filenames(self, base_name: str, output_dir: Path) -> tuple[str, str]:
        """Get cleaned title and video ID for filename generation."""
        title_path = output_dir / f"{base_name}_title.txt"
        title = self.read_component_or_empty(title_path).strip()
        video_id = base_name.replace('youtube_', '')

        if title:
            cleaned_title = clean_title_for_filename(title)
        else:
            cleaned_title = None

        return cleaned_title, video_id

    def assemble_summary_content(
        self,
        template: str,
        base_name: str,
        output_dir: Path
    ) -> str:
        """Assemble summary content from template and components."""
        quick_summary = self.read_component_or_empty(output_dir / f"{base_name}_quick_summary.md")
        metadata = self.read_component_or_empty(output_dir / f"{base_name}_metadata.md")
        summary = self.read_component_or_empty(output_dir / f"{base_name}_summary_tight.md")

        quick_summary = self.strip_leading_header(quick_summary, "## Quick Summary")
        summary = self.strip_leading_header(summary, "## Summary")

        final_content = template.replace("{quick_summary}", quick_summary.strip())
        final_content = final_content.replace("{metadata}", metadata.strip())
        final_content = final_content.replace("{summary}", summary.strip())

        return final_content

    def assemble_transcript_content(
        self,
        template: str,
        base_name: str,
        output_dir: Path
    ) -> str:
        """Assemble transcript content from template and components."""
        description = self.read_component_or_empty(output_dir / f"{base_name}_description.md")
        transcription = self.read_component_or_empty(output_dir / f"{base_name}_transcript.md")

        transcript_content = template.replace("{description}", description.strip())
        transcript_content = transcript_content.replace("{transcription}", transcription.strip())

        return transcript_content

    def assemble_comments_content(
        self,
        template: str,
        base_name: str,
        output_dir: Path,
        standalone: bool = False
    ) -> str:
        """Assemble comments content from template and components."""
        comment_insights = self.read_component_or_empty(output_dir / f"{base_name}_comment_insights_tight.md")
        comments = self.read_component_or_empty(output_dir / f"{base_name}_comments_prefiltered.md")

        if standalone:
            # Include comment insights in the file
            content = template.replace("{comment_insights}", comment_insights.strip())
        else:
            # Comment insights will be appended to summary
            content = template

        content = content.replace("{comments}", comments.strip())
        return content

    def insert_comment_insights_into_summary(
        self,
        summary_path: Path,
        comment_insights: str
    ) -> None:
        """Insert Comment Insights section into existing summary file at end."""
        if not self.fs.exists(summary_path) or not comment_insights.strip():
            return

        content = self.fs.read_text(summary_path)
        insights_section = f"\n\n{comment_insights.strip()}\n"
        updated_content = content.rstrip() + insights_section

        self.fs.write_text(summary_path, updated_content)
        print(f"Inserted Comment Insights into summary file: {summary_path.name}")

    def get_summary_work_files(self, base_name: str) -> list[str]:
        """Get work files for summary mode."""
        return [
            f"{base_name}_title.txt",
            f"{base_name}_metadata.md",
            f"{base_name}_summary.md",
            f"{base_name}_summary_tight.md",
            f"{base_name}_quick_summary.md",
            f"{base_name}_chapters.json",
            f"{base_name}_transcript.vtt",
            f"{base_name}_transcript_dedup.md",
            f"{base_name}_transcript_no_timestamps.txt",
        ]

    def get_transcript_work_files(self, base_name: str) -> list[str]:
        """Get work files for transcript mode."""
        return [
            f"{base_name}_title.txt",
            f"{base_name}_description.md",
            f"{base_name}_chapters.json",
            f"{base_name}_transcript.vtt",
            f"{base_name}_transcript_dedup.md",
            f"{base_name}_transcript_no_timestamps.txt",
            f"{base_name}_transcript_paragraphs.txt",
            f"{base_name}_transcript_paragraphs.md",
            f"{base_name}_transcript_cleaned.md",
            f"{base_name}_transcript.md",
        ]

    def get_comments_work_files(self, base_name: str) -> list[str]:
        """Get work files for comments mode."""
        return [
            f"{base_name}_name.txt",
            f"{base_name}_comments.md",
            f"{base_name}_comments_prefiltered.md",
            f"{base_name}_comment_insights.md",
            f"{base_name}_comment_insights_tight.md",
        ]

    def get_full_work_files(self, base_name: str) -> list[str]:
        """Get all work files for full mode."""
        return (
            self.get_summary_work_files(base_name) +
            self.get_transcript_work_files(base_name) +
            self.get_comments_work_files(base_name)
        )

    def cleanup_work_files(self, work_files: list[str], output_dir: Path) -> None:
        """Remove intermediate work files."""
        # Deduplicate while preserving order
        seen = set()
        unique_files = []
        for f in work_files:
            if f not in seen:
                seen.add(f)
                unique_files.append(f)

        for work_file in unique_files:
            file_path = output_dir / work_file
            if self.fs.exists(file_path):
                self.fs.remove(file_path)

        print("Cleaned up intermediate work files")

    def finalize_summary_only(
        self,
        base_name: str,
        output_dir: Path,
        debug: bool = False
    ) -> Path:
        """Create only summary file."""
        script_dir = Path(__file__).parent
        template = self.read_template(script_dir, "template.md")

        content = self.assemble_summary_content(template, base_name, output_dir)
        cleaned_title, video_id = self.get_filenames(base_name, output_dir)

        if cleaned_title:
            filename = f"youtube - {cleaned_title} ({video_id}).md"
        else:
            filename = f"{base_name}.md"

        output_path = output_dir / filename
        self.fs.write_text(output_path, content)
        print(f"Created summary file: {filename}")

        if not debug:
            self.cleanup_work_files(self.get_summary_work_files(base_name), output_dir)

        return output_path

    def finalize_transcript_only(
        self,
        base_name: str,
        output_dir: Path,
        debug: bool = False
    ) -> Path:
        """Create only transcript file."""
        script_dir = Path(__file__).parent
        template = self.read_template(script_dir, "template_transcript.md")

        content = self.assemble_transcript_content(template, base_name, output_dir)
        cleaned_title, video_id = self.get_filenames(base_name, output_dir)

        if cleaned_title:
            filename = f"youtube - {cleaned_title} - transcript ({video_id}).md"
        else:
            filename = f"{base_name}_transcript.md"

        output_path = output_dir / filename
        self.fs.write_text(output_path, content)
        print(f"Created transcript file: {filename}")

        if not debug:
            self.cleanup_work_files(self.get_transcript_work_files(base_name), output_dir)

        return output_path

    def finalize_comments_only(
        self,
        base_name: str,
        output_dir: Path,
        debug: bool = False
    ) -> Path:
        """Create only comments file (standalone with insights)."""
        script_dir = Path(__file__).parent
        template = self.read_template(script_dir, "template_comments_standalone.md")

        content = self.assemble_comments_content(template, base_name, output_dir, standalone=True)

        # For comments-only, get title from _name.txt instead of _title.txt
        name_path = output_dir / f"{base_name}_name.txt"
        title = self.read_component_or_empty(name_path).strip()
        video_id = base_name.replace('youtube_', '')

        if title:
            cleaned_title = clean_title_for_filename(title)
            filename = f"youtube - {cleaned_title} - comments ({video_id}).md"
        else:
            filename = f"{base_name}_comments.md"

        output_path = output_dir / filename
        self.fs.write_text(output_path, content)
        print(f"Created comments file: {filename}")

        if not debug:
            self.cleanup_work_files(self.get_comments_work_files(base_name), output_dir)

        return output_path

    def finalize_summary_comments(
        self,
        base_name: str,
        output_dir: Path,
        debug: bool = False
    ) -> tuple[Path, Path]:
        """Create summary and comments files, insert insights into summary."""
        script_dir = Path(__file__).parent

        # Create summary file
        summary_template = self.read_template(script_dir, "template.md")
        summary_content = self.assemble_summary_content(summary_template, base_name, output_dir)
        cleaned_title, video_id = self.get_filenames(base_name, output_dir)

        if cleaned_title:
            summary_filename = f"youtube - {cleaned_title} ({video_id}).md"
            comments_filename = f"youtube - {cleaned_title} - comments ({video_id}).md"
        else:
            summary_filename = f"{base_name}.md"
            comments_filename = f"{base_name}_comments.md"

        summary_path = output_dir / summary_filename
        self.fs.write_text(summary_path, summary_content)
        print(f"Created summary file: {summary_filename}")

        # Insert comment insights into summary
        comment_insights = self.read_component_or_empty(output_dir / f"{base_name}_comment_insights_tight.md")
        self.insert_comment_insights_into_summary(summary_path, comment_insights)

        # Create comments file (without insights, they're in summary)
        comments_template = self.read_template(script_dir, "template_comments.md")
        comments_content = self.assemble_comments_content(comments_template, base_name, output_dir, standalone=False)

        comments_path = output_dir / comments_filename
        self.fs.write_text(comments_path, comments_content)
        print(f"Created comments file: {comments_filename}")

        if not debug:
            work_files = self.get_summary_work_files(base_name) + self.get_comments_work_files(base_name)
            self.cleanup_work_files(work_files, output_dir)

        return summary_path, comments_path

    def finalize_full(
        self,
        base_name: str,
        output_dir: Path,
        debug: bool = False
    ) -> tuple[Path, Path, Path]:
        """Create summary, transcript, and comments files."""
        script_dir = Path(__file__).parent
        cleaned_title, video_id = self.get_filenames(base_name, output_dir)

        # Determine filenames
        if cleaned_title:
            summary_filename = f"youtube - {cleaned_title} ({video_id}).md"
            transcript_filename = f"youtube - {cleaned_title} - transcript ({video_id}).md"
            comments_filename = f"youtube - {cleaned_title} - comments ({video_id}).md"
        else:
            summary_filename = f"{base_name}.md"
            transcript_filename = f"{base_name}_transcript.md"
            comments_filename = f"{base_name}_comments.md"

        # Create summary file
        summary_template = self.read_template(script_dir, "template.md")
        summary_content = self.assemble_summary_content(summary_template, base_name, output_dir)
        summary_path = output_dir / summary_filename
        self.fs.write_text(summary_path, summary_content)
        print(f"Created summary file: {summary_filename}")

        # Insert comment insights into summary
        comment_insights = self.read_component_or_empty(output_dir / f"{base_name}_comment_insights_tight.md")
        self.insert_comment_insights_into_summary(summary_path, comment_insights)

        # Create transcript file
        transcript_template = self.read_template(script_dir, "template_transcript.md")
        transcript_content = self.assemble_transcript_content(transcript_template, base_name, output_dir)
        transcript_path = output_dir / transcript_filename
        self.fs.write_text(transcript_path, transcript_content)
        print(f"Created transcript file: {transcript_filename}")

        # Create comments file
        comments_template = self.read_template(script_dir, "template_comments.md")
        comments_content = self.assemble_comments_content(comments_template, base_name, output_dir, standalone=False)
        comments_path = output_dir / comments_filename
        self.fs.write_text(comments_path, comments_content)
        print(f"Created comments file: {comments_filename}")

        if not debug:
            self.cleanup_work_files(self.get_full_work_files(base_name), output_dir)

        return summary_path, transcript_path, comments_path


def main() -> None:
    """CLI entry point."""
    # Parse options
    debug = False
    mode = "full"
    args = []

    for arg in sys.argv[1:]:
        if arg == '--debug':
            debug = True
        elif arg == '--summary-only':
            mode = "summary-only"
        elif arg == '--transcript-only':
            mode = "transcript-only"
        elif arg == '--comments-only':
            mode = "comments-only"
        elif arg == '--summary-comments':
            mode = "summary-comments"
        else:
            args.append(arg)

    if len(args) < 1:
        print("ERROR: No BASE_NAME provided", file=sys.stderr)
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    base_name = args[0]
    output_dir = Path(args[1]) if len(args) > 1 else Path(".")

    try:
        finalizer = Finalizer()

        if debug:
            print("Debug mode: keeping intermediate work files")

        if mode == "summary-only":
            finalizer.finalize_summary_only(base_name, output_dir, debug)
        elif mode == "transcript-only":
            finalizer.finalize_transcript_only(base_name, output_dir, debug)
        elif mode == "comments-only":
            finalizer.finalize_comments_only(base_name, output_dir, debug)
        elif mode == "summary-comments":
            finalizer.finalize_summary_comments(base_name, output_dir, debug)
        else:
            finalizer.finalize_full(base_name, output_dir, debug)

    except Exception as e:
        print(f"ERROR: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
