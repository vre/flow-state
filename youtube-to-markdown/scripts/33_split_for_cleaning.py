#!/usr/bin/env python3
"""Split long transcript paragraphs into cleaning chunks.

Usage:
    33_split_for_cleaning.py <INPUT_MD> <OUTPUT_DIR>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

MAX_INPUT_BYTES = 80 * 1024
MAX_CHUNK_BYTES = 40 * 1024
TARGET_PARAGRAPHS = 20


def split_paragraphs(content: str) -> list[str]:
    """Split transcript text into paragraph blocks.

    Args:
        content: Transcript text where paragraphs are separated by blank lines.

    Returns:
        Ordered paragraph blocks.
    """
    if content == "":
        return []
    return content.split("\n\n")


def joined_byte_size(paragraphs: list[str]) -> int:
    """Return UTF-8 byte size when paragraphs are joined.

    Args:
        paragraphs: Paragraph blocks.

    Returns:
        Encoded byte size of paragraph content joined by blank lines.
    """
    if not paragraphs:
        return 0
    return len("\n\n".join(paragraphs).encode("utf-8"))


def build_chunks(
    paragraphs: list[str],
    target_paragraphs: int = TARGET_PARAGRAPHS,
    max_chunk_bytes: int = MAX_CHUNK_BYTES,
) -> list[list[str]]:
    """Group paragraphs into chunk-sized lists.

    Args:
        paragraphs: Ordered transcript paragraphs.
        target_paragraphs: Preferred maximum number of paragraphs per chunk.
        max_chunk_bytes: Hard byte cap per chunk when possible.

    Returns:
        A list of paragraph lists, one list per chunk.
    """
    chunks: list[list[str]] = []
    current_chunk: list[str] = []

    for paragraph in paragraphs:
        candidate_chunk = current_chunk + [paragraph]
        reached_target = len(current_chunk) >= target_paragraphs
        exceeds_size_cap = bool(current_chunk) and joined_byte_size(candidate_chunk) > max_chunk_bytes

        if reached_target or exceeds_size_cap:
            chunks.append(current_chunk)
            current_chunk = [paragraph]
            continue

        current_chunk.append(paragraph)

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def get_base_name(input_path: Path) -> str:
    """Extract base name for chunk files from transcript path.

    Args:
        input_path: Path to transcript paragraphs file.

    Returns:
        Base name used for generated chunk files.
    """
    suffix = "_transcript_paragraphs"
    stem = input_path.stem
    if stem.endswith(suffix):
        return stem[: -len(suffix)]
    return stem


def write_chunks(chunk_groups: list[list[str]], output_dir: Path, base_name: str) -> list[Path]:
    """Write chunk files and return absolute output paths.

    Args:
        chunk_groups: Paragraph groups to write.
        output_dir: Directory for chunk files.
        base_name: Base name prefix for chunk filenames.

    Returns:
        Absolute paths to chunk files in order.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    chunk_paths: list[Path] = []

    for index, chunk in enumerate(chunk_groups, start=1):
        chunk_path = output_dir / f"{base_name}_chunk_{index:03d}.md"
        chunk_path.write_text("\n\n".join(chunk))
        chunk_paths.append(chunk_path.resolve())

    return chunk_paths


def split_for_cleaning(input_path: Path, output_dir: Path) -> list[Path]:
    """Split transcript into chunk files when input exceeds threshold.

    Args:
        input_path: Path to transcript paragraphs markdown.
        output_dir: Destination directory for chunk files.

    Returns:
        Absolute paths to either original file (passthrough) or generated chunks.
    """
    if input_path.stat().st_size <= MAX_INPUT_BYTES:
        return [input_path.resolve()]

    content = input_path.read_text()
    paragraphs = split_paragraphs(content)
    chunk_groups = build_chunks(paragraphs)
    base_name = get_base_name(input_path)
    return write_chunks(chunk_groups, output_dir, base_name)


def main() -> None:
    """CLI entry point."""
    if len(sys.argv) != 3:
        print("Usage: 33_split_for_cleaning.py <INPUT_MD> <OUTPUT_DIR>", file=sys.stderr)
        sys.exit(2)

    input_path = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])

    if not input_path.exists():
        print(f"ERROR: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    chunk_paths = split_for_cleaning(input_path=input_path, output_dir=output_dir)
    payload = {"chunks": [str(path) for path in chunk_paths]}
    print(json.dumps(payload))


if __name__ == "__main__":
    main()
