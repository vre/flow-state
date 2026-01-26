"""Tests for extract_comments.py."""

from pathlib import Path
from typing import Any

import pytest

from lib.comment_extractor import (
    CommentExtractor,
    SubprocessRunner,
    build_comment_hierarchy,
    count_comments_and_replies,
    extract_video_id,
    format_comment_markdown,
    generate_comments_markdown,
    parse_video_data,
)
from lib.shared_types import (
    Comment,
    CommandRunner,
    FileSystem,
    CommentVideoData,
    VideoDataFetchError,
    VideoIdExtractionError,
    YTDLPNotFoundError,
)


# Fixtures for test data
@pytest.fixture
def sample_comments() -> list[Comment]:
    """Sample comment hierarchy for testing."""
    return [
        Comment(id="1", author="Alice", text="Great video!", like_count=42, parent="root"),
        Comment(id="2", author="Bob", text="Thanks Alice!", like_count=10, parent="1"),
        Comment(id="3", author="Charlie", text="I agree", like_count=5, parent="1"),
        Comment(id="4", author="David", text="Another comment", like_count=30, parent="root"),
        Comment(id="5", author="Eve", text="Deep reply", like_count=2, parent="2"),
        Comment(id="6", author="Frank", text="Very deep", like_count=1, parent="5"),
    ]


@pytest.fixture
def sample_video_data() -> CommentVideoData:
    """Sample video data for testing."""
    comments = [
        Comment(id="1", author="Alice", text="Great video!", like_count=42, parent="root"),
        Comment(id="2", author="Bob", text="Thanks Alice!", like_count=10, parent="1"),
    ]
    return CommentVideoData(title="Test Video", video_id="abc123", comments=comments)


@pytest.fixture
def mock_runner() -> "MockCommandRunner":
    """Mock command runner for testing."""
    return MockCommandRunner()


@pytest.fixture
def mock_filesystem() -> "MockFileSystem":
    """Mock file system for testing."""
    return MockFileSystem()


# Mock implementations
class MockCommandRunner:
    """Mock command runner for testing."""

    def __init__(self):
        self.commands: list[list[str]] = []
        self.return_values: dict[str, tuple[int, str, str]] = {}

    def run(self, cmd: list[str], capture_stdout: bool = False) -> tuple[int, str, str]:
        """Record command and return mocked result."""
        self.commands.append(cmd)
        cmd_key = " ".join(cmd)

        # Return custom value if set, otherwise success
        if cmd_key in self.return_values:
            return self.return_values[cmd_key]
        return 0, "", ""

    def set_return_value(self, cmd: list[str], returncode: int, stdout: str = "", stderr: str = ""):
        """Set return value for specific command."""
        cmd_key = " ".join(cmd)
        self.return_values[cmd_key] = (returncode, stdout, stderr)


class MockFileSystem:
    """Mock file system for testing."""

    def __init__(self):
        self.files: dict[Path, str] = {}
        self.directories: set[Path] = set()

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


# Tests for extract_video_id
class TestExtractVideoId:
    """Tests for extract_video_id function."""

    def test_extract_from_youtube_com_url(self):
        """Test extracting video ID from youtube.com URL."""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert extract_video_id(url) == "dQw4w9WgXcQ"

    def test_extract_from_youtube_com_with_extra_params(self):
        """Test extracting video ID with additional URL parameters."""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=123s"
        assert extract_video_id(url) == "dQw4w9WgXcQ"

    def test_extract_from_youtu_be_url(self):
        """Test extracting video ID from youtu.be short URL."""
        url = "https://youtu.be/dQw4w9WgXcQ"
        assert extract_video_id(url) == "dQw4w9WgXcQ"

    def test_extract_from_youtu_be_with_params(self):
        """Test extracting video ID from youtu.be with parameters."""
        url = "https://youtu.be/dQw4w9WgXcQ?t=123"
        assert extract_video_id(url) == "dQw4w9WgXcQ"

    def test_invalid_url_raises_error(self):
        """Test that invalid URL raises VideoIdExtractionError."""
        with pytest.raises(VideoIdExtractionError):
            extract_video_id("https://www.example.com/not-a-youtube-url")

    def test_empty_url_raises_error(self):
        """Test that empty URL raises error."""
        with pytest.raises(VideoIdExtractionError):
            extract_video_id("")


