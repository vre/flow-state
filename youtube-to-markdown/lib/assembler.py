"""Final assembly library for YouTube to Markdown conversion."""

import re
import sys
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

    def get_filenames(self, base_name: str, output_dir: Path) -> tuple[str | None, str, str | None]:
        """Get cleaned title, video ID, and upload date for filename generation."""
        title_path = output_dir / f"{base_name}_title.txt"
        title = self.read_component_or_empty(title_path).strip()
        video_id = base_name.replace("youtube_", "")

        cleaned_title = clean_title_for_filename(title) if title else None

        upload_date_path = output_dir / f"{base_name}_upload_date.txt"
        upload_date = self.read_component_or_empty(upload_date_path).strip() or None
        if upload_date == "Unknown":
            upload_date = None

        return cleaned_title, video_id, upload_date

    @staticmethod
    def build_filename(upload_date: str | None, cleaned_title: str, video_id: str, suffix: str = "") -> str:
        """Build final filename from components.

        Args:
            upload_date: Upload date (YYYY-MM-DD) or None
            cleaned_title: Cleaned title string
            video_id: YouTube video ID
            suffix: Optional suffix like " - transcript" or " - comments"
        """
        if upload_date:
            return f"{upload_date} - youtube - {cleaned_title}{suffix} ({video_id}).md"
        return f"youtube - {cleaned_title}{suffix} ({video_id}).md"

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

        Falls back to dedup transcript, then legacy no-timestamps transcript.
        Note: Description is pre-wrapped in safety delimiters at extraction time.
        """
        description = self.read_component_or_empty(output_dir / f"{base_name}_description.md")
        transcription = self.read_component_or_empty(output_dir / f"{base_name}_transcript.md")
        if not transcription.strip():
            transcription = self.read_component_or_empty(output_dir / f"{base_name}_transcript_dedup.md")
        if not transcription.strip():
            transcription = self.read_component_or_empty(output_dir / f"{base_name}_transcript_no_timestamps.txt")

        transcript_content = template.replace("{description}", description.strip())
        transcript_content = transcript_content.replace("{transcription}", transcription.strip())

        return transcript_content

    def _save_raw_transcript(
        self,
        base_name: str,
        output_dir: Path,
        template_dir: Path,
        cleaned_title: str | None,
        video_id: str,
        upload_date: str | None,
    ) -> Path | None:
        """Save raw transcript as final transcript file if content available."""
        raw = self.read_component_or_empty(output_dir / f"{base_name}_transcript_dedup.md")
        if not raw.strip():
            raw = self.read_component_or_empty(output_dir / f"{base_name}_transcript_no_timestamps.txt")
        if not raw.strip():
            return None

        template = self.read_template(template_dir, "transcript.md")
        content = self.assemble_transcript_content(template, base_name, output_dir)

        if cleaned_title:
            filename = self.build_filename(upload_date, cleaned_title, video_id, " - transcript")
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

    def replace_comment_insights_in_summary(self, summary_path: Path, comment_insights: str) -> None:
        """Replace existing Comment Insights section in summary, or append if none exists.

        Finds '## Comment Insights' heading and replaces everything from there
        to next '## ' heading (or end of file). Preserves sections after insights
        like Hidden Gems.
        """
        if not self.fs.exists(summary_path):
            return

        content = self.fs.read_text(summary_path)
        marker = "## Comment Insights"

        idx = content.find(marker)
        if idx == -1:
            # No existing insights — append
            if comment_insights.strip():
                self.fs.write_text(summary_path, content.rstrip() + f"\n\n{comment_insights.strip()}\n")
                print(f"Inserted Comment Insights into summary file: {summary_path.name}")
            return

        # Find end of insights section: next ## heading or end of file
        after_marker = content[idx + len(marker) :]
        next_heading = after_marker.find("\n## ")
        if next_heading != -1:
            tail = after_marker[next_heading:]
        else:
            tail = ""

        before = content[:idx].rstrip()
        if comment_insights.strip():
            updated = before + f"\n\n{comment_insights.strip()}" + tail
        else:
            updated = before + tail

        self.fs.write_text(summary_path, updated.rstrip() + "\n")
        print(f"Replaced Comment Insights in summary file: {summary_path.name}")

    def find_existing_summary(self, video_id: str, output_dir: Path) -> Path | None:
        """Find existing summary file by video ID pattern."""
        pattern = f"*({video_id}).md"
        matches = self.fs.glob(pattern, output_dir)
        # Exclude transcript and comments files
        for match in matches:
            name = match.name
            if " - transcript " not in name and " - comments " not in name and " - watch guide " not in name:
                return match
        return None

    @staticmethod
    def _slugify_heading(heading: str) -> str:
        """Convert heading text to a GitHub-style anchor slug."""
        normalized = re.sub(r"\s+", " ", heading).strip().lower()
        slug = re.sub(r"[^\w\s-]", "", normalized).strip().replace(" ", "-")
        return slug or "section"

    def _first_heading_slug_map(self, transcript_content: str) -> dict[str, str]:
        """Build heading->first-slug map from transcript markdown headings."""
        slug_counts: dict[str, int] = {}
        first_by_heading: dict[str, str] = {}

        for line in transcript_content.splitlines():
            match = re.match(r"^#{3,6}\s+(.+?)\s*$", line)
            if not match:
                continue

            heading = match.group(1).strip()
            base_slug = self._slugify_heading(heading)
            seen = slug_counts.get(base_slug, 0)
            slug = base_slug if seen == 0 else f"{base_slug}-{seen}"
            slug_counts[base_slug] = seen + 1

            if heading not in first_by_heading:
                first_by_heading[heading] = slug

        return first_by_heading

    def _replace_watch_guide_cross_links(
        self,
        watch_guide: str,
        transcript_filename: str,
        first_slug_by_heading: dict[str, str],
    ) -> str:
        """Replace cross-link markers with transcript links.

        Cross-link markers use exact lines in form: `→ Heading Name`.
        """
        output_lines: list[str] = []
        pattern = re.compile(r"^→ (.+)$")

        for line in watch_guide.splitlines():
            match = pattern.match(line)
            if not match:
                output_lines.append(line)
                continue

            heading = match.group(1).strip()
            slug = first_slug_by_heading.get(heading)
            if not slug:
                print(f"WARNING: unresolved transcript heading in watch guide: {heading}", file=sys.stderr)
                output_lines.append(line)
                continue

            output_lines.append(f"  Transcript: [{heading}]({transcript_filename}#{slug})")

        return "\n".join(output_lines)

    def _save_watch_guide(
        self,
        base_name: str,
        output_dir: Path,
        template_dir: Path,
        cleaned_title: str | None,
        video_id: str,
        upload_date: str | None,
        transcript_filename: str,
    ) -> Path | None:
        """Save watch guide file when verdict is WATCH or SKIM."""
        watch_guide_path = output_dir / f"{base_name}_watch_guide.md"
        watch_guide = self.read_component_or_empty(watch_guide_path)
        if not watch_guide.strip():
            return None

        lines = watch_guide.splitlines()
        first_line = lines[0].strip() if lines else ""

        if first_line.startswith("READ-ONLY:"):
            return None
        if not (first_line.startswith("WATCH:") or first_line.startswith("SKIM:")):
            print("WARNING: unparseable watch guide verdict, skipping file creation", file=sys.stderr)
            return None

        transcript_path = output_dir / transcript_filename
        transcript_content = self.read_component_or_empty(transcript_path)
        first_slug_by_heading = self._first_heading_slug_map(transcript_content)
        processed_watch_guide = self._replace_watch_guide_cross_links(
            watch_guide,
            transcript_filename,
            first_slug_by_heading,
        )

        template = self.read_template(template_dir, "watch_guide.md")
        content = template.replace("{watch_guide}", processed_watch_guide.strip())

        if cleaned_title:
            filename = self.build_filename(upload_date, cleaned_title, video_id, " - watch guide")
        else:
            filename = f"{base_name}_watch_guide.md"

        final_path = output_dir / filename
        self.fs.write_text(final_path, content)
        print(f"Created watch guide file: {filename}")
        return final_path

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
        cleaned_title, video_id, upload_date = self.get_filenames(base_name, output_dir)

        if cleaned_title:
            filename = self.build_filename(upload_date, cleaned_title, video_id)
        else:
            filename = f"{base_name}.md"

        output_path = output_dir / filename
        self.fs.write_text(output_path, content)
        print(f"Created summary file: {filename}")

        transcript_path = self._save_raw_transcript(base_name, output_dir, template_dir, cleaned_title, video_id, upload_date)

        if not debug:
            self.cleanup_work_files(get_summary_work_files(base_name), output_dir)

        return output_path, transcript_path

    def finalize_transcript_only(self, base_name: str, output_dir: Path, template_dir: Path, debug: bool = False) -> Path:
        """Create only transcript file."""
        template = self.read_template(template_dir, "transcript.md")

        content = self.assemble_transcript_content(template, base_name, output_dir)
        cleaned_title, video_id, upload_date = self.get_filenames(base_name, output_dir)

        if cleaned_title:
            filename = self.build_filename(upload_date, cleaned_title, video_id, " - transcript")
        else:
            filename = f"{base_name}_transcript.md"

        output_path = output_dir / filename
        self.fs.write_text(output_path, content)
        print(f"Created transcript file: {filename}")

        if not debug:
            self.cleanup_work_files(get_transcript_work_files(base_name), output_dir)

        return output_path

    def update_comments(self, base_name: str, output_dir: Path, template_dir: Path, debug: bool = False) -> tuple[Path, Path]:
        """Re-extract comments: replace insights in existing summary, create comments file without insights."""
        cleaned_title, video_id, upload_date = self.get_filenames(base_name, output_dir)

        # Find existing summary
        summary_path = self.find_existing_summary(video_id, output_dir)
        if summary_path is None:
            raise FileOperationError(f"No existing summary file found for video {video_id}")

        # Replace comment insights in summary
        comment_insights = self.read_component_or_empty(output_dir / f"{base_name}_comment_insights_tight.md")
        self.replace_comment_insights_in_summary(summary_path, comment_insights)

        # Create comments file (without insights — uses non-standalone template)
        comments_template = self.read_template(template_dir, "comments.md")
        comments_content = self.assemble_comments_content(comments_template, base_name, output_dir, standalone=False)

        if cleaned_title:
            comments_filename = self.build_filename(upload_date, cleaned_title, video_id, " - comments")
        else:
            comments_filename = f"{base_name}_comments.md"

        comments_path = output_dir / comments_filename
        self.fs.write_text(comments_path, comments_content)
        print(f"Created comments file: {comments_filename}")

        if not debug:
            self.cleanup_work_files(get_comments_work_files(base_name), output_dir)

        return summary_path, comments_path

    def finalize_comments_only(self, base_name: str, output_dir: Path, template_dir: Path, debug: bool = False) -> Path:
        """Create only comments file (standalone with insights)."""
        template = self.read_template(template_dir, "comments_standalone.md")

        content = self.assemble_comments_content(template, base_name, output_dir, standalone=True)
        cleaned_title, video_id, upload_date = self.get_filenames(base_name, output_dir)

        if cleaned_title:
            filename = self.build_filename(upload_date, cleaned_title, video_id, " - comments")
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
        cleaned_title, video_id, upload_date = self.get_filenames(base_name, output_dir)

        if cleaned_title:
            summary_filename = self.build_filename(upload_date, cleaned_title, video_id)
            comments_filename = self.build_filename(upload_date, cleaned_title, video_id, " - comments")
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

        transcript_path = self._save_raw_transcript(base_name, output_dir, template_dir, cleaned_title, video_id, upload_date)

        if not debug:
            work_files = get_summary_work_files(base_name) + get_comments_work_files(base_name)
            self.cleanup_work_files(work_files, output_dir)

        return summary_path, comments_path, transcript_path

    def finalize_full(self, base_name: str, output_dir: Path, template_dir: Path, debug: bool = False) -> tuple[Path, Path, Path]:
        """Create summary, transcript, and comments files."""
        cleaned_title, video_id, upload_date = self.get_filenames(base_name, output_dir)

        if cleaned_title:
            summary_filename = self.build_filename(upload_date, cleaned_title, video_id)
            transcript_filename = self.build_filename(upload_date, cleaned_title, video_id, " - transcript")
            comments_filename = self.build_filename(upload_date, cleaned_title, video_id, " - comments")
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

        self._save_watch_guide(
            base_name=base_name,
            output_dir=output_dir,
            template_dir=template_dir,
            cleaned_title=cleaned_title,
            video_id=video_id,
            upload_date=upload_date,
            transcript_filename=transcript_filename,
        )

        comments_template = self.read_template(template_dir, "comments.md")
        comments_content = self.assemble_comments_content(comments_template, base_name, output_dir, standalone=False)
        comments_path = output_dir / comments_filename
        self.fs.write_text(comments_path, comments_content)
        print(f"Created comments file: {comments_filename}")

        if not debug:
            self.cleanup_work_files(get_all_work_files(base_name), output_dir)

        return summary_path, transcript_path, comments_path
