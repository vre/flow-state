#!/usr/bin/env python3
"""Apply paragraph breaks to deduplicated transcript.
Usage: 31_format_transcript.py <INPUT_MD> <BREAKS_FILE> <OUTPUT_MD>
BREAKS_FILE: file containing comma-separated line numbers (e.g., "15,42,78,103")
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.paragraph_breaker import ParagraphBreaker, extract_video_id_from_path


def main() -> None:
    """CLI entry point."""
    if len(sys.argv) != 4:
        print("Usage: 31_format_transcript.py <INPUT_MD> <BREAKS_FILE> <OUTPUT_MD>", file=sys.stderr)
        sys.exit(1)

    input_path = Path(sys.argv[1])
    breaks_file = Path(sys.argv[2])
    output_path = Path(sys.argv[3])

    if not breaks_file.exists():
        print(f"ERROR: Breaks file not found: {breaks_file}", file=sys.stderr)
        sys.exit(1)
    break_points_str = breaks_file.read_text().strip()

    video_id = extract_video_id_from_path(input_path)

    try:
        breaker = ParagraphBreaker(video_id=video_id)
        break_points = breaker.parse_break_points(break_points_str)
        breaker.apply_breaks(input_path, output_path, break_points)
    except Exception as e:
        print(f"ERROR: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