# Tests for parse_video_data
class TestParseVideoData:
    """Tests for parse_video_data function."""

    def test_parse_complete_data(self):
        """Test parsing complete video data."""
        json_data = {
            "title": "Test Video",
            "id": "abc123",
            "comments": [
                {"id": "1", "author": "Alice", "text": "Great!", "like_count": 42, "parent": "root"},
                {"id": "2", "author": "Bob", "text": "Thanks!", "like_count": 10, "parent": "1"},
            ],
        }
        result = parse_video_data(json_data)

        assert result.title == "Test Video"
        assert result.video_id == "abc123"
        assert len(result.comments) == 2
        assert result.comments[0].author == "Alice"
        assert result.comments[1].parent == "1"

    def test_parse_missing_optional_fields(self):
        """Test parsing data with missing optional fields."""
        json_data = {
            "comments": [
                {"id": "1"},  # Missing author, text, like_count, parent
            ],
        }
        result = parse_video_data(json_data)

        assert result.title == "Untitled"
        assert result.video_id == ""
        assert len(result.comments) == 1
        assert result.comments[0].author == "Unknown"
        assert result.comments[0].text == ""
        assert result.comments[0].like_count == 0
        assert result.comments[0].parent == "root"

    def test_parse_empty_comments(self):
        """Test parsing data with no comments."""
        json_data = {"title": "Test", "id": "abc123"}
        result = parse_video_data(json_data)

        assert result.title == "Test"
        assert len(result.comments) == 0


# Tests for build_comment_hierarchy
class TestBuildCommentHierarchy:
    """Tests for build_comment_hierarchy function."""

    def test_build_hierarchy(self, sample_comments):
        """Test building comment hierarchy."""
        comment_by_id, replies_by_parent = build_comment_hierarchy(sample_comments)

        assert len(comment_by_id) == 6
        assert "1" in comment_by_id
        assert len(replies_by_parent["root"]) == 2  # Alice and David
        assert len(replies_by_parent["1"]) == 2  # Bob and Charlie
        assert len(replies_by_parent["2"]) == 1  # Eve

    def test_empty_comments(self):
        """Test building hierarchy with empty list."""
        comment_by_id, replies_by_parent = build_comment_hierarchy([])

        assert len(comment_by_id) == 0
        assert len(replies_by_parent) == 0


# Tests for format_comment_markdown
class TestFormatCommentMarkdown:
    """Tests for format_comment_markdown function."""

    def test_format_top_level_with_numbering(self, sample_comments):
        """Test formatting top-level comment with numbering."""
        _, replies_by_parent = build_comment_hierarchy(sample_comments)
        comment = sample_comments[0]  # Alice's comment

        result = format_comment_markdown(
            comment, depth=0, replies_by_parent=replies_by_parent, include_numbering=True, number=1
        )

        assert "### 1. Alice (42 likes)" in result
        assert "Great video!" in result

    def test_format_depth_1_reply(self, sample_comments):
        """Test formatting depth 1 reply."""
        _, replies_by_parent = build_comment_hierarchy(sample_comments)
        comment = sample_comments[1]  # Bob's comment

        result = format_comment_markdown(comment, depth=1, replies_by_parent=replies_by_parent)

        assert "#### Bob (10 likes)" in result
        assert "Thanks Alice!" in result

    def test_format_depth_2_reply(self, sample_comments):
        """Test formatting depth 2 reply."""
        _, replies_by_parent = build_comment_hierarchy(sample_comments)
        comment = sample_comments[4]  # Eve's comment

        result = format_comment_markdown(comment, depth=2, replies_by_parent=replies_by_parent)

        assert "##### Eve (2 likes)" in result
        assert "Deep reply" in result

    def test_format_depth_3_uses_h6(self, sample_comments):
        """Test that depth 3 uses H6 heading (YouTube only uses 2 levels, but future-proofed)."""
        _, replies_by_parent = build_comment_hierarchy(sample_comments)
        comment = sample_comments[5]  # Frank's comment

        result = format_comment_markdown(comment, depth=3, replies_by_parent=replies_by_parent)

        assert "###### Frank (1 likes)" in result
        assert "Very deep" in result


