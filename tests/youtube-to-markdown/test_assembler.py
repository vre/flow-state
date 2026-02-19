"""Tests for finalize.py."""

from pathlib import Path

import pytest
from lib.assembler import Finalizer
from lib.shared_types import FileOperationError


class MockFileSystem:
    """Mock file system for testing."""

    def __init__(self):
        self.files: dict[Path, str] = {}
        self.directories: set[Path] = set()

    def read_text(self, path: Path, encoding: str = "utf-8") -> str:
        if path not in self.files:
            raise FileNotFoundError(f"{path} not found")
        return self.files[path]

    def write_text(self, path: Path, content: str, encoding: str = "utf-8") -> None:
        self.files[path] = content

    def exists(self, path: Path) -> bool:
        return path in self.files or path in self.directories

    def mkdir(self, path: Path, parents: bool = True, exist_ok: bool = True) -> None:
        self.directories.add(path)

    def remove(self, path: Path) -> None:
        if path in self.files:
            del self.files[path]

    def glob(self, pattern: str, directory: Path) -> list[Path]:
        import fnmatch

        results = []
        for file_path in self.files.keys():
            if file_path.parent == directory:
                if fnmatch.fnmatch(file_path.name, pattern):
                    results.append(file_path)
        return results


@pytest.fixture
def mock_fs():
    """Provide mock file system."""
    return MockFileSystem()


@pytest.fixture
def finalizer(mock_fs):
    """Provide Finalizer with mock file system."""
    return Finalizer(fs=mock_fs)


class TestReadTemplate:
    """Tests for read_template method."""

    def test_read_template_success(self, finalizer, mock_fs):
        """Test reading existing template."""
        script_dir = Path("/scripts")
        mock_fs.files[script_dir / "template.md"] = "Template content"

        result = finalizer.read_template(script_dir, "template.md")

        assert result == "Template content"

    def test_read_template_not_found(self, finalizer, mock_fs):
        """Test reading non-existent template raises error."""
        script_dir = Path("/scripts")

        with pytest.raises(FileOperationError) as exc_info:
            finalizer.read_template(script_dir, "missing.md")

        assert "not found" in str(exc_info.value)


class TestReadComponentOrEmpty:
    """Tests for read_component_or_empty method."""

    def test_read_existing_component(self, finalizer, mock_fs):
        """Test reading existing component file."""
        path = Path("/output/component.md")
        mock_fs.files[path] = "Component content"

        result = finalizer.read_component_or_empty(path)

        assert result == "Component content"

    def test_read_missing_component_returns_empty(self, finalizer, mock_fs):
        """Test reading non-existent component returns empty string."""
        path = Path("/output/missing.md")

        result = finalizer.read_component_or_empty(path)

        assert result == ""


class TestStripLeadingHeader:
    """Tests for strip_leading_header method."""

    def test_strip_matching_header(self, finalizer):
        """Test stripping matching header."""
        content = "## Summary\n\nActual content here"

        result = finalizer.strip_leading_header(content, "## Summary")

        assert result == "Actual content here"

    def test_strip_no_matching_header(self, finalizer):
        """Test content without matching header is unchanged."""
        content = "## Other\n\nActual content here"

        result = finalizer.strip_leading_header(content, "## Summary")

        assert result == "## Other\n\nActual content here"

    def test_strip_empty_content(self, finalizer):
        """Test empty content returns empty."""
        result = finalizer.strip_leading_header("", "## Summary")

        assert result == ""


