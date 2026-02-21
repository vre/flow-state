#!/usr/bin/env python3
"""Filter low-value comments from extracted YouTube comments.
Usage: 32_filter_comments.py <comments.md> <output.md> <candidates.md> [max_comments]

Removes junk (short AND unpopular), keeps top N by likes (default 200).
If >80 comments after filtering, splits into tier 1 (prefiltered) and tier 2 (candidates).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.comment_filter import (
    MAX_COMMENTS,
    filter_comments,
    format_comments,
    format_compact,
    parse_comments,
    split_tiers,
)

TOKEN_WARNING_CHARS = 100_000  # ~25K tokens


def main():
    if len(sys.argv) < 4:
        print(f"Usage: 32_filter_comments.py <comments.md> <output.md> <candidates.md> [max_comments={MAX_COMMENTS}]")
        sys.exit(2)

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    candidates_path = Path(sys.argv[3])
    max_comments = int(sys.argv[4]) if len(sys.argv) > 4 else MAX_COMMENTS

    content = input_path.read_text()
    comments = parse_comments(content)
    filtered = filter_comments(comments, max_comments)

    tier1, tier2 = split_tiers(filtered)

    if not tier2:
        tier1_content = format_comments(tier1, wrap_safe=True)
        output_path.write_text(tier1_content)
        if candidates_path.exists():
            candidates_path.unlink()
        print(f"Filtered: {len(comments)} → {len(filtered)} comments (single tier)")
        if len(tier1_content) > TOKEN_WARNING_CHARS:
            print(f"WARNING: Output exceeds {TOKEN_WARNING_CHARS // 4 // 1000}K tokens")
        return

    # Write tier 1 without safety wrapper — merge script wraps after append
    tier1_content = format_comments(tier1, wrap_safe=False)
    output_path.write_text(tier1_content)
    tier1_tokens = len(tier1_content) // 4

    # Write tier 2 compact
    tier2_content = format_compact(tier2)
    candidates_path.write_text(tier2_content)
    tier2_tokens = len(tier2_content) // 4

    print(
        f"Filtered: {len(comments)} → {len(filtered)} comments\n"
        f"Split: {len(tier1)} tier-1 (~{tier1_tokens // 1000}K tok)"
        f" + {len(tier2)} tier-2 (~{tier2_tokens // 1000}K tok)"
    )

    if len(tier1_content) > TOKEN_WARNING_CHARS:
        print(f"WARNING: Tier 1 exceeds {TOKEN_WARNING_CHARS // 4 // 1000}K tokens")
    if len(tier2_content) > TOKEN_WARNING_CHARS:
        print(f"WARNING: Tier 2 exceeds {TOKEN_WARNING_CHARS // 4 // 1000}K tokens")


if __name__ == "__main__":
    main()