# Tests for generate_comments_markdown
class TestGenerateCommentsMarkdown:
    """Tests for generate_comments_markdown function."""

    def test_generate_with_comments(self, sample_comments):
        """Test generating markdown with comments."""
        result = generate_comments_markdown(sample_comments)

        assert "### 1. Alice (42 likes)" in result
        assert "### 2. David (30 likes)" in result
        assert "Great video!" in result

    def test_generate_empty_comments(self):
        """Test generating markdown with no comments."""
        result = generate_comments_markdown([])

        assert result == "No comments available\n"

    def test_generate_includes_all_top_level(self, sample_comments):
        """Test that all top-level comments are included (no max limit)."""
        result = generate_comments_markdown(sample_comments)

        assert "### 1. Alice (42 likes)" in result
        assert "### 2. David (30 likes)" in result  # Both top-level included


# Tests for count_comments_and_replies
class TestCountCommentsAndReplies:
    """Tests for count_comments_and_replies function."""

    def test_count_with_hierarchy(self, sample_comments):
        """Test counting comments and replies."""
        top_level, replies = count_comments_and_replies(sample_comments)

        assert top_level == 2  # Alice and David
        assert replies == 4  # Bob, Charlie, Eve, Frank

    def test_count_empty_list(self):
        """Test counting empty list."""
        top_level, replies = count_comments_and_replies([])

        assert top_level == 0
        assert replies == 0

    def test_count_only_top_level(self):
        """Test counting with only top-level comments."""
        comments = [
            Comment(id="1", author="Alice", text="Test", like_count=1, parent="root"),
            Comment(id="2", author="Bob", text="Test", like_count=1, parent="root"),
        ]
        top_level, replies = count_comments_and_replies(comments)

        assert top_level == 2
        assert replies == 0