class TestGetFilenames:
    """Tests for get_filenames method."""

    def test_get_filenames_with_title_and_date(self, finalizer, mock_fs):
        """Test getting filenames when title and upload date exist."""
        output_dir = Path("/output")
        mock_fs.files[output_dir / "youtube_abc123_title.txt"] = "Test Video Title"
        mock_fs.files[output_dir / "youtube_abc123_upload_date.txt"] = "2024-01-15"

        cleaned_title, video_id, upload_date = finalizer.get_filenames("youtube_abc123", output_dir)

        assert cleaned_title == "Test Video Title"
        assert video_id == "abc123"
        assert upload_date == "2024-01-15"

    def test_get_filenames_without_title(self, finalizer, mock_fs):
        """Test getting filenames when title doesn't exist."""
        output_dir = Path("/output")

        cleaned_title, video_id, upload_date = finalizer.get_filenames("youtube_abc123", output_dir)

        assert cleaned_title is None
        assert video_id == "abc123"
        assert upload_date is None

    def test_get_filenames_without_upload_date(self, finalizer, mock_fs):
        """Test getting filenames when upload date doesn't exist."""
        output_dir = Path("/output")
        mock_fs.files[output_dir / "youtube_abc123_title.txt"] = "Test Video Title"

        cleaned_title, video_id, upload_date = finalizer.get_filenames("youtube_abc123", output_dir)

        assert cleaned_title == "Test Video Title"
        assert upload_date is None

    def test_get_filenames_unknown_upload_date(self, finalizer, mock_fs):
        """Test that 'Unknown' upload date is treated as None."""
        output_dir = Path("/output")
        mock_fs.files[output_dir / "youtube_abc123_title.txt"] = "Test Video Title"
        mock_fs.files[output_dir / "youtube_abc123_upload_date.txt"] = "Unknown"

        _, _, upload_date = finalizer.get_filenames("youtube_abc123", output_dir)

        assert upload_date is None

    def test_get_filenames_cleans_title(self, finalizer, mock_fs):
        """Test that title is cleaned for filename."""
        output_dir = Path("/output")
        mock_fs.files[output_dir / "youtube_abc123_title.txt"] = "Test: Video? Title!"

        cleaned_title, video_id, _ = finalizer.get_filenames("youtube_abc123", output_dir)

        assert ":" not in cleaned_title
        assert "?" not in cleaned_title


class TestBuildFilename:
    """Tests for build_filename static method."""

    def test_with_date_and_title(self):
        assert Finalizer.build_filename("2024-01-15", "Test Title", "abc123") == "2024-01-15 - youtube - Test Title (abc123).md"

    def test_with_date_title_and_suffix(self):
        assert (
            Finalizer.build_filename("2024-01-15", "Test Title", "abc123", " - transcript")
            == "2024-01-15 - youtube - Test Title - transcript (abc123).md"
        )

    def test_without_date(self):
        assert Finalizer.build_filename(None, "Test Title", "abc123") == "youtube - Test Title (abc123).md"

    def test_without_date_with_suffix(self):
        assert Finalizer.build_filename(None, "Test Title", "abc123", " - comments") == "youtube - Test Title - comments (abc123).md"


class TestAssembleSummaryContent:
    """Tests for assemble_summary_content method."""

    def test_assemble_summary_content(self, finalizer, mock_fs):
        """Test assembling summary content from components."""
        output_dir = Path("/output")
        base_name = "youtube_test123"
        template = "Quick: {quick_summary}\n\nMeta: {metadata}\n\nSum: {summary}"

        mock_fs.files[output_dir / f"{base_name}_quick_summary.md"] = "## Quick Summary\n\nQuick content"
        mock_fs.files[output_dir / f"{base_name}_metadata.md"] = "Metadata content"
        mock_fs.files[output_dir / f"{base_name}_summary_tight.md"] = "## Summary\n\nSummary content"

        result = finalizer.assemble_summary_content(template, base_name, output_dir)

        assert "Quick: Quick content" in result
        assert "Meta: Metadata content" in result
        assert "Sum: Summary content" in result

    def test_assemble_summary_content_missing_components(self, finalizer, mock_fs):
        """Test assembling with missing components uses empty strings."""
        output_dir = Path("/output")
        base_name = "youtube_test123"
        template = "Quick: {quick_summary}\n\nMeta: {metadata}\n\nSum: {summary}"

        result = finalizer.assemble_summary_content(template, base_name, output_dir)

        assert "Quick:" in result
        assert "Meta:" in result
        assert "Sum:" in result


class TestAssembleTranscriptContent:
    """Tests for assemble_transcript_content method."""

    def test_assemble_transcript_content(self, finalizer, mock_fs):
        """Test assembling transcript content (pre-wrapped at extraction)."""
        output_dir = Path("/output")
        base_name = "youtube_test123"
        template = "Desc: {description}\n\nTrans: {transcription}"

        # Content is pre-wrapped at extraction time
        mock_fs.files[output_dir / f"{base_name}_description.md"] = "[UNTRUSTED]\n\n<|description|>\nDescription here\n<|/description|>"
        mock_fs.files[output_dir / f"{base_name}_transcript.md"] = "Transcript here"

        result = finalizer.assemble_transcript_content(template, base_name, output_dir)

        # Pre-wrapped content passes through
        assert "<|description|>" in result
        assert "Description here" in result
        assert "Transcript here" in result

    def test_assemble_transcript_content_empty_components(self, finalizer, mock_fs):
        """Test assembling with empty components."""
        output_dir = Path("/output")
        base_name = "youtube_test123"
        template = "Desc: {description}\n\nTrans: {transcription}"

        # No files = empty content
        result = finalizer.assemble_transcript_content(template, base_name, output_dir)

        assert "Desc:" in result
        assert "Trans:" in result


