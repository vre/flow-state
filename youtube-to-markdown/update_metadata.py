#!/usr/bin/env python3
"""
Updates metadata section in existing summary file.

Usage: update_metadata.py <SUMMARY_PATH> <METADATA_PATH>

Replaces the "## Video" section content with fresh metadata from metadata file.
Creates backup of original summary before modification.
"""

import re
import sys
from datetime import datetime
from pathlib import Path


def replace_metadata_section(summary: str, fresh_metadata: str) -> str:
    """
    Replace metadata section in summary with fresh metadata.

    Looks for "## Video" section and replaces content until next "##" heading.

    Args:
        summary: Original summary content
        fresh_metadata: New metadata content to insert

    Returns:
        Updated summary content
    """
    # Pattern: ## Video followed by content until next ## or end
    pattern = r"(## Video)\s*\n(.*?)(\n## |\Z)"

    def replacement(match):
        heading = match.group(1)
        next_section = match.group(3)
        # next_section starts with \n## or is empty (end of file)
        if next_section.startswith("\n"):
            return f"{heading}\n\n{fresh_metadata.strip()}\n{next_section}"
        return f"{heading}\n\n{fresh_metadata.strip()}"

    updated = re.sub(pattern, replacement, summary, flags=re.DOTALL)

    # If pattern didn't match, summary might not have ## Video section
    if updated == summary and "## Video" not in summary:
        # Insert after first line (title)
        lines = summary.split("\n", 1)
        if len(lines) > 1:
            updated = f"{lines[0]}\n\n## Video\n\n{fresh_metadata.strip()}\n\n{lines[1]}"
        else:
            updated = f"{summary}\n\n## Video\n\n{fresh_metadata.strip()}"

    return updated


def update_extraction_date(content: str) -> str:
    """Update the Extracted date in metadata to today."""
    today = datetime.now().strftime("%Y-%m-%d")
    # Match: Extracted: YYYY-MM-DD
    pattern = r"(Extracted:\s*)\d{4}-\d{2}-\d{2}"
    return re.sub(pattern, rf"\g<1>{today}", content)


def main() -> None:
    """CLI entry point."""
    if len(sys.argv) != 3:
        print("Usage: update_metadata.py <SUMMARY_PATH> <METADATA_PATH>", file=sys.stderr)
        sys.exit(1)

    summary_path = Path(sys.argv[1])
    metadata_path = Path(sys.argv[2])

    if not summary_path.exists():
        print(f"ERROR: Summary file not found: {summary_path}", file=sys.stderr)
        sys.exit(1)

    if not metadata_path.exists():
        print(f"ERROR: Metadata file not found: {metadata_path}", file=sys.stderr)
        sys.exit(1)

    # Read files
    summary = summary_path.read_text()
    fresh_metadata = metadata_path.read_text()

    # Create backup
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{summary_path.stem}_backup_{timestamp}{summary_path.suffix}"
    backup_path = summary_path.parent / backup_name
    backup_path.write_text(summary)
    print(f"Backup created: {backup_path}")

    # Update metadata section
    updated = replace_metadata_section(summary, fresh_metadata)
    updated = update_extraction_date(updated)

    # Write updated summary
    summary_path.write_text(updated)
    print(f"Updated: {summary_path}")


if __name__ == "__main__":
    main()
