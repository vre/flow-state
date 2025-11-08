#!/usr/bin/env python3
# Apply paragraph breaks to deduplicated transcript
# Usage: python3 apply_paragraph_breaks.py <INPUT_MD> <OUTPUT_MD> <BREAKS>
# BREAKS format: "15,42,78,103" (comma-separated line numbers)

import os
import sys

if len(sys.argv) != 4:
    print("Usage: python3 apply_paragraph_breaks.py <INPUT_MD> <OUTPUT_MD> <BREAKS>", file=sys.stderr)
    sys.exit(1)

INPUT_FILE = sys.argv[1]
OUTPUT_FILE = sys.argv[2]
BREAK_POINTS_STR = sys.argv[3]

try:
    # Parse break points
    break_points = [int(x.strip()) for x in BREAK_POINTS_STR.split(',')]
    break_points_set = set(break_points)

    # Read input file with timestamps
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        lines = [line.rstrip('\n') for line in f.readlines()]

    # Parse timestamps
    timestamps = []
    texts = []
    for line in lines:
        if line.startswith('[') and len(line) > 15:
            timestamp = line[:14]  # [00:00:00.080] is 14 chars
            text = line[15:]  # Text starts at position 15
            timestamps.append(timestamp)
            texts.append(text)
        else:
            timestamps.append(None)
            texts.append(line)

    # Build paragraphs based on break points
    paragraphs = []
    current_paragraph = []
    paragraph_start_timestamp = None

    for i, text in enumerate(texts, start=1):
        # Track first timestamp in paragraph
        if timestamps[i-1] and not paragraph_start_timestamp:
            paragraph_start_timestamp = timestamps[i-1]

        # Add text
        if text:
            current_paragraph.append(text)

        # Check if this is a break point
        if i in break_points_set or i == len(texts):
            # Finish current paragraph
            if current_paragraph and paragraph_start_timestamp:
                paragraph_text = ' '.join(current_paragraph)
                paragraphs.append(f"{paragraph_text} {paragraph_start_timestamp}")
                current_paragraph = []
                paragraph_start_timestamp = None

    # Validate output
    if not paragraphs:
        print(f"ERROR: No paragraphs created from {INPUT_FILE}", file=sys.stderr)
        sys.exit(1)

    # Write to output file
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        for para in paragraphs:
            f.write(para + '\n\n')

    print(f"SUCCESS: Created {len(paragraphs)} paragraphs -> {OUTPUT_FILE}")

except FileNotFoundError:
    print(f"ERROR: {INPUT_FILE} not found", file=sys.stderr)
    sys.exit(1)
except ValueError as e:
    print(f"ERROR: Invalid break points format: {e}", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"ERROR: {str(e)}", file=sys.stderr)
    sys.exit(1)
