#!/usr/bin/env python3
"""Filter low-value comments from extracted YouTube comments.
Usage: 32_filter_comments.py <comments.md> [output.md] [max_comments]

Removes junk (short AND unpopular), keeps top N by likes (default 200).
Comments already sorted by likes from yt-dlp with comment_sort=top.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.comment_filter import (
    MAX_COMMENTS,
    filter_comments,
    format_comments,
    parse_comments,
)


def main():
    if len(sys.argv) < 2:
        print(f"Usage: 32_filter_comments.py <comments.md> [output.md] [max_comments={MAX_COMMENTS}]")
        print("If output.md omitted, overwrites input file.")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else input_path
    max_comments = int(sys.argv[3]) if len(sys.argv) > 3 else MAX_COMMENTS

    content = input_path.read_text()
    comments = parse_comments(content)
    filtered = filter_comments(comments, max_comments)

    output_path.write_text(format_comments(filtered))
    print(f"Filtered: {len(comments)} → {len(filtered)} comments (max {max_comments})")


if __name__ == "__main__":
    main()
