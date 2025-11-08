#!/usr/bin/env python3
"""
Detects video language, lists available subtitles, tries manual subtitles first, falls back to auto-generated
Usage: extract_transcript.py <YOUTUBE_URL> <OUTPUT_DIR> [SUBTITLE_LANG]
Output: SUCCESS: youtube_{VIDEO_ID}_transcript.vtt or ERROR: No subtitles available
"""

import sys
import os
import subprocess
import re
import glob

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
        sys.exit(1)

def get_video_language(youtube_url):
    """Get video language from YouTube"""
    result = subprocess.run(
        ['yt-dlp', '--print', '%(language)s', youtube_url],
        capture_output=True,
        text=True
    )
    video_lang = result.stdout.strip() if result.returncode == 0 else "unknown"
    print(f"Video language: {video_lang}")
    return video_lang

def download_manual_subtitles(youtube_url, subtitle_lang, output_name):
    """Try to download manual subtitles"""
    subprocess.run(
        ['yt-dlp', '--write-sub', '--sub-langs', subtitle_lang, '--skip-download', '--output', output_name, youtube_url],
        capture_output=True
    )
    temp_files = glob.glob(f"{output_name}.*.vtt")
    if temp_files:
        print(f"Manual subtitles downloaded ({subtitle_lang})")
        return temp_files[0]
    return None

def download_auto_subtitles(youtube_url, subtitle_lang, output_name):
    """Try to download auto-generated subtitles"""
    subprocess.run(
        ['yt-dlp', '--write-auto-sub', '--sub-langs', subtitle_lang, '--skip-download', '--output', output_name, youtube_url],
        capture_output=True
    )
    temp_files = glob.glob(f"{output_name}.*.vtt")
    if temp_files:
        print(f"Auto-generated subtitles downloaded ({subtitle_lang})")
        return temp_files[0]
    return None

def download_subtitles(youtube_url, subtitle_lang, output_name):
    """Download subtitles, trying manual first then auto-generated"""
    # Try manual subtitles first
    subtitle_file = download_manual_subtitles(youtube_url, subtitle_lang, output_name)
    if subtitle_file:
        return subtitle_file

    # Fall back to auto-generated
    subtitle_file = download_auto_subtitles(youtube_url, subtitle_lang, output_name)
    if subtitle_file:
        return subtitle_file

    print(f"ERROR: No subtitles available for language: {subtitle_lang}", file=sys.stderr)
    sys.exit(1)

def rename_subtitle_file(temp_file, final_output):
    """Rename temporary subtitle file to final output name"""
    try:
        os.rename(temp_file, final_output)
    except Exception as e:
        print(f"ERROR: Failed to rename transcript file: {e}", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(final_output):
        print(f"ERROR: {final_output} not created", file=sys.stderr)
        sys.exit(1)

    return final_output

def main():
    # Parse arguments
    youtube_url = sys.argv[1] if len(sys.argv) > 1 else None
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "."
    subtitle_lang = sys.argv[3] if len(sys.argv) > 3 else "en"

    # Validate arguments
    if not youtube_url:
        print("ERROR: No YouTube URL provided", file=sys.stderr)
        sys.exit(1)

    # Check required commands
    check_yt_dlp()

    # Extract video ID from URL
    video_id = extract_video_id(youtube_url)
    if not video_id:
        print("ERROR: Could not extract video ID from URL", file=sys.stderr)
        sys.exit(1)

    base_name = f"youtube_{video_id}"

    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Get video language
    get_video_language(youtube_url)

    # Download subtitles
    output_name = os.path.join(output_dir, f"{base_name}_transcript_temp")
    final_output = os.path.join(output_dir, f"{base_name}_transcript.vtt")
    temp_file = download_subtitles(youtube_url, subtitle_lang, output_name)

    # Rename to final filename
    final_file = rename_subtitle_file(temp_file, final_output)

    print(f"SUCCESS: {final_file}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {str(e)}", file=sys.stderr)
        sys.exit(1)
