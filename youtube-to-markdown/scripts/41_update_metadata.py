#!/usr/bin/env python3
"""Updates metadata section in existing summary file.

Usage: 41_update_metadata.py <SUMMARY_PATH> <METADATA_PATH>

Replaces the "## Video" section content with fresh metadata from metadata file.
Creates backup of original summary before modification.
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.update_metadata import replace_metadata_section, update_extraction_date


def main() -> None:
    """CLI entry point."""
    if len(sys.argv) != 3:
        print("Usage: 41_update_metadata.py <SUMMARY_PATH> <METADATA_PATH>", file=sys.stderr)
        sys.exit(1)

    summary_path = Path(sys.argv[1])
    metadata_path = Path(sys.argv[2])

    if not summary_path.exists():
        print(f"ERROR: Summary file not found: {summary_path}", file=sys.stderr)
        sys.exit(1)

    if not metadata_path.exists():
        print(f"ERROR: Metadata file not found: {metadata_path}", file=sys.stderr)
        sys.exit(1)

    summary = summary_path.read_text()
    fresh_metadata = metadata_path.read_text()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{summary_path.stem}_backup_{timestamp}{summary_path.suffix}"
    backup_path = summary_path.parent / backup_name
    backup_path.write_text(summary)
    print(f"Backup created: {backup_path}")

    updated = replace_metadata_section(summary, fresh_metadata)
    updated = update_extraction_date(updated)

    summary_path.write_text(updated)
    print(f"Updated: {summary_path}")


if __name__ == "__main__":
    main()
