#!/usr/bin/env python3
"""Checks if a YouTube video has already been processed.
Usage: 20_check_existing.py <YOUTUBE_URL> <OUTPUT_DIR>
Output: JSON with existence status, file paths, format versions, and stored metadata.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.check_existing import check_existing
from lib.shared_types import extract_video_id


def main() -> None:
    """CLI entry point."""
    if len(sys.argv) != 3:
        print("Usage: 20_check_existing.py <YOUTUBE_URL> <OUTPUT_DIR>", file=sys.stderr)
        sys.exit(1)

    video_url = sys.argv[1]
    output_dir = Path(sys.argv[2])

    if not output_dir.exists():
        print(json.dumps({"exists": False, "video_id": extract_video_id(video_url)}))
        sys.exit(0)

    result = check_existing(video_url, output_dir)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