class TestAssembleCommentsContent:
    """Tests for assemble_comments_content method."""

    def test_assemble_comments_standalone(self, finalizer, mock_fs):
        """Test assembling comments in standalone mode (pre-wrapped at extraction)."""
        output_dir = Path("/output")
        base_name = "youtube_test123"
        template = "Insights: {comment_insights}\n\nComments: {comments}"

        mock_fs.files[output_dir / f"{base_name}_comment_insights_tight.md"] = "Insights here"
        # Comments are pre-wrapped at extraction time
        mock_fs.files[output_dir / f"{base_name}_comments_prefiltered.md"] = "[UNTRUSTED]\n\n<|comments|>\nComments here\n<|/comments|>"

        result = finalizer.assemble_comments_content(template, base_name, output_dir, standalone=True)

        # Insights are LLM-generated, not wrapped
        assert "Insights: Insights here" in result
        # Pre-wrapped comments pass through
        assert "<|comments|>" in result
        assert "Comments here" in result

    def test_assemble_comments_not_standalone(self, finalizer, mock_fs):
        """Test assembling comments not standalone (pre-wrapped at extraction)."""
        output_dir = Path("/output")
        base_name = "youtube_test123"
        template = "Comments: {comments}"

        # Comments are pre-wrapped at extraction time
        mock_fs.files[output_dir / f"{base_name}_comments_prefiltered.md"] = "[UNTRUSTED]\n\n<|comments|>\nComments here\n<|/comments|>"

        result = finalizer.assemble_comments_content(template, base_name, output_dir, standalone=False)

        # Pre-wrapped comments pass through
        assert "<|comments|>" in result
        assert "Comments here" in result

    def test_assemble_comments_empty(self, finalizer, mock_fs):
        """Test empty comments."""
        output_dir = Path("/output")
        base_name = "youtube_test123"
        template = "Comments: {comments}"

        # No files = empty comments
        result = finalizer.assemble_comments_content(template, base_name, output_dir, standalone=False)

        assert "Comments:" in result


class TestInsertCommentInsightsIntoSummary:
    """Tests for insert_comment_insights_into_summary method."""

    def test_insert_insights(self, finalizer, mock_fs):
        """Test inserting comment insights into existing summary."""
        summary_path = Path("/output/summary.md")
        mock_fs.files[summary_path] = "Summary content"

        finalizer.insert_comment_insights_into_summary(summary_path, "## Comment Insights\n\nInsights here")

        assert "Summary content" in mock_fs.files[summary_path]
        assert "Comment Insights" in mock_fs.files[summary_path]

    def test_insert_empty_insights_does_nothing(self, finalizer, mock_fs):
        """Test that empty insights doesn't modify file."""
        summary_path = Path("/output/summary.md")
        mock_fs.files[summary_path] = "Summary content"

        finalizer.insert_comment_insights_into_summary(summary_path, "  ")

        assert mock_fs.files[summary_path] == "Summary content"

    def test_insert_to_missing_file_does_nothing(self, finalizer, mock_fs):
        """Test that missing summary file doesn't raise error."""
        summary_path = Path("/output/missing.md")

        # Should not raise
        finalizer.insert_comment_insights_into_summary(summary_path, "Insights")


