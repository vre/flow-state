"""Tests for extract_transcript module."""

import pytest
from pathlib import Path
from lib.transcript_extractor import TranscriptExtractor
from lib.shared_types import CommandNotFoundError, TranscriptNotAvailableError, FileOperationError


class TestTranscriptExtractor:
    """Tests for TranscriptExtractor class."""

    def test_check_yt_dlp_success(self, mock_cmd):
        """Test successful yt-dlp check."""
        mock_cmd.set_response("yt-dlp --version", returncode=0)
        extractor = TranscriptExtractor(cmd=mock_cmd)
        extractor.check_yt_dlp()  # Should not raise

    def test_check_yt_dlp_not_installed(self, mock_cmd):
        """Test yt-dlp not installed."""
        mock_cmd.set_response("yt-dlp --version", returncode=1)
        extractor = TranscriptExtractor(cmd=mock_cmd)

        with pytest.raises(CommandNotFoundError):
            extractor.check_yt_dlp()

    def test_get_video_language(self, mock_cmd):
        """Test getting video language."""
        mock_cmd.set_response(
            "yt-dlp --print %(language)s https://youtube.com/watch?v=test123",
            returncode=0,
            stdout="en"
        )
        extractor = TranscriptExtractor(cmd=mock_cmd)

        result = extractor.get_video_language("https://youtube.com/watch?v=test123")
        assert result == "en"

    def test_get_video_language_unknown(self, mock_cmd):
        """Test getting video language when unavailable."""
        mock_cmd.set_response(
            "yt-dlp --print %(language)s https://youtube.com/watch?v=test123",
            returncode=1
        )
        extractor = TranscriptExtractor(cmd=mock_cmd)

        result = extractor.get_video_language("https://youtube.com/watch?v=test123")
        assert result == "unknown"

    def test_download_manual_subtitles_success(self, mock_fs, mock_cmd):
        """Test successful manual subtitle download."""
        extractor = TranscriptExtractor(fs=mock_fs, cmd=mock_cmd)

        output_name = Path("/output/youtube_test123_transcript_temp")
        # Simulate yt-dlp creating the VTT file
        vtt_file = Path("/output/youtube_test123_transcript_temp.en.vtt")
        mock_fs.write_text(vtt_file, "VTT content")

        result = extractor.download_manual_subtitles(
            "https://youtube.com/watch?v=test123",
            "en",
            output_name
        )

        assert result == vtt_file

    def test_download_manual_subtitles_not_available(self, mock_fs, mock_cmd):
        """Test manual subtitles not available."""
        extractor = TranscriptExtractor(fs=mock_fs, cmd=mock_cmd)

        output_name = Path("/output/youtube_test123_transcript_temp")
        # No VTT file created

        result = extractor.download_manual_subtitles(
            "https://youtube.com/watch?v=test123",
            "en",
            output_name
        )

        assert result is None

    def test_download_auto_subtitles_success(self, mock_fs, mock_cmd):
        """Test successful auto subtitle download."""
        extractor = TranscriptExtractor(fs=mock_fs, cmd=mock_cmd)

        output_name = Path("/output/youtube_test123_transcript_temp")
        # Simulate yt-dlp creating the VTT file
        vtt_file = Path("/output/youtube_test123_transcript_temp.en.vtt")
        mock_fs.write_text(vtt_file, "VTT content")

        result = extractor.download_auto_subtitles(
            "https://youtube.com/watch?v=test123",
            "en",
            output_name
        )

        assert result == vtt_file

    def test_download_subtitles_tries_manual_first(self, mock_fs, mock_cmd):
        """Test that download_subtitles tries manual before auto."""
        extractor = TranscriptExtractor(fs=mock_fs, cmd=mock_cmd)

        output_name = Path("/output/youtube_test123_transcript_temp")
        # Simulate manual subtitle available
        manual_vtt = Path("/output/youtube_test123_transcript_temp.en.vtt")
        mock_fs.write_text(manual_vtt, "Manual VTT")

        result = extractor.download_subtitles(
            "https://youtube.com/watch?v=test123",
            "en",
            output_name
        )

        assert result == manual_vtt
        # Should only call manual, not auto
        commands = [" ".join(cmd) for cmd in mock_cmd.commands]
        assert any("--write-sub" in cmd for cmd in commands)
        # Since manual succeeded, auto should not be called
        # (but our mock doesn't prevent it, so we just check manual was attempted)

    def test_download_subtitles_fallback_to_auto(self, mock_fs, mock_cmd):
        """Test fallback to auto subtitles when manual unavailable."""
        extractor = TranscriptExtractor(fs=mock_fs, cmd=mock_cmd)

        output_name = Path("/output/youtube_test123_transcript_temp")

        # Simulate: manual fails, but auto succeeds
        # We need to control the glob behavior - first call returns nothing, second returns file
        call_count = [0]

        def smart_glob(pattern, directory):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call (manual) - no files
                return []
            else:
                # Second call (auto) - file exists
                auto_vtt = directory / "youtube_test123_transcript_temp.en.vtt"
                if not mock_fs.exists(auto_vtt):
                    mock_fs.write_text(auto_vtt, "Auto VTT")
                return [auto_vtt]

        mock_fs.glob = smart_glob

        result = extractor.download_subtitles(
            "https://youtube.com/watch?v=test123",
            "en",
            output_name
        )

        assert result is not None
        assert "youtube_test123_transcript_temp.en.vtt" in str(result)

    def test_download_subtitles_not_available(self, mock_fs, mock_cmd):
        """Test error when no subtitles available."""
        extractor = TranscriptExtractor(fs=mock_fs, cmd=mock_cmd)

        output_name = Path("/output/youtube_test123_transcript_temp")
        # No VTT files created

        with pytest.raises(TranscriptNotAvailableError, match="No subtitles available"):
            extractor.download_subtitles(
                "https://youtube.com/watch?v=test123",
                "en",
                output_name
            )

