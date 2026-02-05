#!/usr/bin/env python3
"""
Checks comment growth for existing videos by comparing stored vs current counts.

Usage: 23_check_comment_growth.py <OUTPUT_DIR> <VIDEO_ID_1> [VIDEO_ID_2] ...
Output: JSON with per-video growth analysis.

Rate limiting: 1s Python-level delay between individual video metadata fetches.
"""

import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.channel_listing import check_comment_growth


def fetch_comment_counts(video_ids: list[str]) -> dict[str, int]:
    """Fetch current comment counts from YouTube.

    Args:
        video_ids: List of YouTube video IDs.

    Returns:
        Dict mapping video_id to current comment_count.
    """
    counts: dict[str, int] = {}
    for i, vid in enumerate(video_ids):
        if i > 0:
            time.sleep(1)  # rate limiting between requests
        url = f"https://www.youtube.com/watch?v={vid}"
        result = subprocess.run(
            [
                "yt-dlp",
                "--dump-single-json",
                "--skip-download",
                "--no-write-comments",
                url,
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            try:
                data = json.loads(result.stdout)
                count = data.get("comment_count")
                if count is not None:
                    counts[vid] = count
            except json.JSONDecodeError:
                print(f"WARNING: Failed to parse metadata for {vid}", file=sys.stderr)
    return counts


def main() -> None:
    """CLI entry point."""
    if len(sys.argv) < 3:
        print(
            "Usage: 23_check_comment_growth.py <OUTPUT_DIR> <VIDEO_ID_1> [VIDEO_ID_2] ...",
            file=sys.stderr,
        )
        sys.exit(1)

    output_dir = Path(sys.argv[1])
    video_ids = sys.argv[2:]

    if not output_dir.exists():
        print(json.dumps({"error": f"Output directory not found: {output_dir}"}))
        sys.exit(1)

    # Fetch current comment counts from YouTube
    current_counts = fetch_comment_counts(video_ids)

    # Compare against stored values
    results = check_comment_growth(current_counts, output_dir)

    output = {
        "results": results,
        "rate_limit_note": f"Checked {len(current_counts)} videos with 1s delay between requests",
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
