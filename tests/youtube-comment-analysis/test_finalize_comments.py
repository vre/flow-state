"""Tests for finalize_comments.py."""

from pathlib import Path

import pytest

from finalize_comments import (
    CommentFinalizer,
    clean_title_for_filename,
    fill_template,
    generate_final_filename,
    get_work_files,
    parse_args,
)
from types_and_exceptions import FileSystem, TemplateNotFoundError


# Fixtures
@pytest.fixture
def mock_filesystem() -> "MockFileSystem":
    """Mock file system for testing."""
    return MockFileSystem()


@pytest.fixture
def template_content() -> str:
    """Sample template content (without Golden Insights)."""
    return "## Curated Comments\n\n{comments}\n"


@pytest.fixture
def template_standalone_content() -> str:
    """Sample standalone template content (with Golden Insights)."""
    return "## Golden Insights\n\n{comment_gold}\n\n## Curated Comments\n\n{comments}\n"


# Mock implementation
class MockFileSystem:
    """Mock file system for testing."""

    def __init__(self):
        self.files: dict[Path, str] = {}
        self.directories: set[Path] = set()
        self.removed_files: list[Path] = []

    def read_text(self, path: Path) -> str:
        """Read from mock file system."""
        if path not in self.files:
            raise FileNotFoundError(f"Mock file not found: {path}")
        return self.files[path]

    def write_text(self, path: Path, content: str) -> None:
        """Write to mock file system."""
        self.files[path] = content

    def exists(self, path: Path) -> bool:
        """Check if path exists in mock file system."""
        return path in self.files or path in self.directories

    def mkdir(self, path: Path, parents: bool = False, exist_ok: bool = False) -> None:
        """Create directory in mock file system."""
        self.directories.add(path)

    def remove(self, path: Path) -> None:
        """Remove file from mock file system."""
        if path in self.files:
            del self.files[path]
            self.removed_files.append(path)


# Tests for clean_title_for_filename
class TestCleanTitleForFilename:
    """Tests for clean_title_for_filename function."""

    def test_clean_simple_title(self):
        """Test cleaning a simple title."""
        result = clean_title_for_filename("My Great Video")
        assert result == "My Great Video"

    def test_remove_invalid_characters(self):
        """Test removing invalid filename characters."""
        result = clean_title_for_filename('Title with <invalid> chars: /\\|?*"')
        assert result == "Title with invalid chars"

    def test_normalize_whitespace(self):
        """Test normalizing whitespace."""
        result = clean_title_for_filename("Title  with   extra    spaces")
        assert result == "Title with extra spaces"

    def test_truncate_long_title(self):
        """Test truncating long titles."""
        long_title = "This is a very long title that should be truncated at the maximum length"
        result = clean_title_for_filename(long_title, max_length=30)
        assert len(result) <= 30
        assert not result.endswith(" ")  # Should not end with space

    def test_truncate_at_word_boundary(self):
        """Test that truncation happens at word boundaries."""
        title = "One Two Three Four Five Six Seven"
        result = clean_title_for_filename(title, max_length=20)
        # Should cut at word boundary, not mid-word
        assert " " not in result or not result.endswith(" ")

    def test_strip_whitespace(self):
        """Test stripping leading/trailing whitespace."""
        result = clean_title_for_filename("  Title with spaces  ")
        assert result == "Title with spaces"


# Tests for generate_final_filename
class TestGenerateFinalFilename:
    """Tests for generate_final_filename function."""

    def test_with_video_name(self):
        """Test generating filename with video name."""
        result = generate_final_filename("My Video Title", "abc123")
        assert result == "youtube - My Video Title - comments (abc123).md"

    def test_with_empty_video_name(self):
        """Test generating filename with empty video name."""
        result = generate_final_filename("", "abc123")
        assert result == "youtube_abc123_comment_analysis.md"

    def test_with_whitespace_only_video_name(self):
        """Test generating filename with whitespace-only video name."""
        result = generate_final_filename("   ", "abc123")
        assert result == "youtube_abc123_comment_analysis.md"

    def test_cleans_invalid_characters(self):
        """Test that invalid characters are cleaned from filename."""
        result = generate_final_filename("Title with <invalid> chars", "abc123")
        assert "<" not in result
        assert ">" not in result


