#!/usr/bin/env python3
"""Generate deterministic paragraph break line numbers for a transcript.

Usage: 37_paragraph_breaks.py <INPUT_MD> <CHAPTERS_JSON> <OUTPUT_TXT>
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.paragraph_breaks import ParagraphBreakPlanner


def main() -> None:
    """CLI entry point."""
    if len(sys.argv) != 4:
        print(
            "Usage: 37_paragraph_breaks.py <INPUT_MD> <CHAPTERS_JSON> <OUTPUT_TXT>",
            file=sys.stderr,
        )
        sys.exit(1)

    transcript_path = Path(sys.argv[1])
    chapters_path = Path(sys.argv[2])
    output_path = Path(sys.argv[3])

    try:
        planner = ParagraphBreakPlanner()
        break_points = planner.compute_break_points(transcript_path, chapters_path)
        output_path.write_text(",".join(str(point) for point in break_points), encoding="utf-8")
        print(f"SUCCESS: {output_path} ({len(break_points)} break points)")
    except Exception as exc:
        print(f"ERROR: {str(exc)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
