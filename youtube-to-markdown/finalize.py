#!/usr/bin/env python3
"""
Creates final markdown file from template and component files, cleans up intermediate work files
Usage: finalize.py [--debug] <BASE_NAME> <OUTPUT_DIR>
Keeps: {BASE_NAME}.md
Removes: all intermediate files including _metadata.md, _summary.md, _description.md, _transcript.md (unless --debug)
"""

import sys
from pathlib import Path

from shared_types import FileSystem, RealFileSystem, clean_title_for_filename, FileOperationError


class Finalizer:
    """Finalizes YouTube to Markdown conversion."""

    def __init__(self, fs: FileSystem = RealFileSystem()):
        """
        Initialize finalizer with dependencies.

        Args:
            fs: File system implementation
        """
        self.fs = fs

    def read_template(self, script_dir: Path) -> str:
        """
        Read template file.

        Args:
            script_dir: Directory containing this script

        Returns:
            Template content

        Raises:
            FileOperationError: If template not found
        """
        template_file = script_dir / "template.md"
        if not self.fs.exists(template_file):
            raise FileOperationError(f"{template_file} not found")
        return self.fs.read_text(template_file)

    def read_component_or_empty(self, path: Path) -> str:
        """
        Read component file or return empty string if not found.

        Args:
            path: Path to component file

        Returns:
            File content or empty string
        """
        if self.fs.exists(path):
            return self.fs.read_text(path)
        return ""

    def create_final_filename(self, base_name: str, output_dir: Path) -> str:
        """
        Create human-readable filename from title.

        Args:
            base_name: Base name (youtube_{VIDEO_ID})
            output_dir: Output directory

        Returns:
            Final filename
        """
        title_path = output_dir / f"{base_name}_title.txt"
        title = self.read_component_or_empty(title_path).strip()

        if title:
            cleaned_title = clean_title_for_filename(title)
            video_id = base_name.replace('youtube_', '')
            return f"youtube - {cleaned_title} ({video_id}).md"
        else:
            # Fallback to old format if title not found
            return f"{base_name}.md"

    def assemble_final_content(
        self,
        template: str,
        base_name: str,
        output_dir: Path
    ) -> str:
        """
        Assemble final content from template and components.

        Args:
            template: Template content
            base_name: Base name
            output_dir: Output directory

        Returns:
            Final assembled content
        """
        # Read component files
        metadata = self.read_component_or_empty(output_dir / f"{base_name}_metadata.md")
        summary = self.read_component_or_empty(output_dir / f"{base_name}_summary.md")
        description = self.read_component_or_empty(output_dir / f"{base_name}_description.md")
        transcription = self.read_component_or_empty(output_dir / f"{base_name}_transcript.md")

        # Replace placeholders
        final_content = template.replace("{metadata}", metadata.strip())
        final_content = final_content.replace("{summary}", summary.strip())
        final_content = final_content.replace("{description}", description.strip())
        final_content = final_content.replace("{transcription}", transcription.strip())

        return final_content

    def cleanup_work_files(self, base_name: str, output_dir: Path) -> None:
        """
        Remove intermediate work files.

        Args:
            base_name: Base name
            output_dir: Output directory
        """
        work_files = [
            f"{base_name}_title.txt",
            f"{base_name}_metadata.md",
            f"{base_name}_summary.md",
            f"{base_name}_description.md",
            f"{base_name}_chapters.json",
            f"{base_name}_transcript.vtt",
            f"{base_name}_transcript_dedup.md",
            f"{base_name}_transcript_no_timestamps.txt",
            f"{base_name}_transcript_paragraphs.md",
            f"{base_name}_transcript_cleaned.md",
            f"{base_name}_transcript.md"
        ]

        for work_file in work_files:
            file_path = output_dir / work_file
            if self.fs.exists(file_path):
                self.fs.remove(file_path)

        print("Cleaned up intermediate work files")

    def finalize(
        self,
        base_name: str,
        output_dir: Path,
        debug: bool = False
    ) -> Path:
        """
        Create final markdown file and cleanup.

        Args:
            base_name: Base name (youtube_{VIDEO_ID})
            output_dir: Output directory
            debug: If True, keep intermediate files

        Returns:
            Path to final file

        Raises:
            FileOperationError: If finalization fails
        """
        # Get script directory for template
        script_dir = Path(__file__).parent

        # Read template
        template = self.read_template(script_dir)

        # Assemble final content
        final_content = self.assemble_final_content(template, base_name, output_dir)

        # Create final filename
        final_filename = self.create_final_filename(base_name, output_dir)
        final_path = output_dir / final_filename

        # Write final file
        self.fs.write_text(final_path, final_content)
        print(f"Created final file: {final_filename}")

        # Clean up intermediate work files unless --debug is set
        if debug:
            print("Debug mode: keeping intermediate work files")
        else:
            self.cleanup_work_files(base_name, output_dir)

        print(f"Final file: {final_filename}")
        return final_path


def main() -> None:
    """CLI entry point."""
    # Parse options
    debug = False
    args = []
    for arg in sys.argv[1:]:
        if arg == '--debug':
            debug = True
        else:
            args.append(arg)

    # Parse arguments
    if len(args) < 1:
        print("ERROR: No BASE_NAME provided", file=sys.stderr)
        print("Usage: finalize.py [--debug] <BASE_NAME> <OUTPUT_DIR>", file=sys.stderr)
        sys.exit(1)

    base_name = args[0]
    output_dir = Path(args[1]) if len(args) > 1 else Path(".")

    try:
        finalizer = Finalizer()
        finalizer.finalize(base_name, output_dir, debug)
    except Exception as e:
        print(f"ERROR: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