# Tests for CommentExtractor class
class TestCommentExtractor:
    """Tests for CommentExtractor class."""

    def test_check_yt_dlp_success(self, mock_runner):
        """Test checking yt-dlp when it's available."""
        mock_runner.set_return_value(["yt-dlp", "--version"], 0, "2023.01.01", "")
        extractor = CommentExtractor(mock_runner, MockFileSystem())

        extractor.check_yt_dlp()  # Should not raise

        assert ["yt-dlp", "--version"] in mock_runner.commands

    def test_check_yt_dlp_not_found(self, mock_runner):
        """Test checking yt-dlp when it's not available."""
        mock_runner.set_return_value(["yt-dlp", "--version"], 1, "", "command not found")
        extractor = CommentExtractor(mock_runner, MockFileSystem())

        with pytest.raises(YTDLPNotFoundError) as exc_info:
            extractor.check_yt_dlp()

        assert "not installed" in str(exc_info.value)

    def test_fetch_video_data_success(self, mock_runner, mock_filesystem):
        """Test fetching video data successfully."""
        json_output = '{"title": "Test Video", "id": "abc123", "comments": []}'
        mock_runner.set_return_value(
            ["yt-dlp", "--dump-single-json", "--write-comments", "--skip-download", "--extractor-args", "youtube:comment_sort=top", "test_url"],
            0,
            json_output,
            "",
        )

        extractor = CommentExtractor(mock_runner, mock_filesystem)
        output_dir = Path("/tmp/test")
        mock_filesystem.mkdir(output_dir, exist_ok=True)

        result = extractor.fetch_video_data("test_url", output_dir)

        assert result.title == "Test Video"
        assert result.video_id == "abc123"
        # Temp file should be cleaned up
        assert Path("/tmp/test/video_data.json") not in mock_filesystem.files

    def test_fetch_video_data_command_failure(self, mock_runner, mock_filesystem):
        """Test handling yt-dlp command failure."""
        mock_runner.set_return_value(
            ["yt-dlp", "--dump-single-json", "--write-comments", "--skip-download", "--extractor-args", "youtube:comment_sort=top", "test_url"],
            1,
            "",
            "Error: video not found",
        )

        extractor = CommentExtractor(mock_runner, mock_filesystem)
        output_dir = Path("/tmp/test")
        mock_filesystem.mkdir(output_dir, exist_ok=True)

        with pytest.raises(VideoDataFetchError) as exc_info:
            extractor.fetch_video_data("test_url", output_dir)

        assert "Failed to extract video data" in str(exc_info.value)

    def test_fetch_video_data_invalid_json(self, mock_runner, mock_filesystem):
        """Test handling invalid JSON from yt-dlp."""
        mock_runner.set_return_value(
            ["yt-dlp", "--dump-single-json", "--write-comments", "--skip-download", "--extractor-args", "youtube:comment_sort=top", "test_url"],
            0,
            "invalid json{",
            "",
        )

        extractor = CommentExtractor(mock_runner, mock_filesystem)
        output_dir = Path("/tmp/test")
        mock_filesystem.mkdir(output_dir, exist_ok=True)

        with pytest.raises(VideoDataFetchError) as exc_info:
            extractor.fetch_video_data("test_url", output_dir)

        assert "Failed to parse JSON" in str(exc_info.value)

    def test_extract_and_save_success(self, mock_runner, mock_filesystem, capsys):
        """Test complete extraction and save workflow."""
        json_output = '{"title": "Test Video", "id": "abc123", "comments": []}'
        mock_runner.set_return_value(["yt-dlp", "--version"], 0, "2023.01.01", "")
        mock_runner.set_return_value(
            ["yt-dlp", "--dump-single-json", "--write-comments", "--skip-download", "--extractor-args", "youtube:comment_sort=top", "https://youtu.be/abc123"],
            0,
            json_output,
            "",
        )

        extractor = CommentExtractor(mock_runner, mock_filesystem)
        output_dir = Path("/tmp/test")

        name_file, comments_file = extractor.extract_and_save("https://youtu.be/abc123", output_dir)

        # Check files were created
        assert name_file == output_dir / "youtube_abc123_name.txt"
        assert comments_file == output_dir / "youtube_abc123_comments.md"
        assert mock_filesystem.files[name_file] == "Test Video"
        assert "No comments available" in mock_filesystem.files[comments_file]

        # Check console output
        captured = capsys.readouterr()
        assert "SUCCESS:" in captured.out
        assert "COMMENTS:" in captured.out

    def test_extract_and_save_invalid_url(self, mock_runner, mock_filesystem):
        """Test extraction with invalid URL."""
        mock_runner.set_return_value(["yt-dlp", "--version"], 0, "2023.01.01", "")
        extractor = CommentExtractor(mock_runner, mock_filesystem)

        with pytest.raises(VideoIdExtractionError):
            extractor.extract_and_save("https://invalid.com", Path("/tmp/test"))


# Tests for SubprocessRunner (real implementation)
class TestSubprocessRunner:
    """Tests for SubprocessRunner class."""

    def test_run_successful_command(self):
        """Test running a successful command."""
        runner = SubprocessRunner()
        returncode, stdout, stderr = runner.run(["echo", "hello"])

        assert returncode == 0
        assert "hello" in stdout
        assert stderr == ""

    def test_run_failing_command(self):
        """Test running a command that fails."""
        runner = SubprocessRunner()
        returncode, stdout, stderr = runner.run(["ls", "/nonexistent_directory_xyz123"])

        assert returncode != 0
        assert stderr != ""

    def test_run_nonexistent_command(self):
        """Test running a command that doesn't exist."""
        runner = SubprocessRunner()
        returncode, stdout, stderr = runner.run(["nonexistent_command_xyz123"])

        assert returncode == 1
        assert "Command not found" in stderr
