#!/usr/bin/env python3
"""Extracts YouTube video data: metadata, description, and chapters
Usage: 10_extract_metadata.py <YOUTUBE_URL> <OUTPUT_DIR>
Output: Creates youtube_{VIDEO_ID}_metadata.md, youtube_{VIDEO_ID}_description.md, youtube_{VIDEO_ID}_chapters.json
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.youtube_extractor import YouTubeDataExtractor


def main() -> None:
    """CLI entry point."""
    if len(sys.argv) != 3:
        print("Usage: 10_extract_metadata.py <YOUTUBE_URL> <OUTPUT_DIR>", file=sys.stderr)
        sys.exit(1)

    video_url = sys.argv[1]
    output_dir = Path(sys.argv[2])

    if not video_url:
        print("ERROR: No YouTube URL provided", file=sys.stderr)
        sys.exit(1)

    try:
        extractor = YouTubeDataExtractor()
        extractor.extract_all(video_url, output_dir)
    except Exception as e:
        print(f"ERROR: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
