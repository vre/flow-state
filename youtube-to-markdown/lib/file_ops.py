"""File operations library: backup and cleanup."""

from datetime import datetime
from pathlib import Path

from lib.intermediate_files import get_all_work_files
from lib.shared_types import FileOperationError, FileSystem, RealFileSystem


class FileOps:
    """File operations: backup and cleanup."""

    def __init__(self, fs: FileSystem | None = None):
        self.fs = fs or RealFileSystem()

    def backup(self, file_path: Path) -> Path:
        if not self.fs.exists(file_path):
            raise FileOperationError(f"File not found: {file_path}")

        content = self.fs.read_text(file_path)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stem = file_path.stem
        suffix = file_path.suffix
        backup_name = f"{stem}_backup_{timestamp}{suffix}"
        backup_path = file_path.parent / backup_name

        self.fs.write_text(backup_path, content)
        return backup_path

    def cleanup(self, output_dir: Path, video_id: str) -> int:
        base_name = f"youtube_{video_id}"
        removed_count = 0

        for filename in get_all_work_files(base_name):
            file_path = output_dir / filename
            if self.fs.exists(file_path):
                self.fs.remove(file_path)
                removed_count += 1

        return removed_count
