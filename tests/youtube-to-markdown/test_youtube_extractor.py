"""Tests for extract_data module."""

import pytest
import json
from pathlib import Path
from lib.youtube_extractor import YouTubeDataExtractor
from lib.shared_types import CommandNotFoundError, FileOperationError


class TestYouTubeDataExtractor:
    """Tests for YouTubeDataExtractor class."""

    def test_check_yt_dlp_success(self, mock_cmd):
        """Test successful yt-dlp check."""
        mock_cmd.set_response("yt-dlp --version", returncode=0, stdout="2024.01.01")
        extractor = YouTubeDataExtractor(cmd=mock_cmd)
        extractor.check_yt_dlp()  # Should not raise

    def test_check_yt_dlp_not_installed(self, mock_cmd):
        """Test yt-dlp not installed."""
        mock_cmd.set_response("yt-dlp --version", returncode=1)
        extractor = YouTubeDataExtractor(cmd=mock_cmd)

        with pytest.raises(CommandNotFoundError):
            extractor.check_yt_dlp()

    def test_parse_video_metadata(self, mock_fs, mock_cmd, sample_video_data):
        """Test parsing video metadata."""
        extractor = YouTubeDataExtractor(fs=mock_fs, cmd=mock_cmd)
        metadata = extractor.parse_video_metadata(sample_video_data, "test123")

        assert metadata.video_id == "test123"
        assert metadata.title == "Test Video Title"
        assert metadata.uploader == "Test Channel"
        assert metadata.view_count == 500000
        assert len(metadata.chapters) == 2

    def test_create_metadata_file(self, mock_fs, mock_cmd, sample_video_data):
        """Test creating metadata file."""
        extractor = YouTubeDataExtractor(fs=mock_fs, cmd=mock_cmd)
        metadata = extractor.parse_video_metadata(sample_video_data, "test123")

        output_path = extractor.create_metadata_file(
            metadata,
            "youtube_test123",
            Path("/output")
        )

        assert output_path == Path("/output/youtube_test123_metadata.md")
        content = mock_fs.read_text(output_path)
        assert "Test Video Title" in content
        assert "Test Channel" in content
        assert "1,000,000 subscribers" in content

        # Check title file was created
        title_path = Path("/output/youtube_test123_title.txt")
        assert mock_fs.exists(title_path)
        assert mock_fs.read_text(title_path) == "Test Video Title"

    def test_create_description_file(self, mock_fs, mock_cmd, sample_video_data):
        """Test creating description file."""
        extractor = YouTubeDataExtractor(fs=mock_fs, cmd=mock_cmd)
        metadata = extractor.parse_video_metadata(sample_video_data, "test123")

        output_path = extractor.create_description_file(
            metadata,
            "youtube_test123",
            Path("/output")
        )

        assert output_path == Path("/output/youtube_test123_description.md")
        content = mock_fs.read_text(output_path)
        assert content == "Test video description"

    def test_create_chapters_file(self, mock_fs, mock_cmd, sample_video_data):
        """Test creating chapters file."""
        extractor = YouTubeDataExtractor(fs=mock_fs, cmd=mock_cmd)
        metadata = extractor.parse_video_metadata(sample_video_data, "test123")

        output_path = extractor.create_chapters_file(
            metadata,
            "youtube_test123",
            Path("/output")
        )

        assert output_path == Path("/output/youtube_test123_chapters.json")
        content = mock_fs.read_text(output_path)
        chapters = json.loads(content)
        assert len(chapters) == 2
        assert chapters[0]['title'] == 'Introduction'

    def test_create_chapters_file_empty(self, mock_fs, mock_cmd):
        """Test creating chapters file when no chapters exist."""
        extractor = YouTubeDataExtractor(fs=mock_fs, cmd=mock_cmd)
        data = {'chapters': []}
        metadata = extractor.parse_video_metadata(data, "test123")

        output_path = extractor.create_chapters_file(
            metadata,
            "youtube_test123",
            Path("/output")
        )

        content = mock_fs.read_text(output_path)
        chapters = json.loads(content)
        assert chapters == []

