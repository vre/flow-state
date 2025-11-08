#!/usr/bin/env python3
"""
Extracts YouTube video comments
Usage: extract_comments.py <YOUTUBE_URL> <OUTPUT_DIR>
Output: Creates youtube_{VIDEO_ID}_name.txt, youtube_{VIDEO_ID}_comments.md
"""

import json
import sys
import os
import subprocess
import re

def extract_video_id(url):
    """Extract video ID from YouTube URL"""
    # Handle youtu.be format
    if 'youtu.be/' in url:
        video_id = url.split('youtu.be/')[-1].split('?')[0]
        return video_id

    # Handle youtube.com format with v= parameter
    match = re.search(r'[?&]v=([^&]+)', url)
    if match:
        return match.group(1)

    return None

def check_yt_dlp():
    """Check if yt-dlp is installed"""
    try:
        subprocess.run(['yt-dlp', '--version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("ERROR: yt-dlp is not installed", file=sys.stderr)
        print("Install options:", file=sys.stderr)
        print("  - macOS: brew install yt-dlp", file=sys.stderr)
        print("  - Ubuntu/Debian: sudo apt update && sudo apt install -y yt-dlp", file=sys.stderr)
        print("  - All systems: pip3 install yt-dlp", file=sys.stderr)
        sys.exit(1)

def fetch_video_data(video_url, output_dir):
    """Fetch video title and comments from YouTube"""
    temp_json = os.path.join(output_dir, "video_data.json")
    try:
        with open(temp_json, 'w') as f:
            result = subprocess.run(
                ['yt-dlp', '--dump-single-json', '--write-comments', '--skip-download', video_url],
                stdout=f,
                stderr=subprocess.PIPE,
                text=True
            )
            if result.returncode != 0:
                print("ERROR: Failed to extract video data", file=sys.stderr)
                if os.path.exists(temp_json):
                    os.remove(temp_json)
                sys.exit(1)
    except Exception as e:
        print(f"ERROR: Failed to extract video data: {e}", file=sys.stderr)
        if os.path.exists(temp_json):
            os.remove(temp_json)
        sys.exit(1)

    try:
        with open(temp_json, 'r') as f:
            data = json.load(f)
    except Exception as e:
        print(f"ERROR: Failed to read JSON: {e}", file=sys.stderr)
        if os.path.exists(temp_json):
            os.remove(temp_json)
        sys.exit(1)
    finally:
        if os.path.exists(temp_json):
            os.remove(temp_json)

    return data

def create_comments_file(data, base_name, output_dir):
    """
    Create hierarchical comments using heading levels 3-5, flatten deeper levels.

    yt-dlp returns flat list with 'parent' field. We reconstruct hierarchy:
    - Level 0: ### (foldable in Obsidian)
    - Level 1: ####
    - Level 2: #####
    - Level 3+: Bullet lists (flattened to prevent excessive nesting)
    """
    comments = data.get('comments', [])
    comment_file = os.path.join(output_dir, f"{base_name}_comments.md")

    if not comments:
        # Create empty file
        with open(comment_file, 'w', encoding='utf-8') as cf:
            cf.write("No comments available\n")
        print(f"COMMENTS: {comment_file} (no comments)")
        return comment_file

    # Build hierarchy from flat structure (parent='root' = top-level, else reply)
    comment_by_id = {}
    replies_by_parent = {}

    for comment in comments:
        cid = comment.get('id', '')
        parent = comment.get('parent', 'root')
        comment_by_id[cid] = comment

        if parent not in replies_by_parent:
            replies_by_parent[parent] = []
        replies_by_parent[parent].append(comment)

    def write_comment(cf, comment, depth=0):
        """Recursively write comment and its replies with appropriate heading levels"""
        author = comment.get('author', 'Unknown')
        text = comment.get('text', '')
        likes = comment.get('like_count', 0)
        cid = comment.get('id', '')

        # Use headings for depth 0-2 (### #### #####), flatten beyond that
        if depth == 0:
            # Top-level: ###
            cf.write(f"### {author} ({likes} likes)\n\n")
        elif depth == 1:
            # First reply level: ####
            cf.write(f"#### {author} ({likes} likes)\n\n")
        elif depth == 2:
            # Second reply level: #####
            cf.write(f"##### {author} ({likes} likes)\n\n")
        else:
            # Deeper levels: flatten as bullet list
            cf.write(f"- **{author} ({likes} likes)**: {text}\n\n")
            # Don't recurse further, flatten all deeper replies here
            replies = replies_by_parent.get(cid, [])
            for reply in replies:
                r_author = reply.get('author', 'Unknown')
                r_text = reply.get('text', '')
                r_likes = reply.get('like_count', 0)
                cf.write(f"  - **{r_author} ({r_likes} likes)**: {r_text}\n")
            if replies:
                cf.write("\n")
            return

        # Write comment text for heading levels
        cf.write(f"{text}\n\n")

        # Recursively write replies for depth 0-2
        replies = replies_by_parent.get(cid, [])
        for reply in replies:
            write_comment(cf, reply, depth + 1)

    # Write all top-level comments
    with open(comment_file, 'w', encoding='utf-8') as cf:
        top_level = replies_by_parent.get('root', [])[:50]
        for idx, comment in enumerate(top_level, 1):
            # Add numbering only to top-level
            author = comment.get('author', 'Unknown')
            text = comment.get('text', '')
            likes = comment.get('like_count', 0)
            cid = comment.get('id', '')

            cf.write(f"### {idx}. {author} ({likes} likes)\n\n")
            cf.write(f"{text}\n\n")

            # Write replies recursively
            replies = replies_by_parent.get(cid, [])
            for reply in replies:
                write_comment(cf, reply, depth=1)

    total_replies = len(comments) - len(replies_by_parent.get('root', []))
    print(f"COMMENTS: {comment_file} ({len(replies_by_parent.get('root', []))} comments, {total_replies} replies)")
    return comment_file

def main():
    # Parse arguments
    if len(sys.argv) != 3:
        print("Usage: extract_comments.py <YOUTUBE_URL> <OUTPUT_DIR>", file=sys.stderr)
        sys.exit(1)

    video_url = sys.argv[1]
    output_dir = sys.argv[2]

    # Validate arguments
    if not video_url:
        print("ERROR: No YouTube URL provided", file=sys.stderr)
        sys.exit(1)

    # Check required commands
    check_yt_dlp()

    # Extract video ID from URL
    video_id = extract_video_id(video_url)
    if not video_id:
        print("ERROR: Could not extract video ID from URL", file=sys.stderr)
        sys.exit(1)

    base_name = f"youtube_{video_id}"

    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Fetch video data from YouTube
    data = fetch_video_data(video_url, output_dir)

    # Extract and save video title
    title = data.get('title', 'Untitled')
    name_file = os.path.join(output_dir, f"{base_name}_name.txt")
    with open(name_file, 'w', encoding='utf-8') as f:
        f.write(title)
    print(f"SUCCESS: {name_file}")

    # Create comments file
    create_comments_file(data, base_name, output_dir)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {str(e)}", file=sys.stderr)
        sys.exit(1)
