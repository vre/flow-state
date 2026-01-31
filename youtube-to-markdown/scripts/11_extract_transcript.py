#!/usr/bin/env python3
"""Detects video language, lists available subtitles, tries manual subtitles first, falls back to auto-generated.
Usage: 11_extract_transcript.py <YOUTUBE_URL> <OUTPUT_DIR> [SUBTITLE_LANG]
Output: SUCCESS: youtube_{VIDEO_ID}_transcript.vtt or ERROR: No subtitles available
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.transcript_extractor import TranscriptExtractor


def main() -> None:
    """CLI entry point."""
    youtube_url = sys.argv[1] if len(sys.argv) > 1 else None
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".")
    subtitle_lang = sys.argv[3] if len(sys.argv) > 3 else "en"

    if not youtube_url:
        print("ERROR: No YouTube URL provided", file=sys.stderr)
        sys.exit(1)

    try:
        extractor = TranscriptExtractor()
        extractor.extract_transcript(youtube_url, output_dir, subtitle_lang)
    except Exception as e:
        print(f"ERROR: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