class TestGetWorkFiles:
    """Tests for get_*_work_files functions from intermediate_files module."""

    def test_get_summary_work_files(self):
        """Test getting summary work files list."""
        from lib.intermediate_files import get_summary_work_files

        files = get_summary_work_files("youtube_test123")

        assert "youtube_test123_title.txt" in files
        assert "youtube_test123_metadata.md" in files
        assert "youtube_test123_summary_tight.md" in files

    def test_get_transcript_work_files(self):
        """Test getting transcript work files list."""
        from lib.intermediate_files import get_transcript_work_files

        files = get_transcript_work_files("youtube_test123")

        assert "youtube_test123_transcript.md" in files
        assert "youtube_test123_description.md" in files

    def test_get_comments_work_files(self):
        """Test getting comments work files list."""
        from lib.intermediate_files import get_comments_work_files

        files = get_comments_work_files("youtube_test123")

        assert "youtube_test123_comments.md" in files
        assert "youtube_test123_comment_insights_tight.md" in files

    def test_get_all_work_files_combines_all(self):
        """Test getting all work files combines all lists."""
        from lib.intermediate_files import (
            get_all_work_files,
            get_comments_work_files,
            get_summary_work_files,
            get_transcript_work_files,
        )

        full_files = get_all_work_files("youtube_test123")
        summary_files = get_summary_work_files("youtube_test123")
        transcript_files = get_transcript_work_files("youtube_test123")
        comments_files = get_comments_work_files("youtube_test123")

        for f in summary_files:
            assert f in full_files
        for f in transcript_files:
            assert f in full_files
        for f in comments_files:
            assert f in full_files


class TestCleanupWorkFiles:
    """Tests for cleanup_work_files method."""

    def test_cleanup_removes_existing_files(self, finalizer, mock_fs):
        """Test cleanup removes existing work files."""
        output_dir = Path("/output")
        mock_fs.files[output_dir / "file1.txt"] = "content"
        mock_fs.files[output_dir / "file2.txt"] = "content"

        finalizer.cleanup_work_files(["file1.txt", "file2.txt"], output_dir)

        assert output_dir / "file1.txt" not in mock_fs.files
        assert output_dir / "file2.txt" not in mock_fs.files

    def test_cleanup_ignores_missing_files(self, finalizer, mock_fs):
        """Test cleanup doesn't error on missing files."""
        output_dir = Path("/output")

        # Should not raise
        finalizer.cleanup_work_files(["missing.txt"], output_dir)

    def test_cleanup_deduplicates_files(self, finalizer, mock_fs):
        """Test cleanup handles duplicate file names."""
        output_dir = Path("/output")
        mock_fs.files[output_dir / "file1.txt"] = "content"

        # Same file listed twice should only be removed once
        finalizer.cleanup_work_files(["file1.txt", "file1.txt"], output_dir)

        assert output_dir / "file1.txt" not in mock_fs.files


class TestFinalizeSummaryOnly:
    """Tests for finalize_summary_only method."""

    def test_creates_file_with_title_and_date(self, finalizer, mock_fs):
        """Test finalize_summary_only creates summary file with date prefix."""
        output_dir = Path("/output")
        base_name = "youtube_abc123"
        template_dir = Path("/templates")

        mock_fs.files[template_dir / "summary.md"] = "{quick_summary}\n{metadata}\n{summary}"
        mock_fs.files[output_dir / f"{base_name}_title.txt"] = "Test Title"
        mock_fs.files[output_dir / f"{base_name}_upload_date.txt"] = "2024-01-15"
        mock_fs.files[output_dir / f"{base_name}_quick_summary.md"] = "Quick"
        mock_fs.files[output_dir / f"{base_name}_metadata.md"] = "Meta"
        mock_fs.files[output_dir / f"{base_name}_summary_tight.md"] = "Summary"

        result = finalizer.finalize_summary_only(base_name, output_dir, template_dir, debug=True)
        assert "2024-01-15 - youtube - Test Title (abc123).md" in str(result)

    def test_creates_file_without_title(self, finalizer, mock_fs):
        """Test finalize_summary_only creates summary file without title."""
        output_dir = Path("/output")
        base_name = "youtube_abc123"
        template_dir = Path("/templates")

        mock_fs.files[template_dir / "summary.md"] = "{quick_summary}\n{metadata}\n{summary}"

        result = finalizer.finalize_summary_only(base_name, output_dir, template_dir, debug=True)
        assert f"{base_name}.md" in str(result)


