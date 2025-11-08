#!/usr/bin/env python3
# Deduplicate VTT (removes duplicate lines from auto-generated captions)
# Usage: python3 deduplicate_vtt.py <INPUT_VTT> <OUTPUT_MD>
# Output format: [00:00:01.000] Text here

import os
import re
import sys

if len(sys.argv) != 3:
    print("Usage: python3 deduplicate_vtt.py <INPUT_VTT> <OUTPUT_MD>", file=sys.stderr)
    sys.exit(1)

VTT_FILE = sys.argv[1]
OUTPUT_FILE = sys.argv[2]

seen = set()
current_timestamp = None
output_lines = []

try:
    with open(VTT_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()

            # Skip headers
            if line.startswith('WEBVTT') or line.startswith('Kind:') or line.startswith('Language:'):
                continue

            # Capture timestamp (start time only)
            if '-->' in line:
                current_timestamp = line.split('-->')[0].strip()
                continue

            # Process text with deduplication
            if line and current_timestamp:
                clean = re.sub('<[^>]*>', '', line)
                clean = clean.replace('&amp;', '&').replace('&gt;', '>').replace('&lt;', '<')

                if clean and clean not in seen:
                    output_lines.append(f'[{current_timestamp}] {clean}')
                    seen.add(clean)

    # Validate output
    if not output_lines:
        print(f"ERROR: No text extracted from {VTT_FILE}", file=sys.stderr)
        sys.exit(1)

    # Write to output file
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(output_lines))

    # Verify file was created
    if not os.path.exists(OUTPUT_FILE):
        print(f"ERROR: Failed to create {OUTPUT_FILE}", file=sys.stderr)
        sys.exit(1)

    print(f"SUCCESS: {OUTPUT_FILE} ({len(output_lines)} lines)")

except FileNotFoundError:
    print(f"ERROR: {VTT_FILE} not found", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"ERROR: {str(e)}", file=sys.stderr)
    sys.exit(1)