# Tests for fill_template
class TestFillTemplate:
    """Tests for fill_template function."""

    def test_fill_all_placeholders(self):
        """Test filling all template placeholders."""
        template = "Title: {video_name}\nGold: {comment_gold}\nComments: {comments}"
        result = fill_template(template, "My Video", "Golden insight", "Comment content")

        assert "Title: My Video" in result
        assert "Gold: Golden insight" in result
        assert "Comments: Comment content" in result

    def test_strips_whitespace(self):
        """Test that content whitespace is stripped."""
        template = "{video_name}|{comment_gold}|{comments}"
        result = fill_template(template, "  Video  ", "  Gold  ", "  Comments  ")

        assert result == "Video|Gold|Comments"

    def test_empty_content(self):
        """Test filling template with empty content."""
        template = "Title: {video_name}\nGold: {comment_gold}\nComments: {comments}"
        result = fill_template(template, "", "", "")

        assert "Title:" in result
        assert "Gold:" in result
        assert "Comments:" in result


# Tests for get_work_files
class TestGetWorkFiles:
    """Tests for get_work_files function."""

    def test_get_work_files(self):
        """Test getting list of work files."""
        result = get_work_files("youtube_abc123")

        assert "youtube_abc123_name.txt" in result
        assert "youtube_abc123_comments.md" in result
        assert "youtube_abc123_comments_cleaned.md" in result
        assert "youtube_abc123_comment_gold.md" in result
        assert len(result) == 4


# Tests for parse_args
class TestParseArgs:
    """Tests for parse_args function."""

    def test_parse_minimal_args(self):
        """Test parsing minimal arguments."""
        base_name, output_dir, debug = parse_args(["youtube_abc123"])

        assert base_name == "youtube_abc123"
        assert output_dir == Path(".")
        assert debug is False

    def test_parse_with_output_dir(self):
        """Test parsing with output directory."""
        base_name, output_dir, debug = parse_args(["youtube_abc123", "/tmp/output"])

        assert base_name == "youtube_abc123"
        assert output_dir == Path("/tmp/output")
        assert debug is False

    def test_parse_with_debug_flag(self):
        """Test parsing with debug flag."""
        base_name, output_dir, debug = parse_args(["youtube_abc123", "/tmp/output", "--debug"])

        assert base_name == "youtube_abc123"
        assert output_dir == Path("/tmp/output")
        assert debug is True

    def test_parse_debug_flag_different_position(self):
        """Test parsing with debug flag in different position."""
        base_name, output_dir, debug = parse_args(["--debug", "youtube_abc123", "/tmp/output"])

        assert base_name == "youtube_abc123"
        assert output_dir == Path("/tmp/output")
        assert debug is True

    def test_parse_no_args_raises_error(self):
        """Test parsing with no arguments raises error."""
        with pytest.raises(ValueError) as exc_info:
            parse_args([])

        assert "No BASE_NAME provided" in str(exc_info.value)

    def test_parse_only_debug_raises_error(self):
        """Test parsing with only debug flag raises error."""
        with pytest.raises(ValueError) as exc_info:
            parse_args(["--debug"])

        assert "No BASE_NAME provided" in str(exc_info.value)


