#!/usr/bin/env python3
"""Concatenate cleaned transcript chunks and clean temporary chunk files.

Usage:
    34_concat_cleaned.py <CHUNK_1> [<CHUNK_2> ...] <OUTPUT_MD>
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

CHUNK_NAME_PATTERN = re.compile(r"^(?P<prefix>.+_chunk_\d{3})(?P<cleaned>_cleaned)?\.md$")


def normalize_chunk_content(content: str) -> str:
    """Normalize chunk edges for stable concatenation boundaries.

    Args:
        content: Chunk markdown content.

    Returns:
        Chunk content without leading or trailing newline runs.
    """
    return content.strip("\n")


def concatenate_chunks(chunk_paths: list[Path]) -> str:
    """Read and concatenate chunk files with single blank-line boundaries.

    Args:
        chunk_paths: Ordered chunk paths.

    Returns:
        Concatenated transcript content.
    """
    normalized_chunks = [normalize_chunk_content(path.read_text()) for path in chunk_paths]
    return "\n\n".join(normalized_chunks)


def cleanup_targets_for_chunk(chunk_path: Path) -> set[Path]:
    """Return cleanup paths for a chunk and its counterpart variant.

    Args:
        chunk_path: Either raw chunk path or cleaned chunk path.

    Returns:
        Paths that should be removed after successful concatenation.
    """
    targets: set[Path] = {chunk_path}
    match = CHUNK_NAME_PATTERN.match(chunk_path.name)
    if match is None:
        return targets

    base_prefix = match.group("prefix")
    targets.add(chunk_path.parent / f"{base_prefix}.md")
    targets.add(chunk_path.parent / f"{base_prefix}_cleaned.md")
    return targets


def cleanup_chunk_files(chunk_paths: list[Path], output_path: Path) -> None:
    """Delete chunk artifacts after successful output write.

    Args:
        chunk_paths: Input chunk paths used for concatenation.
        output_path: Final output path that must be preserved.
    """
    output_resolved = output_path.resolve()
    cleanup_paths: set[Path] = set()
    for chunk_path in chunk_paths:
        cleanup_paths.update(cleanup_targets_for_chunk(chunk_path))

    for path in cleanup_paths:
        try:
            if path.resolve() == output_resolved:
                continue
        except FileNotFoundError:
            # Missing path cannot be equal to output; continue to unlink check.
            pass

        if path.exists():
            path.unlink()


def main() -> None:
    """CLI entry point."""
    if len(sys.argv) < 3:
        print("Usage: 34_concat_cleaned.py <CHUNK_1> [<CHUNK_2> ...] <OUTPUT_MD>", file=sys.stderr)
        sys.exit(2)

    chunk_paths = [Path(arg) for arg in sys.argv[1:-1]]
    output_path = Path(sys.argv[-1])

    missing_paths = [path for path in chunk_paths if not path.exists()]
    if missing_paths:
        print(f"ERROR: missing chunk files: {', '.join(str(path) for path in missing_paths)}", file=sys.stderr)
        sys.exit(1)

    concatenated = concatenate_chunks(chunk_paths)
    output_path.write_text(concatenated)
    cleanup_chunk_files(chunk_paths, output_path)


if __name__ == "__main__":
    main()
