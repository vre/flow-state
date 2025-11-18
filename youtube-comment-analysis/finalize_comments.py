#!/usr/bin/env python3
"""
Creates final comment analysis markdown file from template and component files.

Usage: finalize_comments.py <BASE_NAME> <OUTPUT_DIR> [--debug]
Keeps: {BASE_NAME}_comment_analysis.md
Removes: _name.txt, _comments.md, _comments_cleaned.md, _comment_gold.md (unless --debug)
"""

import re
import sys
from pathlib import Path

from types_and_exceptions import FileSystem, TemplateNotFoundError


# Business logic functions (pure, testable)
def clean_title_for_filename(title: str, max_length: int = 60) -> str:
    """
    Clean title for use in filename.

    Args:
        title: Video title
        max_length: Maximum length for filename

    Returns:
        Cleaned title suitable for filename
    """
    # Remove or replace problematic characters
    cleaned = re.sub(r'[<>:"/\\|?*]', "", title)  # Remove invalid filename chars
    cleaned = re.sub(r"\s+", " ", cleaned)  # Normalize whitespace
    cleaned = cleaned.strip()

    # Truncate if too long
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length].rsplit(" ", 1)[0]  # Cut at word boundary

    return cleaned


def generate_final_filename(video_name: str, video_id: str) -> str:
    """
    Generate final filename from video name and ID.

    Args:
        video_name: Video title
        video_id: Video ID (without youtube_ prefix)

    Returns:
        Final filename
    """
    if video_name.strip():
        cleaned_title = clean_title_for_filename(video_name.strip())
        return f"youtube - {cleaned_title} - comments ({video_id}).md"
    else:
        # Fallback to base_name format if title not found
        return f"youtube_{video_id}_comment_analysis.md"


def fill_template(template: str, video_name: str, comment_gold: str, comments: str) -> str:
    """
    Fill template with component content.

    Args:
        template: Template content with placeholders
        video_name: Video title
        comment_gold: Golden comments content
        comments: Cleaned comments content

    Returns:
        Final content with placeholders replaced
    """
    content = template.replace("{video_name}", video_name.strip())
    content = content.replace("{comment_gold}", comment_gold.strip())
    content = content.replace("{comments}", comments.strip())
    return content


def get_work_files(base_name: str) -> list[str]:
    """
    Get list of intermediate work files to clean up.

    Args:
        base_name: Base name (e.g., youtube_VIDEO_ID)

    Returns:
        List of work file names
    """
    return [
        f"{base_name}_name.txt",
        f"{base_name}_comments.md",
        f"{base_name}_comments_cleaned.md",
        f"{base_name}_comment_gold.md",
    ]


