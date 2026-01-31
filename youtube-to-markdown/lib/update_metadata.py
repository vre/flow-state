"""Metadata update library."""

import re
from datetime import datetime


def replace_metadata_section(summary: str, fresh_metadata: str) -> str:
    """Replace metadata section in summary with fresh metadata.
    Looks for "## Video" section and replaces content until next "##" heading.
    """
    pattern = r"(## Video)\s*\n(.*?)(\n## |\Z)"

    def replacement(match):
        heading = match.group(1)
        next_section = match.group(3)
        if next_section.startswith("\n"):
            return f"{heading}\n\n{fresh_metadata.strip()}\n{next_section}"
        return f"{heading}\n\n{fresh_metadata.strip()}"

    updated = re.sub(pattern, replacement, summary, flags=re.DOTALL)

    if updated == summary and "## Video" not in summary:
        lines = summary.split("\n", 1)
        if len(lines) > 1:
            updated = f"{lines[0]}\n\n## Video\n\n{fresh_metadata.strip()}\n\n{lines[1]}"
        else:
            updated = f"{summary}\n\n## Video\n\n{fresh_metadata.strip()}"

    return updated


def update_extraction_date(content: str) -> str:
    """Update the Extracted date in metadata to today."""
    today = datetime.now().strftime("%Y-%m-%d")
    pattern = r"(Extracted:\s*)\d{4}-\d{2}-\d{2}"
    return re.sub(pattern, rf"\g<1>{today}", content)