class TestFinalizeTranscriptOnly:
    """Tests for finalize_transcript_only method."""

    def test_creates_transcript_file_with_date(self, finalizer, mock_fs):
        """Test finalize_transcript_only creates transcript file with date prefix."""
        output_dir = Path("/output")
        base_name = "youtube_abc123"
        template_dir = Path("/templates")

        mock_fs.files[template_dir / "transcript.md"] = "{description}\n{transcription}"
        mock_fs.files[output_dir / f"{base_name}_title.txt"] = "Test Title"
        mock_fs.files[output_dir / f"{base_name}_upload_date.txt"] = "2024-01-15"
        mock_fs.files[output_dir / f"{base_name}_description.md"] = "Desc"
        mock_fs.files[output_dir / f"{base_name}_transcript.md"] = "Trans"

        result = finalizer.finalize_transcript_only(base_name, output_dir, template_dir, debug=True)
        assert "2024-01-15 - youtube - Test Title - transcript (abc123).md" in str(result)


class TestFinalizeCommentsOnly:
    """Tests for finalize_comments_only method."""

    def test_creates_comments_file_with_date(self, finalizer, mock_fs):
        """Test finalize_comments_only creates comments file with date prefix."""
        output_dir = Path("/output")
        base_name = "youtube_abc123"
        template_dir = Path("/templates")

        mock_fs.files[template_dir / "comments_standalone.md"] = "{comment_insights}\n{comments}"
        mock_fs.files[output_dir / f"{base_name}_title.txt"] = "Test Title"
        mock_fs.files[output_dir / f"{base_name}_upload_date.txt"] = "2024-01-15"
        mock_fs.files[output_dir / f"{base_name}_comment_insights_tight.md"] = "Insights"
        mock_fs.files[output_dir / f"{base_name}_comments_prefiltered.md"] = "Comments"

        result = finalizer.finalize_comments_only(base_name, output_dir, template_dir, debug=True)
        assert "2024-01-15 - youtube - Test Title - comments (abc123).md" in str(result)


class TestFinalizeSummaryComments:
    """Tests for finalize_summary_comments method."""

    def test_creates_both_files_with_date(self, finalizer, mock_fs):
        """Test finalize_summary_comments creates files with date prefix."""
        output_dir = Path("/output")
        base_name = "youtube_abc123"
        template_dir = Path("/templates")

        mock_fs.files[template_dir / "summary.md"] = "{quick_summary}\n{metadata}\n{summary}"
        mock_fs.files[template_dir / "comments.md"] = "{comments}"
        mock_fs.files[output_dir / f"{base_name}_title.txt"] = "Test Title"
        mock_fs.files[output_dir / f"{base_name}_upload_date.txt"] = "2024-01-15"
        mock_fs.files[output_dir / f"{base_name}_quick_summary.md"] = "Quick"
        mock_fs.files[output_dir / f"{base_name}_metadata.md"] = "Meta"
        mock_fs.files[output_dir / f"{base_name}_summary_tight.md"] = "Summary"
        mock_fs.files[output_dir / f"{base_name}_comment_insights_tight.md"] = "Insights"
        mock_fs.files[output_dir / f"{base_name}_comments_prefiltered.md"] = "Comments"

        summary_path, comments_path, transcript_path = finalizer.finalize_summary_comments(base_name, output_dir, template_dir, debug=True)
        assert "2024-01-15 - youtube - Test Title (abc123).md" in str(summary_path)
        assert "2024-01-15 - youtube - Test Title - comments (abc123).md" in str(comments_path)
        assert transcript_path is None


