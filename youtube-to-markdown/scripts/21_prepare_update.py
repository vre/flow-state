#!/usr/bin/env python3
"""Analyzes existing extraction and prepares update recommendations.

Usage: 21_prepare_update.py <YOUTUBE_URL> <OUTPUT_DIR>
Output: JSON with status, metadata changes, issues, and recommendation.

Exit codes:
  0 - Success, JSON output with recommendation
  1 - Error (invalid args, video unavailable, etc.)
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.prepare_update import prepare_update


def main() -> None:
    """CLI entry point."""
    if len(sys.argv) != 3:
        print("Usage: 21_prepare_update.py <YOUTUBE_URL> <OUTPUT_DIR>", file=sys.stderr)
        sys.exit(1)

    video_url = sys.argv[1]
    output_dir = Path(sys.argv[2])

    try:
        result = prepare_update(video_url, output_dir)
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(json.dumps({"status": "ERROR", "message": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
