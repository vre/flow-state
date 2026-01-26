"""Tests for deduplicate_vtt module."""

import pytest
from pathlib import Path
from lib.vtt_deduplicator import VTTDeduplicator
from lib.shared_types import FileOperationError


class TestVTTDeduplicator:
    """Tests for VTTDeduplicator class."""

    def test_parse_vtt_line_header(self):
        """Test parsing VTT header lines."""
        dedup = VTTDeduplicator()

        timestamp, text = dedup.parse_vtt_line("WEBVTT")
        assert timestamp is None
        assert text == ""

        timestamp, text = dedup.parse_vtt_line("Kind: captions")
        assert timestamp is None
        assert text == ""

    def test_parse_vtt_line_timestamp(self):
        """Test parsing timestamp lines."""
        dedup = VTTDeduplicator()

        timestamp, text = dedup.parse_vtt_line("00:00:01.000 --> 00:00:03.000")
        assert timestamp == "00:00:01.000"
        assert text == ""

    def test_parse_vtt_line_text(self):
        """Test parsing text lines."""
        dedup = VTTDeduplicator()

        timestamp, text = dedup.parse_vtt_line("Hello world")
        assert timestamp is None
        assert text == "Hello world"

    def test_parse_vtt_line_html_tags(self):
        """Test cleaning HTML tags from text."""
        dedup = VTTDeduplicator()

        timestamp, text = dedup.parse_vtt_line("<c>Hello</c> world")
        assert text == "Hello world"

    def test_parse_vtt_line_html_entities(self):
        """Test cleaning HTML entities."""
        dedup = VTTDeduplicator()

        timestamp, text = dedup.parse_vtt_line("A &amp; B &gt; C &lt; D")
        assert text == "A & B > C < D"

    def test_deduplicate_vtt_success(self, mock_fs, sample_vtt_content):
        """Test successful VTT deduplication."""
        dedup = VTTDeduplicator(fs=mock_fs)

        input_path = Path("/input.vtt")
        output_path = Path("/output.md")
        mock_fs.write_text(input_path, sample_vtt_content)

        line_count = dedup.deduplicate_vtt(input_path, output_path)

        assert line_count == 3  # Duplicates should be removed
        content = mock_fs.read_text(output_path)
        lines = content.split('\n')
        assert len(lines) == 3
        assert "[00:00:01.000] First line of text" in content
        assert "[00:00:05.000] Second line of text" in content
        assert "[00:00:07.000] Third line of text" in content

    def test_deduplicate_vtt_file_not_found(self, mock_fs):
        """Test error when input file doesn't exist."""
        dedup = VTTDeduplicator(fs=mock_fs)

        with pytest.raises(FileOperationError, match="not found"):
            dedup.deduplicate_vtt(Path("/nonexistent.vtt"), Path("/output.md"))

    def test_deduplicate_vtt_no_text_extracted(self, mock_fs):
        """Test error when no text is extracted."""
        dedup = VTTDeduplicator(fs=mock_fs)

        input_path = Path("/input.vtt")
        output_path = Path("/output.md")
        mock_fs.write_text(input_path, "WEBVTT\n\n")  # Only header, no content

        with pytest.raises(FileOperationError, match="No text extracted"):
            dedup.deduplicate_vtt(input_path, output_path)

    def test_deduplicate_vtt_removes_duplicates(self, mock_fs):
        """Test that duplicate lines are properly removed."""
        dedup = VTTDeduplicator(fs=mock_fs)

        vtt_content = """WEBVTT

00:00:01.000 --> 00:00:02.000
Same text

00:00:02.000 --> 00:00:03.000
Same text

00:00:03.000 --> 00:00:04.000
Different text

00:00:04.000 --> 00:00:05.000
Same text
"""
        input_path = Path("/input.vtt")
        output_path = Path("/output.md")
        mock_fs.write_text(input_path, vtt_content)

        line_count = dedup.deduplicate_vtt(input_path, output_path)

        assert line_count == 2  # Only "Same text" and "Different text"
        content = mock_fs.read_text(output_path)
        assert content.count("Same text") == 1
        assert content.count("Different text") == 1

    def test_deduplicate_vtt_with_no_timestamps_output(self, mock_fs, sample_vtt_content):
        """Test writing additional file without timestamps."""
        dedup = VTTDeduplicator(fs=mock_fs)

        input_path = Path("/input.vtt")
        output_path = Path("/output.md")
        no_timestamps_path = Path("/output_plain.md")
        mock_fs.write_text(input_path, sample_vtt_content)

        line_count = dedup.deduplicate_vtt(input_path, output_path, no_timestamps_path)

        assert line_count == 3
        # Check timestamped output
        content = mock_fs.read_text(output_path)
        assert "[00:00:01.000] First line of text" in content

        # Check plain output (no timestamps)
        plain_content = mock_fs.read_text(no_timestamps_path)
        lines = plain_content.split('\n')
        assert len(lines) == 3
        assert lines[0] == "First line of text"
        assert lines[1] == "Second line of text"
        assert lines[2] == "Third line of text"
        # Verify no timestamps in plain output
        assert "[00:00:" not in plain_content