class TestFinalizeFull:
    """Tests for finalize_full method."""

    def test_creates_all_three_files_with_date(self, finalizer, mock_fs):
        """Test finalize_full creates all files with date prefix."""
        output_dir = Path("/output")
        base_name = "youtube_abc123"
        template_dir = Path("/templates")

        mock_fs.files[template_dir / "summary.md"] = "{quick_summary}\n{metadata}\n{summary}"
        mock_fs.files[template_dir / "transcript.md"] = "{description}\n{transcription}"
        mock_fs.files[template_dir / "comments.md"] = "{comments}"
        mock_fs.files[output_dir / f"{base_name}_title.txt"] = "Test Title"
        mock_fs.files[output_dir / f"{base_name}_upload_date.txt"] = "2024-01-15"
        mock_fs.files[output_dir / f"{base_name}_quick_summary.md"] = "Quick"
        mock_fs.files[output_dir / f"{base_name}_metadata.md"] = "Meta"
        mock_fs.files[output_dir / f"{base_name}_summary_tight.md"] = "Summary"
        mock_fs.files[output_dir / f"{base_name}_description.md"] = "Desc"
        mock_fs.files[output_dir / f"{base_name}_transcript.md"] = "Trans"
        mock_fs.files[output_dir / f"{base_name}_comment_insights_tight.md"] = "Insights"
        mock_fs.files[output_dir / f"{base_name}_comments_prefiltered.md"] = "Comments"

        summary_path, transcript_path, comments_path = finalizer.finalize_full(base_name, output_dir, template_dir, debug=True)
        assert "2024-01-15 - youtube - Test Title (abc123).md" in str(summary_path)
        assert "2024-01-15 - youtube - Test Title - transcript (abc123).md" in str(transcript_path)
        assert "2024-01-15 - youtube - Test Title - comments (abc123).md" in str(comments_path)

    def test_cleanup_in_non_debug_mode(self, finalizer, mock_fs):
        """Test that work files are cleaned up when not in debug mode."""
        output_dir = Path("/output")
        base_name = "youtube_abc123"
        template_dir = Path("/templates")

        mock_fs.files[template_dir / "summary.md"] = "{quick_summary}\n{metadata}\n{summary}"
        mock_fs.files[template_dir / "transcript.md"] = "{description}\n{transcription}"
        mock_fs.files[template_dir / "comments.md"] = "{comments}"
        mock_fs.files[output_dir / f"{base_name}_title.txt"] = "Test Title"
        mock_fs.files[output_dir / f"{base_name}_upload_date.txt"] = "2024-01-15"
        mock_fs.files[output_dir / f"{base_name}_quick_summary.md"] = "Quick"
        mock_fs.files[output_dir / f"{base_name}_metadata.md"] = "Meta"
        mock_fs.files[output_dir / f"{base_name}_summary_tight.md"] = "Summary"
        mock_fs.files[output_dir / f"{base_name}_description.md"] = "Desc"
        mock_fs.files[output_dir / f"{base_name}_transcript.md"] = "Trans"
        mock_fs.files[output_dir / f"{base_name}_comment_insights_tight.md"] = "Insights"
        mock_fs.files[output_dir / f"{base_name}_comments_prefiltered.md"] = "Comments"

        finalizer.finalize_full(base_name, output_dir, template_dir, debug=False)
        # Work files should be cleaned up
        assert output_dir / f"{base_name}_metadata.md" not in mock_fs.files
        assert output_dir / f"{base_name}_upload_date.txt" not in mock_fs.files


class TestReplaceCommentInsightsInSummary:
    """Tests for replace_comment_insights_in_summary method."""

    def test_replaces_existing_insights(self, finalizer, mock_fs):
        """Test replacing old Comment Insights with new ones."""
        summary_path = Path("/output/summary.md")
        mock_fs.files[summary_path] = (
            "## Summary heading\n\nSummary content\n\n## Comment Insights (old theme)\n\n**Old insight**: old stuff\n"
        )

        finalizer.replace_comment_insights_in_summary(summary_path, "## Comment Insights (new theme)\n\n**New insight**: new stuff")

        result = mock_fs.files[summary_path]
        assert "new stuff" in result
        assert "old stuff" not in result
        assert "Summary content" in result

    def test_appends_when_no_existing_insights(self, finalizer, mock_fs):
        """Test appending insights when summary has none."""
        summary_path = Path("/output/summary.md")
        mock_fs.files[summary_path] = "## Summary heading\n\nSummary content"

        finalizer.replace_comment_insights_in_summary(summary_path, "## Comment Insights (theme)\n\nNew insights")

        result = mock_fs.files[summary_path]
        assert "Summary content" in result
        assert "New insights" in result

    def test_empty_insights_removes_old_section(self, finalizer, mock_fs):
        """Test that empty new insights still removes old section."""
        summary_path = Path("/output/summary.md")
        mock_fs.files[summary_path] = "## Summary heading\n\nContent\n\n## Comment Insights (old)\n\nOld stuff\n"

        finalizer.replace_comment_insights_in_summary(summary_path, "  ")

        result = mock_fs.files[summary_path]
        assert "Old stuff" not in result
        assert "Content" in result

    def test_missing_file_does_nothing(self, finalizer, mock_fs):
        """Test that missing summary file doesn't raise error."""
        summary_path = Path("/output/missing.md")
        finalizer.replace_comment_insights_in_summary(summary_path, "Insights")

    def test_preserves_hidden_gems_after_insights(self, finalizer, mock_fs):
        """Test that Hidden Gems section after insights is preserved."""
        summary_path = Path("/output/summary.md")
        mock_fs.files[summary_path] = (
            "## Summary heading\n\nContent\n\n## Comment Insights (old)\n\nOld insights\n\n## Hidden Gems\n\nGem content\n"
        )

        finalizer.replace_comment_insights_in_summary(summary_path, "## Comment Insights (new)\n\nNew insights")

        result = mock_fs.files[summary_path]
        assert "New insights" in result
        assert "Old insights" not in result
        assert "Gem content" in result


