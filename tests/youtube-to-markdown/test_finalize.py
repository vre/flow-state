"""Tests for finalize.py."""

from pathlib import Path

import pytest

from finalize import Finalizer
from shared_types import FileOperationError


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

    def test_get_filenames_with_title(self, finalizer, mock_fs):
        """Test getting filenames when title exists."""
        output_dir = Path("/output")
        mock_fs.files[output_dir / "youtube_abc123_title.txt"] = "Test Video Title"

        cleaned_title, video_id = finalizer.get_filenames("youtube_abc123", output_dir)

        assert cleaned_title == "Test Video Title"
        assert video_id == "abc123"

    def test_get_filenames_without_title(self, finalizer, mock_fs):
        """Test getting filenames when title doesn't exist."""
        output_dir = Path("/output")

        cleaned_title, video_id = finalizer.get_filenames("youtube_abc123", output_dir)

        assert cleaned_title is None
        assert video_id == "abc123"

    def test_get_filenames_cleans_title(self, finalizer, mock_fs):
        """Test that title is cleaned for filename."""
        output_dir = Path("/output")
        mock_fs.files[output_dir / "youtube_abc123_title.txt"] = "Test: Video? Title!"

        cleaned_title, video_id = finalizer.get_filenames("youtube_abc123", output_dir)

        # Special characters should be removed
        assert ":" not in cleaned_title
        assert "?" not in cleaned_title


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
        """Test assembling transcript content."""
        output_dir = Path("/output")
        base_name = "youtube_test123"
        template = "Desc: {description}\n\nTrans: {transcription}"

        mock_fs.files[output_dir / f"{base_name}_description.md"] = "Description here"
        mock_fs.files[output_dir / f"{base_name}_transcript.md"] = "Transcript here"

        result = finalizer.assemble_transcript_content(template, base_name, output_dir)

        assert "Desc: Description here" in result
        assert "Trans: Transcript here" in result


