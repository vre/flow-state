#!/usr/bin/env python3
"""
Creates final markdown file from template and component files, cleans up intermediate work files
Usage: finalize.py [--debug] <BASE_NAME> <OUTPUT_DIR>
Keeps: {BASE_NAME}.md
Removes: all intermediate files including _metadata.md, _summary.md, _description.md, _transcript.md (unless --debug)
"""

import sys
import os
import re

def clean_title_for_filename(title, max_length=60):
    """Clean title for use in filename"""
    # Remove or replace problematic characters
    cleaned = re.sub(r'[<>:"/\\|?*]', '', title)  # Remove invalid filename chars
    cleaned = re.sub(r'\s+', ' ', cleaned)  # Normalize whitespace
    cleaned = cleaned.strip()

    # Truncate if too long
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length].rsplit(' ', 1)[0]  # Cut at word boundary

    return cleaned

def read_file_or_empty(file_path):
    """Read file content or return empty string if file doesn't exist"""
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    return ""

def main():
    # Parse options
    debug = False
    args = []
    for arg in sys.argv[1:]:
        if arg == '--debug':
            debug = True
        else:
            args.append(arg)

    # Parse arguments
    if len(args) < 1:
        print("ERROR: No BASE_NAME provided", file=sys.stderr)
        print("Usage: finalize.py [--debug] <BASE_NAME> <OUTPUT_DIR>", file=sys.stderr)
        sys.exit(1)

    base_name = args[0]
    output_dir = args[1] if len(args) > 1 else "."

    # Get script directory for template
    script_dir = os.path.dirname(os.path.abspath(__file__))
    template_file = os.path.join(script_dir, "template.md")

    # Validate template exists
    if not os.path.exists(template_file):
        print(f"ERROR: {template_file} not found", file=sys.stderr)
        sys.exit(1)

    # Read template
    with open(template_file, 'r', encoding='utf-8') as f:
        template = f.read()

    # Read component files
    metadata = read_file_or_empty(os.path.join(output_dir, f"{base_name}_metadata.md"))
    summary = read_file_or_empty(os.path.join(output_dir, f"{base_name}_summary.md"))
    description = read_file_or_empty(os.path.join(output_dir, f"{base_name}_description.md"))
    transcription = read_file_or_empty(os.path.join(output_dir, f"{base_name}_transcript.md"))

    # Replace placeholders
    final_content = template.replace("{metadata}", metadata.strip())
    final_content = final_content.replace("{summary}", summary.strip())
    final_content = final_content.replace("{description}", description.strip())
    final_content = final_content.replace("{transcription}", transcription.strip())

    # Read title and create human-readable filename
    title = read_file_or_empty(os.path.join(output_dir, f"{base_name}_title.txt")).strip()
    if title:
        cleaned_title = clean_title_for_filename(title)
        video_id = base_name.replace('youtube_', '')
        final_filename = f"youtube - {cleaned_title} ({video_id}).md"
    else:
        # Fallback to old format if title not found
        final_filename = f"{base_name}.md"

    # Write final file
    final_file = os.path.join(output_dir, final_filename)
    with open(final_file, 'w', encoding='utf-8') as f:
        f.write(final_content)

    print(f"Created final file: {final_filename}")

    # Clean up intermediate work files unless --debug is set
    if debug:
        print("Debug mode: keeping intermediate work files")
    else:
        work_files = [
            f"{base_name}_title.txt",
            f"{base_name}_metadata.md",
            f"{base_name}_summary.md",
            f"{base_name}_description.md",
            f"{base_name}_chapters.json",
            f"{base_name}_transcript.vtt",
            f"{base_name}_transcript_dedup.md",
            f"{base_name}_transcript_no_timestamps.txt",
            f"{base_name}_transcript_paragraphs.md",
            f"{base_name}_transcript_cleaned.md",
            f"{base_name}_transcript.md"
        ]

        for work_file in work_files:
            file_path = os.path.join(output_dir, work_file)
            if os.path.exists(file_path):
                os.remove(file_path)

        print("Cleaned up intermediate work files")

    print(f"Final file: {final_filename}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {str(e)}", file=sys.stderr)
        sys.exit(1)