class TestUpdateComments:
    """Tests for update_comments method."""

    def test_updates_existing_summary_and_creates_comments(self, finalizer, mock_fs):
        """Test update_comments inserts insights into summary, creates comments file."""
        output_dir = Path("/output")
        base_name = "youtube_abc123"
        template_dir = Path("/templates")

        # Existing summary file
        summary_filename = "2024-01-15 - youtube - Test Title (abc123).md"
        mock_fs.files[output_dir / summary_filename] = "## Video\n\nMeta\n\n## Summary\n\nContent"

        # Templates and work files
        mock_fs.files[template_dir / "comments.md"] = "## Curated Comments\n\n{comments}"
        mock_fs.files[output_dir / f"{base_name}_title.txt"] = "Test Title"
        mock_fs.files[output_dir / f"{base_name}_upload_date.txt"] = "2024-01-15"
        mock_fs.files[output_dir / f"{base_name}_comment_insights_tight.md"] = "## Comment Insights (theme)\n\nInsights here"
        mock_fs.files[output_dir / f"{base_name}_comments_prefiltered.md"] = "Curated comments here"

        summary_path, comments_path = finalizer.update_comments(base_name, output_dir, template_dir, debug=True)

        # Summary should have insights appended
        assert "Insights here" in mock_fs.files[summary_path]
        assert "Content" in mock_fs.files[summary_path]

        # Comments file should NOT have insights
        comments_content = mock_fs.files[comments_path]
        assert "Curated comments here" in comments_content
        assert "Insights here" not in comments_content

    def test_replaces_old_insights_in_summary(self, finalizer, mock_fs):
        """Test update_comments replaces existing insights in summary."""
        output_dir = Path("/output")
        base_name = "youtube_abc123"
        template_dir = Path("/templates")

        summary_filename = "2024-01-15 - youtube - Test Title (abc123).md"
        mock_fs.files[output_dir / summary_filename] = "## Summary\n\nContent\n\n## Comment Insights (old)\n\nOld insights\n"

        mock_fs.files[template_dir / "comments.md"] = "## Curated Comments\n\n{comments}"
        mock_fs.files[output_dir / f"{base_name}_title.txt"] = "Test Title"
        mock_fs.files[output_dir / f"{base_name}_upload_date.txt"] = "2024-01-15"
        mock_fs.files[output_dir / f"{base_name}_comment_insights_tight.md"] = "## Comment Insights (new)\n\nNew insights"
        mock_fs.files[output_dir / f"{base_name}_comments_prefiltered.md"] = "Comments"

        summary_path, _ = finalizer.update_comments(base_name, output_dir, template_dir, debug=True)

        result = mock_fs.files[summary_path]
        assert "New insights" in result
        assert "Old insights" not in result

    def test_cleans_up_work_files(self, finalizer, mock_fs):
        """Test update_comments cleans work files when not debug."""
        output_dir = Path("/output")
        base_name = "youtube_abc123"
        template_dir = Path("/templates")

        summary_filename = "youtube - Test Title (abc123).md"
        mock_fs.files[output_dir / summary_filename] = "## Summary\n\nContent"

        mock_fs.files[template_dir / "comments.md"] = "{comments}"
        mock_fs.files[output_dir / f"{base_name}_title.txt"] = "Test Title"
        mock_fs.files[output_dir / f"{base_name}_comment_insights_tight.md"] = "Insights"
        mock_fs.files[output_dir / f"{base_name}_comments_prefiltered.md"] = "Comments"

        finalizer.update_comments(base_name, output_dir, template_dir, debug=False)

        assert output_dir / f"{base_name}_comment_insights_tight.md" not in mock_fs.files
