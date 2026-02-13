#!/usr/bin/env python3
"""Extracts YouTube video comments.

Usage: 13_extract_comments.py <YOUTUBE_URL> <OUTPUT_DIR>
Output: Creates youtube_{VIDEO_ID}_title.txt, youtube_{VIDEO_ID}_comments.md
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.comment_extractor import CommentExtractor, SubprocessRunner
from lib.shared_types import RealFileSystem


def main() -> None:
    """Main entry point."""
    if len(sys.argv) != 3:
        print("Usage: 13_extract_comments.py <YOUTUBE_URL> <OUTPUT_DIR>", file=sys.stderr)
        sys.exit(1)

    video_url = sys.argv[1]
    output_dir = Path(sys.argv[2])

    if not video_url:
        print("ERROR: No YouTube URL provided", file=sys.stderr)
        sys.exit(1)

    extractor = CommentExtractor(SubprocessRunner(), RealFileSystem())

    try:
        extractor.extract_and_save(video_url, output_dir)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