# I/O layer (uses injected dependencies)
class CommentFinalizer:
    """Finalize comment analysis using dependency injection for testability."""

    def __init__(self, filesystem: FileSystem, script_dir: Path):
        """
        Initialize finalizer with dependencies.

        Args:
            filesystem: File system interface for I/O
            script_dir: Directory containing the script and template
        """
        self.filesystem = filesystem
        self.script_dir = script_dir

    def load_template(self, standalone: bool = False) -> str:
        """
        Load template file.

        Args:
            standalone: If True, load standalone template with Golden Insights section

        Returns:
            Template content

        Raises:
            TemplateNotFoundError: If template file not found
        """
        template_name = "template_standalone.md" if standalone else "template.md"
        template_file = self.script_dir / template_name
        if not self.filesystem.exists(template_file):
            raise TemplateNotFoundError(f"Template not found: {template_file}")
        return self.filesystem.read_text(template_file)

    def read_file_or_empty(self, file_path: Path) -> str:
        """
        Read file content or return empty string if file doesn't exist.

        Args:
            file_path: Path to file

        Returns:
            File content or empty string
        """
        if self.filesystem.exists(file_path):
            return self.filesystem.read_text(file_path)
        return ""

    def insert_golden_comments_into_summary(
        self, summary_file: Path, comment_gold: str
    ) -> None:
        """
        Insert Golden Comments section into existing summary file before Description.

        Args:
            summary_file: Path to summary file
            comment_gold: Golden comments content to insert
        """
        if not self.filesystem.exists(summary_file):
            return

        content = self.filesystem.read_text(summary_file)

        # Find "## Description" and insert before it
        description_marker = "## Description"
        if description_marker in content:
            golden_section = f"## Golden Comments\n\n{comment_gold.strip()}\n\n"
            updated_content = content.replace(
                description_marker, f"{golden_section}{description_marker}"
            )
            self.filesystem.write_text(summary_file, updated_content)
            print(f"Inserted Golden Comments into summary file: {summary_file.name}")

    def finalize(
        self, base_name: str, output_dir: Path, debug: bool = False
    ) -> Path:
        """
        Create final comment analysis file and clean up intermediate files.

        Args:
            base_name: Base name (e.g., youtube_VIDEO_ID)
            output_dir: Output directory
            debug: If True, keep intermediate work files

        Returns:
            Path to final file

        Raises:
            TemplateNotFoundError: If template not found
        """
        # Read component files
        video_name = self.read_file_or_empty(output_dir / f"{base_name}_name.txt")
        comment_gold = self.read_file_or_empty(output_dir / f"{base_name}_comment_gold.md")
        comments = self.read_file_or_empty(output_dir / f"{base_name}_comments_cleaned.md")

        # Generate summary filename to check if it exists
        video_id = base_name.replace("youtube_", "")
        summary_filename = f"youtube - {clean_title_for_filename(video_name.strip())} ({video_id}).md" if video_name.strip() else None
        summary_file = output_dir / summary_filename if summary_filename else None

        # Check if summary file exists
        summary_exists = summary_file and self.filesystem.exists(summary_file)

        if summary_exists:
            # Insert Golden Comments into existing summary file (if they exist)
            if comment_gold:
                self.insert_golden_comments_into_summary(summary_file, comment_gold)
            # Use template without Golden Insights section
            template = self.load_template(standalone=False)
        else:
            # Use standalone template with Golden Insights section
            template = self.load_template(standalone=True)

        # Fill template
        final_content = fill_template(template, video_name, comment_gold, comments)

        # Generate filename
        final_filename = generate_final_filename(video_name, video_id)

        # Write final file
        final_file = output_dir / final_filename
        self.filesystem.write_text(final_file, final_content)

        print(f"Created final file: {final_filename}")

        # Clean up intermediate work files unless --debug is set
        if debug:
            print("Debug mode: keeping intermediate work files")
        else:
            work_files = get_work_files(base_name)
            for work_file in work_files:
                file_path = output_dir / work_file
                if self.filesystem.exists(file_path):
                    self.filesystem.remove(file_path)
            print("Cleaned up intermediate work files")

        print(f"Final file: {final_filename}")
        return final_file


# Real implementation for production use
class RealFileSystem:
    """Real file system implementation."""

    def read_text(self, path: Path) -> str:
        """Read text from file."""
        return path.read_text(encoding="utf-8")

    def write_text(self, path: Path, content: str) -> None:
        """Write text to file."""
        path.write_text(content, encoding="utf-8")

    def exists(self, path: Path) -> bool:
        """Check if path exists."""
        return path.exists()

    def mkdir(self, path: Path, parents: bool = False, exist_ok: bool = False) -> None:
        """Create directory."""
        path.mkdir(parents=parents, exist_ok=exist_ok)

    def remove(self, path: Path) -> None:
        """Remove file."""
        path.unlink()


def parse_args(args: list[str]) -> tuple[str, Path, bool]:
    """
    Parse command line arguments.

    Args:
        args: Command line arguments (excluding script name)

    Returns:
        Tuple of (base_name, output_dir, debug)
    """
    debug = False
    filtered_args = []
    for arg in args:
        if arg == "--debug":
            debug = True
        else:
            filtered_args.append(arg)

    if len(filtered_args) < 1:
        raise ValueError("No BASE_NAME provided")

    base_name = filtered_args[0]
    output_dir = Path(filtered_args[1]) if len(filtered_args) > 1 else Path(".")

    return base_name, output_dir, debug


def main() -> None:
    """Main entry point."""
    try:
        base_name, output_dir, debug = parse_args(sys.argv[1:])
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        print("Usage: finalize_comments.py <BASE_NAME> <OUTPUT_DIR> [--debug]", file=sys.stderr)
        sys.exit(1)

    # Get script directory for template
    script_dir = Path(__file__).parent.resolve()

    # Create finalizer with real dependencies
    finalizer = CommentFinalizer(RealFileSystem(), script_dir)

    try:
        finalizer.finalize(base_name, output_dir, debug)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
