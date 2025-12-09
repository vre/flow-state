"""Tests for finalize module."""

import pytest
from pathlib import Path
from finalize import Finalizer
from shared_types import FileOperationError


class TestFinalizer:
    """Tests for Finalizer class."""

    def test_read_template_success(self, mock_fs, sample_template):
        """Test successful template reading."""
        finalizer = Finalizer(fs=mock_fs)

        template_path = Path("/script_dir/template.md")
        mock_fs.write_text(template_path, sample_template)

        result = finalizer.read_template(Path("/script_dir"))
        assert result == sample_template

    def test_read_template_not_found(self, mock_fs):
        """Test error when template doesn't exist."""
        finalizer = Finalizer(fs=mock_fs)

        with pytest.raises(FileOperationError, match="not found"):
            finalizer.read_template(Path("/script_dir"))

    def test_read_component_or_empty_exists(self, mock_fs):
        """Test reading existing component file."""
        finalizer = Finalizer(fs=mock_fs)

        path = Path("/output/component.md")
        mock_fs.write_text(path, "Component content")

        result = finalizer.read_component_or_empty(path)
        assert result == "Component content"

    def test_read_component_or_empty_not_exists(self, mock_fs):
        """Test reading non-existent component file."""
        finalizer = Finalizer(fs=mock_fs)

        result = finalizer.read_component_or_empty(Path("/output/nonexistent.md"))
        assert result == ""

    def test_create_final_filename_with_title(self, mock_fs):
        """Test creating filename with title."""
        finalizer = Finalizer(fs=mock_fs)

        title_path = Path("/output/youtube_test123_title.txt")
        mock_fs.write_text(title_path, "Test Video Title")

        result = finalizer.create_final_filename("youtube_test123", Path("/output"))
        assert result == "youtube - Test Video Title (test123).md"

    def test_create_final_filename_without_title(self, mock_fs):
        """Test creating filename when title doesn't exist."""
        finalizer = Finalizer(fs=mock_fs)

        result = finalizer.create_final_filename("youtube_test123", Path("/output"))
        assert result == "youtube_test123.md"

    def test_create_final_filename_cleans_title(self, mock_fs):
        """Test that title is cleaned for filename."""
        finalizer = Finalizer(fs=mock_fs)

        title_path = Path("/output/youtube_test123_title.txt")
        mock_fs.write_text(title_path, 'Test: Video | "Title"')

        result = finalizer.create_final_filename("youtube_test123", Path("/output"))
        assert result == "youtube - Test Video Title (test123).md"

    def test_assemble_final_content(self, mock_fs, sample_template):
        """Test assembling summary content from components."""
        finalizer = Finalizer(fs=mock_fs)

        base_name = "youtube_test123"
        output_dir = Path("/output")

        # Create component files
        mock_fs.write_text(output_dir / f"{base_name}_metadata.md", "Metadata content")
        mock_fs.write_text(output_dir / f"{base_name}_summary_tight.md", "Summary content")

        result = finalizer.assemble_final_content(sample_template, base_name, output_dir)

        assert "Metadata content" in result
        assert "Summary content" in result
        assert "{metadata}" not in result  # Placeholders should be replaced

    def test_assemble_transcript_content(self, mock_fs, sample_transcript_template):
        """Test assembling transcript content from components."""
        finalizer = Finalizer(fs=mock_fs)

        base_name = "youtube_test123"
        output_dir = Path("/output")

        # Create component files
        mock_fs.write_text(output_dir / f"{base_name}_description.md", "Description content")
        mock_fs.write_text(output_dir / f"{base_name}_transcript.md", "Transcript content")

        result = finalizer.assemble_transcript_content(sample_transcript_template, base_name, output_dir)

        assert "Description content" in result
        assert "Transcript content" in result
        assert "{description}" not in result  # Placeholders should be replaced

    def test_assemble_final_content_missing_components(self, mock_fs, sample_template):
        """Test assembling with missing component files."""
        finalizer = Finalizer(fs=mock_fs)

        base_name = "youtube_test123"
        output_dir = Path("/output")

        # Only create metadata file
        mock_fs.write_text(output_dir / f"{base_name}_metadata.md", "Metadata content")

        result = finalizer.assemble_final_content(sample_template, base_name, output_dir)

        assert "Metadata content" in result
        # Missing components should be empty, not error
        assert "## Summary" in result

    def test_cleanup_work_files(self, mock_fs):
        """Test cleanup of intermediate work files."""
        finalizer = Finalizer(fs=mock_fs)

        base_name = "youtube_test123"
        output_dir = Path("/output")

        # Create work files
        work_files = [
            f"{base_name}_title.txt",
            f"{base_name}_metadata.md",
            f"{base_name}_summary.md",
            f"{base_name}_description.md",
            f"{base_name}_chapters.json",
            f"{base_name}_transcript.vtt",
            f"{base_name}_transcript_dedup.md",
            f"{base_name}_transcript_no_timestamps.txt",
            f"{base_name}_transcript_paragraphs.md",
            f"{base_name}_transcript_cleaned.md",
            f"{base_name}_transcript.md"
        ]

        for work_file in work_files:
            mock_fs.write_text(output_dir / work_file, "content")

        # Create final file (should not be deleted)
        final_file = output_dir / "youtube - Test (test123).md"
        mock_fs.write_text(final_file, "final content")

        finalizer.cleanup_work_files(base_name, output_dir)

        # Work files should be deleted
        for work_file in work_files:
            assert not mock_fs.exists(output_dir / work_file)

        # Final file should still exist
        assert mock_fs.exists(final_file)

    def test_finalize_complete_flow(self, mock_fs, sample_template, sample_transcript_template):
        """Test complete finalization flow."""
        finalizer = Finalizer(fs=mock_fs)

        base_name = "youtube_test123"
        output_dir = Path("/output")
        script_dir = Path("/script_dir")

        # Setup files
        mock_fs.write_text(script_dir / "template.md", sample_template)
        mock_fs.write_text(script_dir / "template_transcript.md", sample_transcript_template)
        mock_fs.write_text(output_dir / f"{base_name}_title.txt", "Test Video")
        mock_fs.write_text(output_dir / f"{base_name}_metadata.md", "Metadata")
        mock_fs.write_text(output_dir / f"{base_name}_summary.md", "Summary")
        mock_fs.write_text(output_dir / f"{base_name}_description.md", "Description")
        mock_fs.write_text(output_dir / f"{base_name}_transcript.md", "Transcript")

        # Mock __file__ path
        import finalize as finalize_module
        original_file = finalize_module.__file__
        try:
            finalize_module.__file__ = str(script_dir / "finalize.py")

            summary_path, transcript_path = finalizer.finalize(base_name, output_dir, debug=False)

            # Check both files were created
            assert summary_path.name == "youtube - Test Video (test123).md"
            assert transcript_path.name == "youtube - Test Video - transcript (test123).md"
            assert mock_fs.exists(summary_path)
            assert mock_fs.exists(transcript_path)

            # Check summary content
            summary_content = mock_fs.read_text(summary_path)
            assert "Metadata" in summary_content
            assert "Summary" in summary_content
            assert "Description" not in summary_content  # Should not be in summary
            assert "Transcript" not in summary_content  # Should not be in summary

            # Check transcript content
            transcript_content = mock_fs.read_text(transcript_path)
            assert "Description" in transcript_content
            assert "Transcript" in transcript_content

            # Work files should be cleaned up
            assert not mock_fs.exists(output_dir / f"{base_name}_metadata.md")

        finally:
            finalize_module.__file__ = original_file

    def test_finalize_debug_mode(self, mock_fs, sample_template, sample_transcript_template):
        """Test finalization with debug mode (keeps work files)."""
        finalizer = Finalizer(fs=mock_fs)

        base_name = "youtube_test123"
        output_dir = Path("/output")
        script_dir = Path("/script_dir")

        # Setup files
        mock_fs.write_text(script_dir / "template.md", sample_template)
        mock_fs.write_text(script_dir / "template_transcript.md", sample_transcript_template)
        mock_fs.write_text(output_dir / f"{base_name}_title.txt", "Test Video")
        mock_fs.write_text(output_dir / f"{base_name}_metadata.md", "Metadata")
        mock_fs.write_text(output_dir / f"{base_name}_description.md", "Description")
        mock_fs.write_text(output_dir / f"{base_name}_transcript.md", "Transcript")

        import finalize as finalize_module
        original_file = finalize_module.__file__
        try:
            finalize_module.__file__ = str(script_dir / "finalize.py")

            summary_path, transcript_path = finalizer.finalize(base_name, output_dir, debug=True)

            # Both final files should be created
            assert mock_fs.exists(summary_path)
            assert mock_fs.exists(transcript_path)

            # Work files should NOT be cleaned up in debug mode
            assert mock_fs.exists(output_dir / f"{base_name}_metadata.md")

        finally:
            finalize_module.__file__ = original_file
