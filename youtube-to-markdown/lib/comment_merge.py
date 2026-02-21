"""Merge tier-2 kept comments into prefiltered file."""

import re


def parse_compact(content: str) -> list[dict]:
    """Parse compact format back to comment dicts.

    Format: [index|@author|X likes] text
    """
    if not content.strip():
        return []
    results = []
    skipped = 0
    for line in content.strip().split("\n"):
        match = re.match(r"\[(\d+)\|@(\S+)\|(\d+) likes?\] (.*)", line)
        if match:
            results.append(
                {
                    "index": int(match.group(1)),
                    "author": match.group(2),
                    "likes": int(match.group(3)),
                    "text": match.group(4),
                }
            )
        elif line.strip():
            skipped += 1
    if skipped:
        print(f"WARNING: {skipped} malformed line(s) skipped in candidates file")
    return results


def parse_keep_list(keep_str: str) -> list[int]:
    """Parse 'KEEP: 17, 45, 51' into list of ints.

    Tolerant: case-insensitive prefix, ignores trailing text/newlines,
    extracts all integers from first line.
    """
    cleaned = keep_str.strip()
    if not cleaned:
        return []
    # Take only first line (model may add explanation after)
    cleaned = cleaned.split("\n")[0]
    # Remove KEEP: prefix (case-insensitive)
    cleaned = re.sub(r"^KEEP:\s*", "", cleaned, flags=re.IGNORECASE)
    if not cleaned.strip():
        return []
    return [int(n) for n in re.findall(r"\d+", cleaned)]


def merge_kept_comments(
    prefiltered: str,
    candidates: list[dict],
    keep_indices: list[int],
) -> str:
    """Append kept tier-2 comments to prefiltered and renumber.

    Args:
        prefiltered: Existing prefiltered markdown content.
        candidates: Parsed compact-format comments.
        keep_indices: Original indices of comments to keep.

    Returns:
        Merged markdown with sequential numbering.
    """
    if not keep_indices:
        return prefiltered

    by_index = {c["index"]: c for c in candidates}
    seen: set[int] = set()
    kept = []
    for i in keep_indices:
        if i in by_index and i not in seen:
            seen.add(i)
            kept.append(by_index[i])

    if not kept:
        return prefiltered

    # Count existing headers in prefiltered (machine-generated, safe to regex)
    existing_count = len(re.findall(r"^### \d+\. @", prefiltered, re.MULTILINE))

    # Append kept comments with correct sequential numbering (no global renumber)
    lines = [prefiltered.rstrip()]
    for i, c in enumerate(kept, existing_count + 1):
        label = "like" if c["likes"] == 1 else "likes"
        lines.append(f"\n### {i}. @{c['author']} ({c['likes']} {label})\n")
        lines.append(c["text"])

    return "\n".join(lines) + "\n"