class TestAssembleCommentsContent:
    """Tests for assemble_comments_content method."""

    def test_assemble_comments_standalone(self, finalizer, mock_fs):
        """Test assembling comments in standalone mode."""
        output_dir = Path("/output")
        base_name = "youtube_test123"
        template = "Insights: {comment_insights}\n\nComments: {comments}"

        mock_fs.files[output_dir / f"{base_name}_comment_insights_tight.md"] = "Insights here"
        mock_fs.files[output_dir / f"{base_name}_comments_prefiltered.md"] = "Comments here"

        result = finalizer.assemble_comments_content(template, base_name, output_dir, standalone=True)

        assert "Insights: Insights here" in result
        assert "Comments: Comments here" in result

    def test_assemble_comments_not_standalone(self, finalizer, mock_fs):
        """Test assembling comments not standalone (insights go to summary)."""
        output_dir = Path("/output")
        base_name = "youtube_test123"
        template = "Comments: {comments}"

        mock_fs.files[output_dir / f"{base_name}_comments_prefiltered.md"] = "Comments here"

        result = finalizer.assemble_comments_content(template, base_name, output_dir, standalone=False)

        assert "Comments: Comments here" in result


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
        from intermediate_files import get_summary_work_files
        files = get_summary_work_files("youtube_test123")

        assert "youtube_test123_title.txt" in files
        assert "youtube_test123_metadata.md" in files
        assert "youtube_test123_summary_tight.md" in files

    def test_get_transcript_work_files(self):
        """Test getting transcript work files list."""
        from intermediate_files import get_transcript_work_files
        files = get_transcript_work_files("youtube_test123")

        assert "youtube_test123_transcript.md" in files
        assert "youtube_test123_description.md" in files

    def test_get_comments_work_files(self):
        """Test getting comments work files list."""
        from intermediate_files import get_comments_work_files
        files = get_comments_work_files("youtube_test123")

        assert "youtube_test123_comments.md" in files
        assert "youtube_test123_comment_insights_tight.md" in files

    def test_get_all_work_files_combines_all(self):
        """Test getting all work files combines all lists."""
        from intermediate_files import (
            get_all_work_files,
            get_summary_work_files,
            get_transcript_work_files,
            get_comments_work_files,
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

    def test_creates_file_with_title(self, finalizer, mock_fs):
        """Test finalize_summary_only creates summary file with title."""
        output_dir = Path("/output")
        base_name = "youtube_abc123"
        script_dir = Path("/scripts")

        mock_fs.files[script_dir / "template.md"] = "{quick_summary}\n{metadata}\n{summary}"
        mock_fs.files[output_dir / f"{base_name}_title.txt"] = "Test Title"
        mock_fs.files[output_dir / f"{base_name}_quick_summary.md"] = "Quick"
        mock_fs.files[output_dir / f"{base_name}_metadata.md"] = "Meta"
        mock_fs.files[output_dir / f"{base_name}_summary_tight.md"] = "Summary"

        import finalize
        original_file = finalize.__file__
        finalize.__file__ = str(script_dir / "finalize.py")

        try:
            result = finalizer.finalize_summary_only(base_name, output_dir, debug=True)
            assert "youtube - Test Title (abc123).md" in str(result)
        finally:
            finalize.__file__ = original_file

    def test_creates_file_without_title(self, finalizer, mock_fs):
        """Test finalize_summary_only creates summary file without title."""
        output_dir = Path("/output")
        base_name = "youtube_abc123"
        script_dir = Path("/scripts")

        mock_fs.files[script_dir / "template.md"] = "{quick_summary}\n{metadata}\n{summary}"

        import finalize
        original_file = finalize.__file__
        finalize.__file__ = str(script_dir / "finalize.py")

        try:
            result = finalizer.finalize_summary_only(base_name, output_dir, debug=True)
            assert f"{base_name}.md" in str(result)
        finally:
            finalize.__file__ = original_file


class TestFinalizeTranscriptOnly:
    """Tests for finalize_transcript_only method."""

    def test_creates_transcript_file(self, finalizer, mock_fs):
        """Test finalize_transcript_only creates transcript file."""
        output_dir = Path("/output")
        base_name = "youtube_abc123"
        script_dir = Path("/scripts")

        mock_fs.files[script_dir / "template_transcript.md"] = "{description}\n{transcription}"
        mock_fs.files[output_dir / f"{base_name}_title.txt"] = "Test Title"
        mock_fs.files[output_dir / f"{base_name}_description.md"] = "Desc"
        mock_fs.files[output_dir / f"{base_name}_transcript.md"] = "Trans"

        import finalize
        original_file = finalize.__file__
        finalize.__file__ = str(script_dir / "finalize.py")

        try:
            result = finalizer.finalize_transcript_only(base_name, output_dir, debug=True)
            assert "transcript" in str(result)
        finally:
            finalize.__file__ = original_file


class TestFinalizeCommentsOnly:
    """Tests for finalize_comments_only method."""

    def test_creates_comments_file(self, finalizer, mock_fs):
        """Test finalize_comments_only creates comments file."""
        output_dir = Path("/output")
        base_name = "youtube_abc123"
        script_dir = Path("/scripts")

        mock_fs.files[script_dir / "template_comments_standalone.md"] = "{comment_insights}\n{comments}"
        mock_fs.files[output_dir / f"{base_name}_name.txt"] = "Test Title"
        mock_fs.files[output_dir / f"{base_name}_comment_insights_tight.md"] = "Insights"
        mock_fs.files[output_dir / f"{base_name}_comments_prefiltered.md"] = "Comments"

        import finalize
        original_file = finalize.__file__
        finalize.__file__ = str(script_dir / "finalize.py")

        try:
            result = finalizer.finalize_comments_only(base_name, output_dir, debug=True)
            assert "comments" in str(result)
        finally:
            finalize.__file__ = original_file


class TestFinalizeSummaryComments:
    """Tests for finalize_summary_comments method."""

    def test_creates_both_files(self, finalizer, mock_fs):
        """Test finalize_summary_comments creates summary and comments files."""
        output_dir = Path("/output")
        base_name = "youtube_abc123"
        script_dir = Path("/scripts")

        mock_fs.files[script_dir / "template.md"] = "{quick_summary}\n{metadata}\n{summary}"
        mock_fs.files[script_dir / "template_comments.md"] = "{comments}"
        mock_fs.files[output_dir / f"{base_name}_title.txt"] = "Test Title"
        mock_fs.files[output_dir / f"{base_name}_quick_summary.md"] = "Quick"
        mock_fs.files[output_dir / f"{base_name}_metadata.md"] = "Meta"
        mock_fs.files[output_dir / f"{base_name}_summary_tight.md"] = "Summary"
        mock_fs.files[output_dir / f"{base_name}_comment_insights_tight.md"] = "Insights"
        mock_fs.files[output_dir / f"{base_name}_comments_prefiltered.md"] = "Comments"

        import finalize
        original_file = finalize.__file__
        finalize.__file__ = str(script_dir / "finalize.py")

        try:
            summary_path, comments_path = finalizer.finalize_summary_comments(base_name, output_dir, debug=True)
            assert "youtube - Test Title (abc123).md" in str(summary_path)
            assert "comments" in str(comments_path)
        finally:
            finalize.__file__ = original_file


class TestFinalizeFull:
    """Tests for finalize_full method."""

    def test_creates_all_three_files(self, finalizer, mock_fs):
        """Test finalize_full creates summary, transcript, and comments files."""
        output_dir = Path("/output")
        base_name = "youtube_abc123"
        script_dir = Path("/scripts")

        mock_fs.files[script_dir / "template.md"] = "{quick_summary}\n{metadata}\n{summary}"
        mock_fs.files[script_dir / "template_transcript.md"] = "{description}\n{transcription}"
        mock_fs.files[script_dir / "template_comments.md"] = "{comments}"
        mock_fs.files[output_dir / f"{base_name}_title.txt"] = "Test Title"
        mock_fs.files[output_dir / f"{base_name}_quick_summary.md"] = "Quick"
        mock_fs.files[output_dir / f"{base_name}_metadata.md"] = "Meta"
        mock_fs.files[output_dir / f"{base_name}_summary_tight.md"] = "Summary"
        mock_fs.files[output_dir / f"{base_name}_description.md"] = "Desc"
        mock_fs.files[output_dir / f"{base_name}_transcript.md"] = "Trans"
        mock_fs.files[output_dir / f"{base_name}_comment_insights_tight.md"] = "Insights"
        mock_fs.files[output_dir / f"{base_name}_comments_prefiltered.md"] = "Comments"

        import finalize
        original_file = finalize.__file__
        finalize.__file__ = str(script_dir / "finalize.py")

        try:
            summary_path, transcript_path, comments_path = finalizer.finalize_full(base_name, output_dir, debug=True)
            assert "youtube - Test Title (abc123).md" in str(summary_path)
            assert "transcript" in str(transcript_path)
            assert "comments" in str(comments_path)
        finally:
            finalize.__file__ = original_file

    def test_cleanup_in_non_debug_mode(self, finalizer, mock_fs):
        """Test that work files are cleaned up when not in debug mode."""
        output_dir = Path("/output")
        base_name = "youtube_abc123"
        script_dir = Path("/scripts")

        mock_fs.files[script_dir / "template.md"] = "{quick_summary}\n{metadata}\n{summary}"
        mock_fs.files[script_dir / "template_transcript.md"] = "{description}\n{transcription}"
        mock_fs.files[script_dir / "template_comments.md"] = "{comments}"
        mock_fs.files[output_dir / f"{base_name}_title.txt"] = "Test Title"
        mock_fs.files[output_dir / f"{base_name}_quick_summary.md"] = "Quick"
        mock_fs.files[output_dir / f"{base_name}_metadata.md"] = "Meta"
        mock_fs.files[output_dir / f"{base_name}_summary_tight.md"] = "Summary"
        mock_fs.files[output_dir / f"{base_name}_description.md"] = "Desc"
        mock_fs.files[output_dir / f"{base_name}_transcript.md"] = "Trans"
        mock_fs.files[output_dir / f"{base_name}_comment_insights_tight.md"] = "Insights"
        mock_fs.files[output_dir / f"{base_name}_comments_prefiltered.md"] = "Comments"

        import finalize
        original_file = finalize.__file__
        finalize.__file__ = str(script_dir / "finalize.py")

        try:
            finalizer.finalize_full(base_name, output_dir, debug=False)
            # Work files should be cleaned up
            assert output_dir / f"{base_name}_metadata.md" not in mock_fs.files
        finally:
            finalize.__file__ = original_file
