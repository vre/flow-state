"""Final assembly library for YouTube to Markdown conversion."""

from pathlib import Path

from lib.intermediate_files import (
    get_all_work_files,
    get_comments_work_files,
    get_summary_work_files,
    get_transcript_work_files,
)
from lib.shared_types import (
    FileOperationError,
    FileSystem,
    RealFileSystem,
    clean_title_for_filename,
)


class Finalizer:
    """Finalizes YouTube to Markdown conversion."""

    def __init__(self, fs: FileSystem = RealFileSystem()):
        self.fs = fs

    def read_template(self, template_dir: Path, template_name: str) -> str:
        """Read template file."""
        template_file = template_dir / template_name
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
            stripped = stripped[len(header) :].lstrip()
        return stripped

    def get_filenames(self, base_name: str, output_dir: Path) -> tuple[str | None, str]:
        """Get cleaned title and video ID for filename generation."""
        title_path = output_dir / f"{base_name}_title.txt"
        title = self.read_component_or_empty(title_path).strip()
        video_id = base_name.replace("youtube_", "")

        if title:
            cleaned_title = clean_title_for_filename(title)
        else:
            cleaned_title = None

        return cleaned_title, video_id

    def assemble_summary_content(self, template: str, base_name: str, output_dir: Path) -> str:
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

    def assemble_transcript_content(self, template: str, base_name: str, output_dir: Path) -> str:
        """Assemble transcript content from template and components.

        Falls back to raw transcript_no_timestamps if polished transcript not available.
        Note: Description is pre-wrapped in safety delimiters at extraction time.
        """
        description = self.read_component_or_empty(output_dir / f"{base_name}_description.md")
        transcription = self.read_component_or_empty(output_dir / f"{base_name}_transcript.md")
        if not transcription.strip():
            transcription = self.read_component_or_empty(output_dir / f"{base_name}_transcript_no_timestamps.txt")

        transcript_content = template.replace("{description}", description.strip())
        transcript_content = transcript_content.replace("{transcription}", transcription.strip())

        return transcript_content

    def _save_raw_transcript(
        self, base_name: str, output_dir: Path, template_dir: Path, cleaned_title: str | None, video_id: str
    ) -> Path | None:
        """Save raw transcript as final transcript file if content available."""
        raw = self.read_component_or_empty(output_dir / f"{base_name}_transcript_no_timestamps.txt")
        if not raw.strip():
            return None

        template = self.read_template(template_dir, "transcript.md")
        content = self.assemble_transcript_content(template, base_name, output_dir)

        if cleaned_title:
            filename = f"youtube - {cleaned_title} - transcript ({video_id}).md"
        else:
            filename = f"{base_name}_transcript.md"

        transcript_path = output_dir / filename
        self.fs.write_text(transcript_path, content)
        print(f"Created transcript file: {filename}")
        return transcript_path

    def assemble_comments_content(self, template: str, base_name: str, output_dir: Path, standalone: bool = False) -> str:
        """Assemble comments content from template and components.

        Note: Comments are pre-wrapped in safety delimiters at extraction time.
        """
        comment_insights = self.read_component_or_empty(output_dir / f"{base_name}_comment_insights_tight.md")
        comments = self.read_component_or_empty(output_dir / f"{base_name}_comments_prefiltered.md")

        if standalone:
            content = template.replace("{comment_insights}", comment_insights.strip())
        else:
            content = template

        content = content.replace("{comments}", comments.strip())
        return content

    def insert_comment_insights_into_summary(self, summary_path: Path, comment_insights: str) -> None:
        """Insert Comment Insights section into existing summary file at end."""
        if not self.fs.exists(summary_path) or not comment_insights.strip():
            return

        content = self.fs.read_text(summary_path)
        insights_section = f"\n\n{comment_insights.strip()}\n"
        updated_content = content.rstrip() + insights_section

        self.fs.write_text(summary_path, updated_content)
        print(f"Inserted Comment Insights into summary file: {summary_path.name}")

    def cleanup_work_files(self, work_files: list[str], output_dir: Path) -> None:
        """Remove intermediate work files."""
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

    def finalize_summary_only(self, base_name: str, output_dir: Path, template_dir: Path, debug: bool = False) -> tuple[Path, Path | None]:
        """Create summary file and raw transcript file."""
        template = self.read_template(template_dir, "summary.md")

        content = self.assemble_summary_content(template, base_name, output_dir)
        cleaned_title, video_id = self.get_filenames(base_name, output_dir)

        if cleaned_title:
            filename = f"youtube - {cleaned_title} ({video_id}).md"
        else:
            filename = f"{base_name}.md"

        output_path = output_dir / filename
        self.fs.write_text(output_path, content)
        print(f"Created summary file: {filename}")

        transcript_path = self._save_raw_transcript(base_name, output_dir, template_dir, cleaned_title, video_id)

        if not debug:
            self.cleanup_work_files(get_summary_work_files(base_name), output_dir)

        return output_path, transcript_path

    def finalize_transcript_only(self, base_name: str, output_dir: Path, template_dir: Path, debug: bool = False) -> Path:
        """Create only transcript file."""
        template = self.read_template(template_dir, "transcript.md")

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
            self.cleanup_work_files(get_transcript_work_files(base_name), output_dir)

        return output_path

    def finalize_comments_only(self, base_name: str, output_dir: Path, template_dir: Path, debug: bool = False) -> Path:
        """Create only comments file (standalone with insights)."""
        template = self.read_template(template_dir, "comments_standalone.md")

        content = self.assemble_comments_content(template, base_name, output_dir, standalone=True)

        name_path = output_dir / f"{base_name}_name.txt"
        title = self.read_component_or_empty(name_path).strip()
        video_id = base_name.replace("youtube_", "")

        if title:
            cleaned_title = clean_title_for_filename(title)
            filename = f"youtube - {cleaned_title} - comments ({video_id}).md"
        else:
            filename = f"{base_name}_comments.md"

        output_path = output_dir / filename
        self.fs.write_text(output_path, content)
        print(f"Created comments file: {filename}")

        if not debug:
            self.cleanup_work_files(get_comments_work_files(base_name), output_dir)

        return output_path

    def finalize_summary_comments(
        self, base_name: str, output_dir: Path, template_dir: Path, debug: bool = False
    ) -> tuple[Path, Path, Path | None]:
        """Create summary, comments, and raw transcript files. Insert insights into summary."""
        summary_template = self.read_template(template_dir, "summary.md")
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

        comment_insights = self.read_component_or_empty(output_dir / f"{base_name}_comment_insights_tight.md")
        self.insert_comment_insights_into_summary(summary_path, comment_insights)

        comments_template = self.read_template(template_dir, "comments.md")
        comments_content = self.assemble_comments_content(comments_template, base_name, output_dir, standalone=False)

        comments_path = output_dir / comments_filename
        self.fs.write_text(comments_path, comments_content)
        print(f"Created comments file: {comments_filename}")

        transcript_path = self._save_raw_transcript(base_name, output_dir, template_dir, cleaned_title, video_id)

        if not debug:
            work_files = get_summary_work_files(base_name) + get_comments_work_files(base_name)
            self.cleanup_work_files(work_files, output_dir)

        return summary_path, comments_path, transcript_path

    def finalize_full(self, base_name: str, output_dir: Path, template_dir: Path, debug: bool = False) -> tuple[Path, Path, Path]:
        """Create summary, transcript, and comments files."""
        cleaned_title, video_id = self.get_filenames(base_name, output_dir)

        if cleaned_title:
            summary_filename = f"youtube - {cleaned_title} ({video_id}).md"
            transcript_filename = f"youtube - {cleaned_title} - transcript ({video_id}).md"
            comments_filename = f"youtube - {cleaned_title} - comments ({video_id}).md"
        else:
            summary_filename = f"{base_name}.md"
            transcript_filename = f"{base_name}_transcript.md"
            comments_filename = f"{base_name}_comments.md"

        summary_template = self.read_template(template_dir, "summary.md")
        summary_content = self.assemble_summary_content(summary_template, base_name, output_dir)
        summary_path = output_dir / summary_filename
        self.fs.write_text(summary_path, summary_content)
        print(f"Created summary file: {summary_filename}")

        comment_insights = self.read_component_or_empty(output_dir / f"{base_name}_comment_insights_tight.md")
        self.insert_comment_insights_into_summary(summary_path, comment_insights)

        transcript_template = self.read_template(template_dir, "transcript.md")
        transcript_content = self.assemble_transcript_content(transcript_template, base_name, output_dir)
        transcript_path = output_dir / transcript_filename
        self.fs.write_text(transcript_path, transcript_content)
        print(f"Created transcript file: {transcript_filename}")

        comments_template = self.read_template(template_dir, "comments.md")
        comments_content = self.assemble_comments_content(comments_template, base_name, output_dir, standalone=False)
        comments_path = output_dir / comments_filename
        self.fs.write_text(comments_path, comments_content)
        print(f"Created comments file: {comments_filename}")

        if not debug:
            self.cleanup_work_files(get_all_work_files(base_name), output_dir)

        return summary_path, transcript_path, comments_path
