#!/usr/bin/env python3
"""Resolve the best available summary file for synthesis."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib.assembler import Finalizer


def main() -> None:
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <base_name> <output_directory>", file=sys.stderr)
        sys.exit(1)

    base = sys.argv[1]
    d = Path(sys.argv[2])

    tight = d / f"{base}_summary_tight.md"
    if tight.exists():
        print(json.dumps({"summary": str(tight)}))
        return

    f = Finalizer()
    video_id = base.replace("youtube_", "", 1)
    existing = f.find_existing_summary(video_id, d)
    if existing:
        print(json.dumps({"summary": str(existing)}))
        return

    print(json.dumps({"summary": None}))


if __name__ == "__main__":
    main()
