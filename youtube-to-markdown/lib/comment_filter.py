"""Comment filtering library."""

import re

from lib.content_safety import wrap_untrusted_content

MAX_COMMENTS = 200


def parse_comments(content: str) -> list[dict]:
    """Parse comments markdown into list of dicts."""
    pattern = r"### \d+\. @(\S+) \((\d+) likes?\)\n\n(.*?)(?=\n### \d+\.|$)"
    matches = re.findall(pattern, content, re.DOTALL)
    return [{"author": m[0], "likes": int(m[1]), "text": m[2].strip()} for m in matches]


def filter_comments(comments: list[dict], max_comments: int = MAX_COMMENTS) -> list[dict]:
    """Remove junk, keep top N. Comments already sorted by likes from yt-dlp."""
    filtered = [c for c in comments if len(c["text"]) >= 20 or c["likes"] >= 2]
    return filtered[:max_comments]


def format_comments(comments: list[dict], wrap_safe: bool = True) -> str:
    """Format filtered comments back to markdown.

    Args:
        comments: List of comment dicts with author, likes, text
        wrap_safe: If True, wrap output in safety delimiters (default True)

    Returns:
        Formatted markdown string, optionally wrapped in safety delimiters
    """
    lines = []
    for i, c in enumerate(comments, 1):
        lines.append(f"### {i}. @{c['author']} ({c['likes']} likes)\n")
        lines.append(f"{c['text']}\n")
    content = "\n".join(lines)

    if wrap_safe:
        return wrap_untrusted_content(content, "comments")
    return content
