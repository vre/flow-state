#!/usr/bin/env python3
"""Dispatch youtube-to-markdown script commands behind one stable entry point."""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_GUARD_MAX_SIZE = 153_600

SCRIPT_MAP: dict[str, str] = {
    "assemble": "50_assemble.py",
    "backup": "40_backup.py",
    "channel": "22_list_channel.py",
    "check": "20_check_existing.py",
    "clean-vtt": "30_clean_vtt.py",
    "comments": "13_extract_comments.py",
    "concat-cleaned": "34_concat_cleaned.py",
    "filter-comments": "32_filter_comments.py",
    "format-transcript": "31_format_transcript.py",
    "insert-headings": "35_insert_headings_from_json.py",
    "paragraph-breaks": "37_paragraph_breaks.py",
    "merge-tier2": "33_merge_tier2.py",
    "metadata": "10_extract_metadata.py",
    "prepare-update": "21_prepare_update.py",
    "resolve-summary": "36_resolve_summary.py",
    "split-chunks": "33_split_for_cleaning.py",
    "transcript": "11_extract_transcript.py",
    "transcript-whisper": "12_extract_transcript_whisper.py",
    "update-metadata": "41_update_metadata.py",
}

BUILTIN_COMMANDS = ("flag", "guard", "rm")


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI parser."""
    parser = argparse.ArgumentParser(
        description="Run youtube-to-markdown helper scripts through one stable CLI.",
    )
    parser.add_argument(
        "command",
        choices=sorted([*SCRIPT_MAP.keys(), *BUILTIN_COMMANDS]),
        help="Dispatcher subcommand.",
    )
    parser.add_argument(
        "args",
        nargs=argparse.REMAINDER,
        help="Arguments passed through to the selected subcommand.",
    )
    return parser


def parse_single_path(command: str, args: Sequence[str]) -> Path:
    """Parse one required path argument for simple built-ins."""
    parser = argparse.ArgumentParser(prog=f"run.py {command}")
    parser.add_argument("path")
    namespace = parser.parse_args(list(args))
    return Path(namespace.path)


def parse_guard_args(args: Sequence[str]) -> argparse.Namespace:
    """Parse arguments for the guard built-in."""
    parser = argparse.ArgumentParser(prog="run.py guard")
    parser.add_argument("path")
    parser.add_argument("--max-size", type=int, default=DEFAULT_GUARD_MAX_SIZE)
    return parser.parse_args(list(args))


def dispatch_script(command: str, args: Sequence[str]) -> int:
    """Run an existing numbered script and return its exit code."""
    script_path = SCRIPT_DIR / SCRIPT_MAP[command]
    if not script_path.exists():
        print(f"Missing dispatcher target: {script_path}", file=sys.stderr)
        return 1

    result = subprocess.run([sys.executable, str(script_path), *args])
    return result.returncode


def run_flag(args: Sequence[str]) -> int:
    """Create or overwrite a marker file."""
    path = parse_single_path("flag", args)
    path.write_text("1\n", encoding="utf-8")
    return 0


def run_rm(args: Sequence[str]) -> int:
    """Delete a file if it exists."""
    path = parse_single_path("rm", args)
    path.unlink(missing_ok=True)
    return 0


def run_guard(args: Sequence[str]) -> int:
    """Print whether a file is present and below the size threshold."""
    namespace = parse_guard_args(args)
    path = Path(namespace.path)

    if not path.exists():
        print("skip: file missing")
        return 0

    if path.stat().st_size > namespace.max_size:
        print(f"skip: file >{namespace.max_size} bytes")
        return 0

    print("ok")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point."""
    parser = build_parser()
    namespace = parser.parse_args(list(argv) if argv is not None else None)

    if namespace.command in SCRIPT_MAP:
        return dispatch_script(namespace.command, namespace.args)
    if namespace.command == "flag":
        return run_flag(namespace.args)
    if namespace.command == "rm":
        return run_rm(namespace.args)
    if namespace.command == "guard":
        return run_guard(namespace.args)

    parser.error(f"Unknown command: {namespace.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
