#!/usr/bin/env python3
"""File operations for YouTube to Markdown: backup and cleanup.

Usage:
    40_backup.py backup <file>
        Create timestamped backup: {file}_backup_{YYYYMMDD}.md

    40_backup.py cleanup <output_dir> <video_id>
        Remove intermediate work files for given video_id
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.file_ops import FileOps


def main():
    """CLI entry point."""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]

    if command == "backup":
        if len(sys.argv) != 3:
            print("Usage: 40_backup.py backup <file>")
            sys.exit(1)

        file_path = Path(sys.argv[2])
        file_ops = FileOps()
        backup_path = file_ops.backup(file_path)
        print(f"Created backup: {backup_path}")

    elif command == "cleanup":
        if len(sys.argv) != 4:
            print("Usage: 40_backup.py cleanup <output_dir> <video_id>")
            sys.exit(1)

        output_dir = Path(sys.argv[2])
        video_id = sys.argv[3]
        file_ops = FileOps()
        removed = file_ops.cleanup(output_dir, video_id)
        print(f"Removed {removed} intermediate files")

    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
