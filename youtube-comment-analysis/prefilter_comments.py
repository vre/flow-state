#!/usr/bin/env python3
"""Filter low-value comments from extracted YouTube comments.

Usage: python3 prefilter_comments.py <comments.md> [output.md] [max_comments]

Removes junk (short AND unpopular), keeps top N by likes (default 200).
Comments already sorted by likes from yt-dlp with comment_sort=top.
"""

import re
import sys
from pathlib import Path

MAX_COMMENTS = 200


def parse_comments(content: str) -> list[dict]:
    """Parse comments markdown into list of dicts."""
    pattern = r'### \d+\. @(\S+) \((\d+) likes?\)\n\n(.*?)(?=\n### \d+\.|$)'
    matches = re.findall(pattern, content, re.DOTALL)
    return [
        {'author': m[0], 'likes': int(m[1]), 'text': m[2].strip()}
        for m in matches
    ]


def filter_comments(comments: list[dict], max_comments: int = MAX_COMMENTS) -> list[dict]:
    """Remove junk, keep top N. Comments already sorted by likes from yt-dlp."""
    # Remove short AND unpopular (junk)
    filtered = [c for c in comments if len(c['text']) >= 20 or c['likes'] >= 2]
    # Take top N (already sorted by likes)
    return filtered[:max_comments]


def format_comments(comments: list[dict]) -> str:
    """Format filtered comments back to markdown."""
    lines = []
    for i, c in enumerate(comments, 1):
        lines.append(f"### {i}. @{c['author']} ({c['likes']} likes)\n")
        lines.append(f"{c['text']}\n")
    return '\n'.join(lines)


def main():
    if len(sys.argv) < 2:
        print(f"Usage: python3 prefilter_comments.py <comments.md> [output.md] [max_comments={MAX_COMMENTS}]")
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


if __name__ == '__main__':
    main()
