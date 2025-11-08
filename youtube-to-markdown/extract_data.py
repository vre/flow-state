#!/usr/bin/env python3
"""
Extracts YouTube video data: metadata, description, and chapters
Usage: extract_data.py <YOUTUBE_URL> <OUTPUT_DIR>
Output: Creates youtube_{VIDEO_ID}_metadata.md, youtube_{VIDEO_ID}_description.md, youtube_{VIDEO_ID}_chapters.json
"""

import json
import sys
import os
import subprocess
import re
from datetime import datetime

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
    """Fetch video metadata from YouTube"""
    temp_json = os.path.join(output_dir, "video_data.json")
    try:
        with open(temp_json, 'w') as f:
            result = subprocess.run(
                ['yt-dlp', '--dump-single-json', '--skip-download', video_url],
                stdout=f,
                stderr=subprocess.PIPE,
                text=True
            )
            if result.returncode != 0:
                print("ERROR: Failed to extract video metadata", file=sys.stderr)
                if os.path.exists(temp_json):
                    os.remove(temp_json)
                sys.exit(1)
    except Exception as e:
        print(f"ERROR: Failed to extract video metadata: {e}", file=sys.stderr)
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

def format_upload_date(upload_date):
    """Format upload date from YYYYMMDD to YYYY-MM-DD"""
    if upload_date != 'Unknown' and len(str(upload_date)) == 8:
        return f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"
    return upload_date

def format_subscribers(subscribers):
    """Format subscriber count"""
    if isinstance(subscribers, int):
        return f"{subscribers:,} subscribers"
    return f"{subscribers} subscribers"

def format_duration(duration):
    """Format duration from seconds to HH:MM:SS or MM:SS"""
    if duration:
        hours = duration // 3600
        minutes = (duration % 3600) // 60
        seconds = duration % 60
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"
    return "Unknown"

def create_metadata_file(data, base_name, output_dir):
    """Create metadata file with video origin info"""
    filename = os.path.join(output_dir, f"{base_name}_metadata.md")
    title = data.get('title', 'Untitled')

    # Save title to separate file for finalize.py to use in filename
    title_file = os.path.join(output_dir, f"{base_name}_title.txt")
    with open(title_file, 'w', encoding='utf-8') as tf:
        tf.write(title)
    link = data.get('webpage_url', 'N/A')
    channel = data.get('uploader', 'Unknown')
    channel_url = data.get('channel_url', data.get('uploader_url', ''))
    subscribers = data.get('channel_follower_count', 'N/A')
    upload_date = data.get('upload_date', 'Unknown')
    view_count = data.get('view_count', 0)
    like_count = data.get('like_count', 0)
    duration = data.get('duration', 0)

    upload_date = format_upload_date(upload_date)
    extraction_date = datetime.now().strftime('%Y-%m-%d')
    sub_text = format_subscribers(subscribers)
    duration_text = format_duration(duration)
    views_text = f"{view_count:,}" if view_count else "0"
    likes_text = f"{like_count:,}" if like_count else "0"

    with open(filename, 'w', encoding='utf-8') as md:
        md.write(f"- **Title:** [{title}]({link})\n")
        if channel_url:
            md.write(f"- **Channel:** [{channel}]({channel_url}) ({sub_text})\n")
        else:
            md.write(f"- **Channel:** {channel} ({sub_text})\n")
        md.write(f"- **Views:** {views_text} | Likes: {likes_text} | Duration: {duration_text}\n")
        md.write(f"- **Published:** {upload_date} | Extracted: {extraction_date}\n")

    print(f"SUCCESS: {filename}")
    return filename

def create_description_file(data, base_name, output_dir):
    """Create description file"""
    filename = os.path.join(output_dir, f"{base_name}_description.md")
    description = data.get('description', 'No description')

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(description)

    print(f"SUCCESS: {filename}")
    return filename

def create_chapters_file(data, base_name, output_dir):
    """Create chapters JSON file"""
    chapters = data.get('chapters', [])
    chapters_file = os.path.join(output_dir, f"{base_name}_chapters.json")

    with open(chapters_file, 'w', encoding='utf-8') as cf:
        json.dump(chapters if chapters else [], cf, indent=2)

    if chapters:
        print(f"CHAPTERS: {chapters_file}")
    else:
        print(f"CHAPTERS: {chapters_file} (no chapters in video)")

    return chapters_file

def main():
    # Parse arguments
    if len(sys.argv) != 3:
        print("Usage: extract_data.py <YOUTUBE_URL> <OUTPUT_DIR>", file=sys.stderr)
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

    # Create output files
    create_metadata_file(data, base_name, output_dir)
    create_description_file(data, base_name, output_dir)
    create_chapters_file(data, base_name, output_dir)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {str(e)}", file=sys.stderr)
        sys.exit(1)
