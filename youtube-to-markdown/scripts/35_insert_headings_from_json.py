#!/usr/bin/env python3
"""Insert transcript headings from JSON metadata.

Usage:
    35_insert_headings_from_json.py <TRANSCRIPT_MD> <HEADINGS_JSON> <OUTPUT_MD>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TypedDict


class HeadingEntry(TypedDict):
    """Heading insertion instruction."""

    before_paragraph: int
    heading: str


def split_paragraphs(content: str) -> list[str]:
    """Split transcript content into paragraphs separated by blank lines.

    Args:
        content: Transcript markdown content.

    Returns:
        Paragraph blocks in source order.
    """
    if content == "":
        return []
    return content.split("\n\n")


def load_headings(path: Path) -> list[HeadingEntry]:
    """Load and validate heading entries from JSON.

    Args:
        path: Path to headings JSON file.

    Returns:
        Validated heading entries.

    Raises:
        ValueError: If JSON does not follow required schema.
    """
    data = json.loads(path.read_text())
    if not isinstance(data, list):
        raise ValueError("Headings JSON must be an array")

    entries: list[HeadingEntry] = []
    for item in data:
        if not isinstance(item, dict):
            raise ValueError("Each heading entry must be an object")
        before_paragraph = item.get("before_paragraph")
        heading = item.get("heading")
        if not isinstance(before_paragraph, int):
            raise ValueError("before_paragraph must be an integer")
        if not isinstance(heading, str):
            raise ValueError("heading must be a string")
        entries.append({"before_paragraph": before_paragraph, "heading": heading})

    return entries


def group_headings_by_paragraph(
    headings: list[HeadingEntry],
    paragraph_count: int,
) -> dict[int, list[str]]:
    """Group valid headings by target paragraph index.

    Args:
        headings: Heading entries from metadata JSON.
        paragraph_count: Number of paragraphs in transcript.

    Returns:
        Mapping from paragraph index (1-indexed) to ordered heading strings.
    """
    grouped: dict[int, list[str]] = {}
    for entry in headings:
        index = entry["before_paragraph"]
        if index < 1 or index > paragraph_count:
            print(
                (f"WARNING: skipping heading with before_paragraph={index}; out of range 1..{paragraph_count}"),
                file=sys.stderr,
            )
            continue
        grouped.setdefault(index, []).append(entry["heading"])
    return grouped


def insert_headings(paragraphs: list[str], grouped_headings: dict[int, list[str]]) -> str:
    """Insert headings before selected paragraphs.

    Args:
        paragraphs: Transcript paragraph blocks.
        grouped_headings: Headings grouped by target paragraph index.

    Returns:
        Transcript markdown with inserted heading blocks.
    """
    output_blocks: list[str] = []
    for index, paragraph in enumerate(paragraphs, start=1):
        output_blocks.extend(grouped_headings.get(index, []))
        output_blocks.append(paragraph)
    return "\n\n".join(output_blocks)


def main() -> None:
    """CLI entry point."""
    if len(sys.argv) != 4:
        print(
            "Usage: 35_insert_headings_from_json.py <TRANSCRIPT_MD> <HEADINGS_JSON> <OUTPUT_MD>",
            file=sys.stderr,
        )
        sys.exit(2)

    transcript_path = Path(sys.argv[1])
    headings_path = Path(sys.argv[2])
    output_path = Path(sys.argv[3])

    if not transcript_path.exists():
        print(f"ERROR: transcript file not found: {transcript_path}", file=sys.stderr)
        sys.exit(1)
    if not headings_path.exists():
        print(f"ERROR: headings JSON file not found: {headings_path}", file=sys.stderr)
        sys.exit(1)

    paragraphs = split_paragraphs(transcript_path.read_text())
    headings = load_headings(headings_path)
    grouped_headings = group_headings_by_paragraph(headings, paragraph_count=len(paragraphs))
    output_path.write_text(insert_headings(paragraphs, grouped_headings))


if __name__ == "__main__":
    main()