# Tests for CommentFinalizer class
class TestCommentFinalizer:
    """Tests for CommentFinalizer class."""

    def test_load_template_success(self, mock_filesystem, template_content):
        """Test loading template successfully."""
        script_dir = Path("/app")
        template_path = script_dir / "template.md"
        mock_filesystem.files[template_path] = template_content

        finalizer = CommentFinalizer(mock_filesystem, script_dir)
        result = finalizer.load_template(standalone=False)

        assert result == template_content

    def test_load_template_standalone(self, mock_filesystem, template_standalone_content):
        """Test loading standalone template successfully."""
        script_dir = Path("/app")
        template_path = script_dir / "template_standalone.md"
        mock_filesystem.files[template_path] = template_standalone_content

        finalizer = CommentFinalizer(mock_filesystem, script_dir)
        result = finalizer.load_template(standalone=True)

        assert result == template_standalone_content

    def test_load_template_not_found(self, mock_filesystem):
        """Test loading template when file doesn't exist."""
        script_dir = Path("/app")
        finalizer = CommentFinalizer(mock_filesystem, script_dir)

        with pytest.raises(TemplateNotFoundError) as exc_info:
            finalizer.load_template()

        assert "Template not found" in str(exc_info.value)

    def test_read_file_or_empty_existing(self, mock_filesystem):
        """Test reading existing file."""
        script_dir = Path("/app")
        test_file = Path("/tmp/test.txt")
        mock_filesystem.files[test_file] = "Test content"

        finalizer = CommentFinalizer(mock_filesystem, script_dir)
        result = finalizer.read_file_or_empty(test_file)

        assert result == "Test content"

    def test_read_file_or_empty_nonexistent(self, mock_filesystem):
        """Test reading nonexistent file returns empty string."""
        script_dir = Path("/app")
        finalizer = CommentFinalizer(mock_filesystem, script_dir)
        result = finalizer.read_file_or_empty(Path("/tmp/nonexistent.txt"))

        assert result == ""

    def test_finalize_standalone_mode(self, mock_filesystem, template_standalone_content, capsys):
        """Test finalization when no summary file exists (standalone mode)."""
        script_dir = Path("/app")
        output_dir = Path("/tmp/output")
        base_name = "youtube_abc123"

        # Setup mock files - no summary file exists
        mock_filesystem.files[script_dir / "template_standalone.md"] = template_standalone_content
        mock_filesystem.files[output_dir / f"{base_name}_name.txt"] = "Test Video"
        mock_filesystem.files[output_dir / f"{base_name}_comment_gold.md"] = "Golden insight"
        mock_filesystem.files[output_dir / f"{base_name}_comments_cleaned.md"] = "Comment content"

        finalizer = CommentFinalizer(mock_filesystem, script_dir)
        result_file = finalizer.finalize(base_name, output_dir, debug=False)

        # Check final file created
        expected_filename = "youtube - Test Video - comments (abc123).md"
        assert result_file == output_dir / expected_filename
        assert result_file in mock_filesystem.files

        # Check content - should have Golden Insights section
        final_content = mock_filesystem.files[result_file]
        assert "Golden insight" in final_content
        assert "Comment content" in final_content
        assert "## Golden Insights" in final_content

        # Check work files cleaned up
        assert output_dir / f"{base_name}_name.txt" not in mock_filesystem.files
        assert output_dir / f"{base_name}_comments.md" not in mock_filesystem.files
        assert output_dir / f"{base_name}_comments_cleaned.md" not in mock_filesystem.files
        assert output_dir / f"{base_name}_comment_gold.md" not in mock_filesystem.files

        # Check console output
        captured = capsys.readouterr()
        assert "Created final file" in captured.out
        assert "Cleaned up intermediate work files" in captured.out

    def test_finalize_with_summary_file(self, mock_filesystem, template_content, capsys):
        """Test finalization when summary file exists - inserts Golden Comments into summary."""
        script_dir = Path("/app")
        output_dir = Path("/tmp/output")
        base_name = "youtube_abc123"

        # Setup mock files including summary file
        mock_filesystem.files[script_dir / "template.md"] = template_content
        mock_filesystem.files[output_dir / f"{base_name}_name.txt"] = "Test Video"
        mock_filesystem.files[output_dir / f"{base_name}_comment_gold.md"] = "Golden insight"
        mock_filesystem.files[output_dir / f"{base_name}_comments_cleaned.md"] = "Comment content"

        # Create summary file
        summary_file = output_dir / "youtube - Test Video (abc123).md"
        summary_content = "## Summary\n\nVideo summary here\n\n## Description\n\nVideo description\n\n## Transcription\n\nTranscript here"
        mock_filesystem.files[summary_file] = summary_content

        finalizer = CommentFinalizer(mock_filesystem, script_dir)
        result_file = finalizer.finalize(base_name, output_dir, debug=False)

        # Check summary file was updated with Golden Comments
        updated_summary = mock_filesystem.files[summary_file]
        assert "## Golden Comments" in updated_summary
        assert "Golden insight" in updated_summary
        # Golden Comments should be before Description
        golden_pos = updated_summary.index("## Golden Comments")
        desc_pos = updated_summary.index("## Description")
        assert golden_pos < desc_pos

        # Check comment file created without Golden Insights section
        final_content = mock_filesystem.files[result_file]
        assert "Comment content" in final_content
        assert "## Golden Insights" not in final_content

        # Check console output
        captured = capsys.readouterr()
        assert "Inserted Golden Comments into summary" in captured.out

    def test_finalize_with_summary_file_no_golden_comments(self, mock_filesystem, template_content, capsys):
        """Test finalization when summary exists but no golden comments - uses template.md."""
        script_dir = Path("/app")
        output_dir = Path("/tmp/output")
        base_name = "youtube_xyz789"

        # Setup mock files including summary file, but no comment_gold
        mock_filesystem.files[script_dir / "template.md"] = template_content
        mock_filesystem.files[output_dir / f"{base_name}_name.txt"] = "Test Video"
        mock_filesystem.files[output_dir / f"{base_name}_comment_gold.md"] = ""  # Empty
        mock_filesystem.files[output_dir / f"{base_name}_comments_cleaned.md"] = "Comment content"

        # Create summary file
        summary_file = output_dir / "youtube - Test Video (xyz789).md"
        summary_content = "## Summary\n\nVideo summary\n\n## Description\n\nVideo description"
        mock_filesystem.files[summary_file] = summary_content

        finalizer = CommentFinalizer(mock_filesystem, script_dir)
        result_file = finalizer.finalize(base_name, output_dir, debug=False)

        # Summary file should NOT be modified (no golden comments to insert)
        updated_summary = mock_filesystem.files[summary_file]
        assert "## Golden Comments" not in updated_summary
        assert updated_summary == summary_content

        # Comment file should use template.md (no Golden Insights section)
        final_content = mock_filesystem.files[result_file]
        assert "Comment content" in final_content
        assert "## Golden Insights" not in final_content
        assert "## Curated Comments" in final_content

        # Check console output - no insertion message
        captured = capsys.readouterr()
        assert "Inserted Golden Comments into summary" not in captured.out

    def test_finalize_debug_mode(self, mock_filesystem, template_standalone_content, capsys):
        """Test finalization in debug mode keeps work files."""
        script_dir = Path("/app")
        output_dir = Path("/tmp/output")
        base_name = "youtube_abc123"

        # Setup mock files
        mock_filesystem.files[script_dir / "template_standalone.md"] = template_standalone_content
        mock_filesystem.files[output_dir / f"{base_name}_name.txt"] = "Test Video"
        mock_filesystem.files[output_dir / f"{base_name}_comment_gold.md"] = ""
        mock_filesystem.files[output_dir / f"{base_name}_comments_cleaned.md"] = ""

        finalizer = CommentFinalizer(mock_filesystem, script_dir)
        finalizer.finalize(base_name, output_dir, debug=True)

        # Check work files NOT cleaned up
        assert output_dir / f"{base_name}_name.txt" in mock_filesystem.files
        assert len(mock_filesystem.removed_files) == 0

        # Check console output
        captured = capsys.readouterr()
        assert "Debug mode: keeping intermediate work files" in captured.out

    def test_finalize_missing_component_files(self, mock_filesystem, template_standalone_content):
        """Test finalization with missing component files uses empty strings."""
        script_dir = Path("/app")
        output_dir = Path("/tmp/output")
        base_name = "youtube_abc123"

        # Only setup template, no component files
        mock_filesystem.files[script_dir / "template_standalone.md"] = template_standalone_content

        finalizer = CommentFinalizer(mock_filesystem, script_dir)
        result_file = finalizer.finalize(base_name, output_dir, debug=False)

        # Should still create final file with empty content
        assert result_file in mock_filesystem.files
        final_content = mock_filesystem.files[result_file]
        # Template placeholders should be replaced with empty strings (stripped)
        assert "{video_name}" not in final_content
        assert "{comment_gold}" not in final_content
        assert "{comments}" not in final_content

    def test_finalize_empty_video_name_fallback(self, mock_filesystem, template_standalone_content):
        """Test finalization with empty video name uses fallback filename."""
        script_dir = Path("/app")
        output_dir = Path("/tmp/output")
        base_name = "youtube_abc123"

        # Setup with empty video name
        mock_filesystem.files[script_dir / "template_standalone.md"] = template_standalone_content
        mock_filesystem.files[output_dir / f"{base_name}_name.txt"] = ""

        finalizer = CommentFinalizer(mock_filesystem, script_dir)
        result_file = finalizer.finalize(base_name, output_dir, debug=False)

        # Should use fallback filename
        assert result_file.name == "youtube_abc123_comment_analysis.md"

    def test_finalize_partial_cleanup(self, mock_filesystem, template_standalone_content):
        """Test that finalization only removes files that exist."""
        script_dir = Path("/app")
        output_dir = Path("/tmp/output")
        base_name = "youtube_abc123"

        # Setup with only some component files
        mock_filesystem.files[script_dir / "template_standalone.md"] = template_standalone_content
        mock_filesystem.files[output_dir / f"{base_name}_name.txt"] = "Test"
        # Other component files don't exist

        finalizer = CommentFinalizer(mock_filesystem, script_dir)
        # Should not raise error even if some files don't exist
        finalizer.finalize(base_name, output_dir, debug=False)

        # Should only remove the one file that existed
        assert output_dir / f"{base_name}_name.txt" not in mock_filesystem.files

    def test_insert_golden_comments_into_summary(self, mock_filesystem):
        """Test inserting Golden Comments into existing summary file."""
        script_dir = Path("/app")
        summary_file = Path("/tmp/youtube - Test Video (abc123).md")
        summary_content = "## Summary\n\nSummary here\n\n## Description\n\nDescription here"
        mock_filesystem.files[summary_file] = summary_content

        finalizer = CommentFinalizer(mock_filesystem, script_dir)
        finalizer.insert_golden_comments_into_summary(summary_file, "Golden insight content")

        # Check Golden Comments section was inserted
        updated_content = mock_filesystem.files[summary_file]
        assert "## Golden Comments" in updated_content
        assert "Golden insight content" in updated_content

        # Check it's before Description
        golden_pos = updated_content.index("## Golden Comments")
        desc_pos = updated_content.index("## Description")
        assert golden_pos < desc_pos

    def test_insert_golden_comments_no_description_section(self, mock_filesystem):
        """Test inserting Golden Comments when no Description section exists."""
        script_dir = Path("/app")
        summary_file = Path("/tmp/youtube - Test Video (abc123).md")
        summary_content = "## Summary\n\nSummary here\n\n## Transcription\n\nTranscript"
        mock_filesystem.files[summary_file] = summary_content

        finalizer = CommentFinalizer(mock_filesystem, script_dir)
        finalizer.insert_golden_comments_into_summary(summary_file, "Golden insight")

        # Should not modify if no Description marker found
        updated_content = mock_filesystem.files[summary_file]
        assert updated_content == summary_content

    def test_insert_golden_comments_file_not_exist(self, mock_filesystem, capsys):
        """Test inserting Golden Comments when summary file doesn't exist."""
        script_dir = Path("/app")
        summary_file = Path("/tmp/nonexistent.md")

        finalizer = CommentFinalizer(mock_filesystem, script_dir)
        # Should not raise error
        finalizer.insert_golden_comments_into_summary(summary_file, "Golden insight")

        # No output expected
        captured = capsys.readouterr()
        assert "Inserted Golden Comments" not in captured.out
