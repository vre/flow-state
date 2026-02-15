#!/usr/bin/env python3
"""Lists YouTube channel videos and matches against local extractions.

Usage: 22_list_channel.py <CHANNEL_URL> <OUTPUT_DIR> [--offset N] [--limit N]
Output: JSON with channel metadata, new/existing videos, pagination info.
Video entries include both `views` (formatted) and `view_count` (raw int).

Rate limiting: uses --sleep-requests 0.5 for flat-playlist listing.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.channel_listing import (
    find_output_dir,
    list_channel_videos,
    match_existing_videos,
    parse_channel_entry,
    parse_channel_metadata,
    suggest_output_dir,
)


def main() -> None:
    """CLI entry point."""
    offset = 0
    limit = 50
    positional = []
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == "--offset" and i + 1 < len(sys.argv):
            offset = int(sys.argv[i + 1])
            i += 2
        elif sys.argv[i] == "--limit" and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])
            i += 2
        else:
            positional.append(sys.argv[i])
            i += 1
    args = positional

    if len(args) != 2:
        print(
            "Usage: 22_list_channel.py <CHANNEL_URL> <OUTPUT_DIR> [--offset N] [--limit N]",
            file=sys.stderr,
        )
        sys.exit(1)

    channel_url = args[0]
    output_dir = Path(args[1])
    offset = max(0, offset)
    limit = max(1, limit)

    # Fetch channel video list
    try:
        raw_entries = list_channel_videos(channel_url, offset=offset, limit=limit)
    except RuntimeError as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)
    if not raw_entries:
        print(json.dumps({"error": "No videos found or invalid channel URL"}))
        sys.exit(1)

    # Parse channel metadata from first entry
    channel_meta = parse_channel_metadata(raw_entries[0])

    # Parse video entries (includes both formatted views and raw view_count).
    videos = [parse_channel_entry(e) for e in raw_entries]

    # Resolve output directory
    effective_dir = output_dir
    if output_dir.exists() and channel_meta["id"]:
        found_dir = find_output_dir(output_dir, channel_meta["id"])
        if found_dir:
            effective_dir = found_dir

    # Match against existing files
    if effective_dir.exists():
        new_videos, existing_videos = match_existing_videos(videos, effective_dir)
    else:
        new_videos, existing_videos = videos, []

    # Build suggestion if no existing videos found anywhere
    suggestion = None
    if not existing_videos and channel_meta["name"] and channel_meta["id"]:
        suggestion = str(suggest_output_dir(output_dir, channel_meta["name"], channel_meta["id"]))

    # has_more: if we got exactly limit entries, there's likely more
    has_more = len(videos) == limit
    result = {
        "channel": channel_meta,
        "page": {
            "offset": offset,
            "count": len(videos),
            "has_more": has_more,
        },
        "new_videos": new_videos,
        "existing_videos": existing_videos,
    }
    if suggestion:
        result["output_dir_suggestion"] = suggestion

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
