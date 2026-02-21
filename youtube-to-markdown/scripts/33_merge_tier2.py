#!/usr/bin/env python3
"""Merge Haiku-kept tier-2 comments into prefiltered file.
Usage: 33_merge_tier2.py <candidates.md> <prefiltered.md> <keep_numbers>

keep_numbers: comma-separated list, e.g. "KEEP: 17, 45, 51" or "17, 45, 51"
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.comment_merge import merge_kept_comments, parse_compact, parse_keep_list
from lib.content_safety import wrap_untrusted_content


def main():
    if len(sys.argv) < 4:
        print("Usage: 33_merge_tier2.py <candidates.md> <prefiltered.md> <keep_numbers>")
        sys.exit(2)

    candidates_path = Path(sys.argv[1])
    prefiltered_path = Path(sys.argv[2])
    keep_str = sys.argv[3]

    candidates = parse_compact(candidates_path.read_text())
    prefiltered = prefiltered_path.read_text()
    keep_indices = parse_keep_list(keep_str)

    if not keep_indices:
        # No tier-2 comments kept — wrap existing content and write
        prefiltered_path.write_text(wrap_untrusted_content(prefiltered, "comments"))
        print("Merged: +0 from tier-2 (no comments kept)")
        return

    result = merge_kept_comments(prefiltered, candidates, keep_indices)
    # Wrap merged content in safety delimiters
    prefiltered_path.write_text(wrap_untrusted_content(result, "comments"))

    existing_count = len(re.findall(r"^### \d+\. @", prefiltered, re.MULTILINE))
    total = len(re.findall(r"^### \d+\. @", result, re.MULTILINE))
    added = total - existing_count
    print(f"Merged: +{added} from tier-2 ({total} total)")


if __name__ == "__main__":
    main()
