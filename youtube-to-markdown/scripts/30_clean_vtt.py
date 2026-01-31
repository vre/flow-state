#!/usr/bin/env python3
"""Deduplicate VTT (removes duplicate lines from auto-generated captions).
Usage: 30_clean_vtt.py <INPUT_VTT> <OUTPUT_MD> [NO_TIMESTAMPS_MD]
Output format: [00:00:01.000] Text here
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.vtt_deduplicator import VTTDeduplicator


def main() -> None:
    """CLI entry point."""
    if len(sys.argv) < 3 or len(sys.argv) > 4:
        print(
            "Usage: 30_clean_vtt.py <INPUT_VTT> <OUTPUT_MD> [NO_TIMESTAMPS_MD]",
            file=sys.stderr,
        )
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    no_timestamps_path = Path(sys.argv[3]) if len(sys.argv) == 4 else None

    try:
        deduplicator = VTTDeduplicator()
        deduplicator.deduplicate_vtt(input_path, output_path, no_timestamps_path)
    except Exception as e:
        print(f"ERROR: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
