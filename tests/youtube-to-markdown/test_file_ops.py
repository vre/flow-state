"""Tests for file_ops module."""

import pytest
from pathlib import Path
from datetime import datetime
from file_ops import FileOps


class TestBackup:
    """Tests for backup command."""

    def test_backup_creates_timestamped_copy(self, mock_fs):
        """Test backup creates file with timestamp suffix."""
        file_ops = FileOps(fs=mock_fs)

        original = Path("/output/test_file.md")
        mock_fs.write_text(original, "Original content")

        backup_path = file_ops.backup(original)

        # Check backup was created with timestamp (YYYYMMDD_HHMMSS)
        today = datetime.now().strftime("%Y%m%d")
        assert backup_path.name.startswith(f"test_file_backup_{today}_")
        assert backup_path.name.endswith(".md")
        assert backup_path.parent == original.parent
        assert mock_fs.exists(backup_path)
        assert mock_fs.read_text(backup_path) == "Original content"

    def test_backup_preserves_original(self, mock_fs):
        """Test backup does not modify original file."""
        file_ops = FileOps(fs=mock_fs)

        original = Path("/output/test_file.md")
        mock_fs.write_text(original, "Original content")

        file_ops.backup(original)

        assert mock_fs.exists(original)
        assert mock_fs.read_text(original) == "Original content"

    def test_backup_nonexistent_file_raises_error(self, mock_fs):
        """Test backup of nonexistent file raises FileOperationError."""
        from shared_types import FileOperationError

        file_ops = FileOps(fs=mock_fs)

        with pytest.raises(FileOperationError, match="not found"):
            file_ops.backup(Path("/output/nonexistent.md"))

    def test_backup_handles_complex_filename(self, mock_fs):
        """Test backup handles filename with multiple dots."""
        file_ops = FileOps(fs=mock_fs)

        original = Path("/output/youtube - Video Title (abc123).md")
        mock_fs.write_text(original, "Content")

        backup_path = file_ops.backup(original)

        today = datetime.now().strftime("%Y%m%d")
        assert backup_path.name.startswith(f"youtube - Video Title (abc123)_backup_{today}_")
        assert backup_path.name.endswith(".md")


class TestCleanup:
    """Tests for cleanup command."""

    def test_cleanup_removes_intermediate_files(self, mock_fs):
        """Test cleanup removes all intermediate work files."""
        file_ops = FileOps(fs=mock_fs)

        output_dir = Path("/output")
        video_id = "test123"
        base_name = f"youtube_{video_id}"

        # Create intermediate files
        intermediate_files = [
            f"{base_name}_title.txt",
            f"{base_name}_metadata.md",
            f"{base_name}_summary.md",
            f"{base_name}_summary_tight.md",
            f"{base_name}_description.md",
            f"{base_name}_chapters.json",
            f"{base_name}_transcript.vtt",
            f"{base_name}_transcript_dedup.md",
            f"{base_name}_transcript_no_timestamps.txt",
            f"{base_name}_transcript_paragraphs.txt",
            f"{base_name}_transcript_paragraphs.md",
            f"{base_name}_transcript_cleaned.md",
            f"{base_name}_transcript.md",
        ]

        for filename in intermediate_files:
            mock_fs.write_text(output_dir / filename, "intermediate content")

        file_ops.cleanup(output_dir, video_id)

        # All intermediate files should be removed
        for filename in intermediate_files:
            assert not mock_fs.exists(output_dir / filename), f"{filename} should be removed"

    def test_cleanup_preserves_final_files(self, mock_fs):
        """Test cleanup does not remove final output files."""
        file_ops = FileOps(fs=mock_fs)

        output_dir = Path("/output")
        video_id = "test123"
        base_name = f"youtube_{video_id}"

        # Create intermediate file
        mock_fs.write_text(output_dir / f"{base_name}_metadata.md", "intermediate")

        # Create final files (should be preserved)
        final_summary = output_dir / "youtube - Test Video (test123).md"
        final_transcript = output_dir / "youtube - Test Video - transcript (test123).md"
        mock_fs.write_text(final_summary, "final summary")
        mock_fs.write_text(final_transcript, "final transcript")

        file_ops.cleanup(output_dir, video_id)

        # Final files should still exist
        assert mock_fs.exists(final_summary)
        assert mock_fs.exists(final_transcript)

    def test_cleanup_handles_missing_files(self, mock_fs):
        """Test cleanup handles case where some intermediate files don't exist."""
        file_ops = FileOps(fs=mock_fs)

        output_dir = Path("/output")
        video_id = "test123"
        base_name = f"youtube_{video_id}"

        # Only create some intermediate files
        mock_fs.write_text(output_dir / f"{base_name}_metadata.md", "content")
        mock_fs.write_text(output_dir / f"{base_name}_summary.md", "content")

        # Should not raise error
        file_ops.cleanup(output_dir, video_id)

        assert not mock_fs.exists(output_dir / f"{base_name}_metadata.md")
        assert not mock_fs.exists(output_dir / f"{base_name}_summary.md")

    def test_cleanup_empty_directory(self, mock_fs):
        """Test cleanup handles empty output directory."""
        file_ops = FileOps(fs=mock_fs)

        output_dir = Path("/output")
        mock_fs.mkdir(output_dir)

        # Should not raise error
        file_ops.cleanup(output_dir, "test123")

    def test_cleanup_returns_removed_count(self, mock_fs):
        """Test cleanup returns count of removed files."""
        file_ops = FileOps(fs=mock_fs)

        output_dir = Path("/output")
        video_id = "test123"
        base_name = f"youtube_{video_id}"

        # Create 3 intermediate files
        mock_fs.write_text(output_dir / f"{base_name}_metadata.md", "content")
        mock_fs.write_text(output_dir / f"{base_name}_summary.md", "content")
        mock_fs.write_text(output_dir / f"{base_name}_title.txt", "content")

        removed_count = file_ops.cleanup(output_dir, video_id)

        assert removed_count == 3
