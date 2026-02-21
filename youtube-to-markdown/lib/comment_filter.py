"""Comment filtering library."""

import re

from lib.content_safety import wrap_untrusted_content

MAX_COMMENTS = 200
TIER_SPLIT_THRESHOLD = 80
LENGTH_THRESHOLD = 400


def parse_comments(content: str) -> list[dict]:
    """Parse comments markdown into list of dicts."""
    pattern = r"### \d+\. @(\S+) \((\d+) likes?\)\n\n(.*?)(?=\n### \d+\.|$)"
    matches = re.findall(pattern, content, re.DOTALL)
    return [{"author": m[0], "likes": int(m[1]), "text": m[2].strip()} for m in matches]


def filter_comments(comments: list[dict], max_comments: int = MAX_COMMENTS) -> list[dict]:
    """Remove junk, keep top N. Comments already sorted by likes from yt-dlp."""
    filtered = [c for c in comments if len(c["text"]) >= 20 or c["likes"] >= 2]
    kept = filtered[:max_comments]
    for i, c in enumerate(kept, 1):
        c["index"] = i
    return kept


def calculate_likes_p75(comments: list[dict]) -> int:
    """Calculate 75th percentile of likes distribution (nearest-rank)."""
    if not comments:
        return 0
    likes = sorted(c["likes"] for c in comments)
    idx = -(-len(likes) * 3 // 4) - 1  # ceil(0.75 * N) - 1
    return likes[max(0, min(idx, len(likes) - 1))]


def split_tiers(
    comments: list[dict],
    likes_threshold: int | None = None,
    length_threshold: int = LENGTH_THRESHOLD,
    skip_threshold: int = TIER_SPLIT_THRESHOLD,
) -> tuple[list[dict], list[dict]]:
    """Split into tier 1 (auto-keep) and tier 2 (needs screening).

    Args:
        comments: Filtered comments with index field.
        likes_threshold: Minimum likes for tier 1. None = use p75.
        length_threshold: Minimum text length (chars) for tier 1.
        skip_threshold: If len(comments) <= this, all go to tier 1.

    Returns:
        (tier1, tier2) comment lists.
    """
    if len(comments) <= skip_threshold:
        return comments, []
    if likes_threshold is None:
        likes_threshold = calculate_likes_p75(comments)
    tier1 = []
    tier2 = []
    for c in comments:
        if c["likes"] >= likes_threshold or len(c["text"]) >= length_threshold:
            tier1.append(c)
        else:
            tier2.append(c)
    return tier1, tier2


def format_compact(comments: list[dict]) -> str:
    """Format comments in compact one-line format for Haiku screening.

    Format: [index|@author|X likes] Full text on single line
    """
    if not comments:
        return ""
    lines = []
    for c in comments:
        text = c["text"].replace("\n", " ").replace("\r", "")
        label = "like" if c["likes"] == 1 else "likes"
        lines.append(f"[{c['index']}|@{c['author']}|{c['likes']} {label}] {text}")
    return "\n".join(lines)


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
        label = "like" if c["likes"] == 1 else "likes"
        lines.append(f"### {i}. @{c['author']} ({c['likes']} {label})\n")
        lines.append(f"{c['text']}\n")
    content = "\n".join(lines)

    if wrap_safe:
        return wrap_untrusted_content(content, "comments")
    return content
