#!/usr/bin/env python3
"""Fetches video descriptions for informed selection in channel browser.

Usage: 24_enrich_metadata.py <VIDEO_ID_1> [VIDEO_ID_2] ...
Output: JSON array of {video_id, description} — single-line text, ≤200 chars.

Rate limiting: 1s Python-level delay between requests.
"""

import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def fetch_descriptions(video_ids: list[str]) -> list[dict]:
    """Fetch video descriptions from YouTube.

    Returns single-line text (≤200 chars). Content safety wrapping is the
    caller's responsibility — raw text is needed for user-facing checkbox files.

    Args:
        video_ids: List of YouTube video IDs.

    Returns:
        List of dicts with video_id and description.
    """
    results: list[dict] = []
    for i, vid in enumerate(video_ids):
        if i > 0:
            time.sleep(1)
        url = f"https://www.youtube.com/watch?v={vid}"
        result = subprocess.run(
            [
                "yt-dlp",
                "--dump-json",
                "--skip-download",
                "--no-write-comments",
                url,
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            print(f"WARNING: Failed to fetch metadata for {vid}", file=sys.stderr)
            results.append({"video_id": vid, "description": ""})
            continue

        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            print(f"WARNING: Failed to parse metadata for {vid}", file=sys.stderr)
            results.append({"video_id": vid, "description": ""})
            continue

        desc = data.get("description") or ""
        # Keep selection file stable and avoid multiline markdown injection.
        desc = desc.replace("\r", " ").replace("\n", " ")
        results.append({"video_id": vid, "description": desc[:200]})

    return results


def main() -> None:
    """CLI entry point."""
    if len(sys.argv) < 2:
        print(
            "Usage: 24_enrich_metadata.py <VIDEO_ID_1> [VIDEO_ID_2] ...",
            file=sys.stderr,
        )
        sys.exit(2)

    video_ids = sys.argv[1:]
    results = fetch_descriptions(video_ids)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
