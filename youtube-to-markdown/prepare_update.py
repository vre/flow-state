#!/usr/bin/env python3
"""
Analyzes existing extraction and prepares update recommendations.

Usage: prepare_update.py <YOUTUBE_URL> <OUTPUT_DIR>
Output: JSON with status, metadata changes, issues, and recommendation.

Exit codes:
  0 - Success, JSON output with recommendation
  1 - Error (invalid args, video unavailable, etc.)
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from check_existing import check_existing, extract_metadata_from_file
from extract_data import YouTubeDataExtractor
from intermediate_files import get_key_intermediate_files
from shared_types import (
    extract_video_id,
    FileOperationError,
    RealFileSystem,
    RealCommandRunner,
)


class VideoUnavailableError(Exception):
    """Video is no longer available on YouTube."""

    pass


def parse_count(value: str | None) -> int | None:
    """Parse formatted count string back to integer."""
    if value is None or value == "N/A":
        return None
    value = value.replace(",", "")
    if value.endswith("B"):
        return int(float(value[:-1]) * 1_000_000_000)
    if value.endswith("M"):
        return int(float(value[:-1]) * 1_000_000)
    if value.endswith("K"):
        return int(float(value[:-1]) * 1_000)
    try:
        return int(value)
    except ValueError:
        return None


def compare_counts(old: int | None, new: int | None) -> dict:
    """Compare two count values, return change info."""
    if old is None or new is None:
        return {"old": old, "new": new, "changed": old != new, "significant": False}

    changed = old != new
    # Significant if increase > 50%
    significant = changed and new > old and (new - old) / max(old, 1) > 0.5
    return {"old": old, "new": new, "changed": changed, "significant": significant}


def compare_strings(old: str | None, new: str | None) -> dict:
    """Compare two string values."""
    return {"old": old, "new": new, "changed": old != new}


def fetch_fresh_metadata(video_url: str, output_dir: Path) -> dict:
    """
    Fetch fresh metadata from YouTube.

    Returns:
        Dictionary with video metadata fields

    Raises:
        VideoUnavailableError: If video is not available
        FileOperationError: If extraction fails
    """
    extractor = YouTubeDataExtractor(
        fs=RealFileSystem(), cmd=RealCommandRunner()
    )

    try:
        extractor.check_yt_dlp()
        raw_data = extractor.fetch_video_data(video_url, output_dir)
    except FileOperationError as e:
        # yt-dlp failures usually mean video is unavailable/private/deleted
        # The specific error message is in stderr which we don't capture
        raise VideoUnavailableError(f"Video unavailable or extraction failed: {e}")

    video_id = extract_video_id(video_url)
    metadata = extractor.parse_video_metadata(raw_data, video_id)

    return {
        "title": metadata.title,
        "description": metadata.description,
        "views": metadata.view_count,
        "likes": metadata.like_count,
        "comment_count": metadata.comment_count,
        "chapters": len(metadata.chapters) if metadata.chapters else 0,
        "duration": metadata.duration,
    }


def detect_interrupted_extraction(video_id: str, output_dir: Path, existing: dict) -> bool:
    """
    Detect if extraction was interrupted (intermediate files exist without final).

    Returns True if intermediate files exist but no final output files.
    """
    base_name = f"youtube_{video_id}"
    key_files = get_key_intermediate_files(base_name)

    # Check if any key intermediate files exist
    has_intermediate = any(
        (output_dir / f).exists() for f in key_files
    )

    # Check if final files exist
    has_final = existing.get("summary_file") is not None

    return has_intermediate and not has_final


def detect_issues(existing: dict, changes: dict, interrupted: bool = False) -> list[str]:
    """Detect issues based on existing files and metadata changes."""
    issues = []

    # Interrupted extraction
    if interrupted:
        issues.append("interrupted_extraction: intermediate files exist without final output")

    # v1 format issues
    if existing.get("summary_v1"):
        issues.append("summary_v1: outdated format requires re-summarization")
    if existing.get("comments_v1"):
        issues.append("comments_v1: outdated format lacks type-specific sections")

    # Validity issues
    if existing.get("summary_issues"):
        issues.append(f"summary_invalid: {', '.join(existing['summary_issues'])}")
    if existing.get("transcript_issues"):
        issues.append(f"transcript_invalid: {', '.join(existing['transcript_issues'])}")
    if existing.get("comments_issues"):
        issues.append(f"comments_invalid: {', '.join(existing['comments_issues'])}")

    # Significant metadata changes
    if changes.get("comment_count", {}).get("significant"):
        old = changes["comment_count"]["old"]
        new = changes["comment_count"]["new"]
        pct = int((new - old) / max(old, 1) * 100)
        issues.append(f"comment_count increased significantly (+{pct}%)")

    if changes.get("title", {}).get("changed"):
        issues.append("title changed - video may have been updated")

    if changes.get("chapters", {}).get("changed"):
        old = changes["chapters"]["old"]
        new = changes["chapters"]["new"]
        if old == 0 and new > 0:
            issues.append(f"chapters added ({new} chapters now available)")

    return issues


def generate_recommendation(
    existing: dict, changes: dict, issues: list[str], interrupted: bool = False
) -> dict:
    """Generate update recommendation based on analysis."""
    files_to_backup = []
    summary_path = existing.get("summary_file")
    comment_path = existing.get("comment_file")
    transcript_path = existing.get("transcript_file")

    # Priority 0: Interrupted extraction - clean up and restart
    if interrupted:
        return {
            "action": "full_refresh",
            "reason": "Previous extraction was interrupted, cleanup and restart",
            "suggested_output": "E",
            "files_to_backup": [],  # No final files to backup
        }

    # Priority 1: v1 format upgrades
    if existing.get("summary_v1"):
        if summary_path:
            files_to_backup.append(summary_path)
        if transcript_path:
            files_to_backup.append(transcript_path)
        return {
            "action": "update_summary",
            "reason": "Summary uses v1.0 format, needs upgrade to v2.0",
            "suggested_output": "E" if comment_path else "A",
            "files_to_backup": files_to_backup,
        }

    # Priority 2: Invalid files
    if existing.get("summary_issues"):
        if summary_path:
            files_to_backup.append(summary_path)
        if transcript_path:
            files_to_backup.append(transcript_path)
        return {
            "action": "update_summary",
            "reason": f"Summary has issues: {', '.join(existing['summary_issues'])}",
            "suggested_output": "E" if comment_path else "A",
            "files_to_backup": files_to_backup,
        }

    # Priority 3: Comments v1 or significant comment increase
    comment_needs_update = existing.get("comments_v1") or changes.get(
        "comment_count", {}
    ).get("significant")
    if comment_needs_update and comment_path:
        files_to_backup.append(comment_path)
        reason = (
            "Comments use v1.0 format"
            if existing.get("comments_v1")
            else "Comment count increased significantly"
        )
        return {
            "action": "update_comments",
            "reason": reason,
            "suggested_output": "D",
            "files_to_backup": files_to_backup,
        }

    # Priority 4: Title/content changed
    if changes.get("title", {}).get("changed"):
        if summary_path:
            files_to_backup.append(summary_path)
        if transcript_path:
            files_to_backup.append(transcript_path)
        if comment_path:
            files_to_backup.append(comment_path)
        return {
            "action": "full_refresh",
            "reason": "Video title changed, content may have been updated",
            "suggested_output": "E",
            "files_to_backup": files_to_backup,
        }

    # Priority 5: Metadata only (views/likes changed)
    metadata_changed = any(
        changes.get(field, {}).get("changed")
        for field in ["views", "likes", "comment_count"]
    )
    if metadata_changed and not issues:
        return {
            "action": "metadata_only",
            "reason": "Only engagement metrics changed",
            "suggested_output": None,
            "files_to_backup": [],
        }

    # Priority 6: Extend with missing modules
    has_summary = existing.get("summary_file") is not None
    has_transcript = existing.get("transcript_file") is not None
    has_comments = existing.get("comment_file") is not None

    if has_summary and not has_comments:
        return {
            "action": "extend",
            "reason": "Summary exists, comments can be added",
            "suggested_output": "D",
            "files_to_backup": [],
        }

    if has_summary and not has_transcript:
        return {
            "action": "extend",
            "reason": "Summary exists, transcript can be added",
            "suggested_output": "E",
            "files_to_backup": [],
        }

    # No recommendation needed
    return {
        "action": "none",
        "reason": "All files up to date",
        "suggested_output": None,
        "files_to_backup": [],
    }


def prepare_update(video_url: str, output_dir: Path) -> dict:
    """
    Analyze existing extraction and prepare update recommendation.

    Args:
        video_url: YouTube URL
        output_dir: Directory containing existing files

    Returns:
        Dictionary with analysis results and recommendation
    """
    video_id = extract_video_id(video_url)

    # Get existing file status
    existing = check_existing(video_url, output_dir)

    # Check for interrupted extraction
    interrupted = detect_interrupted_extraction(video_id, output_dir, existing)

    # Fetch fresh metadata
    try:
        fresh = fetch_fresh_metadata(video_url, output_dir)
        video_available = True
    except VideoUnavailableError:
        return {"video_id": video_id, "video_available": False}

    # Get stored metadata
    stored = existing.get("stored_metadata", {})

    # Compare metadata
    changes = {
        "title": compare_strings(stored.get("title"), fresh["title"]),
        "views": compare_counts(parse_count(stored.get("views")), fresh["views"]),
        "likes": compare_counts(parse_count(stored.get("likes")), fresh["likes"]),
        "comment_count": compare_counts(
            parse_count(stored.get("comments")), fresh["comment_count"]
        ),
        "chapters": compare_counts(0, fresh["chapters"]),  # Can't get old chapter count
    }

    # Detect issues
    issues = detect_issues(existing, changes, interrupted)

    # Generate recommendation
    recommendation = generate_recommendation(existing, changes, issues, interrupted)

    # Build existing status for output
    existing_status = {
        "summary": {
            "exists": existing.get("summary_file") is not None,
            "valid": existing.get("summary_valid", False),
            "version": "v1" if existing.get("summary_v1") else "v2",
            "path": existing.get("summary_file"),
        },
        "transcript": {
            "exists": existing.get("transcript_file") is not None,
            "valid": existing.get("transcript_valid", True),
            "path": existing.get("transcript_file"),
        },
        "comments": {
            "exists": existing.get("comment_file") is not None,
            "valid": existing.get("comments_valid", False),
            "version": "v1" if existing.get("comments_v1") else "v2",
            "path": existing.get("comment_file"),
        },
    }

    return {
        "video_id": video_id,
        "video_available": video_available,
        "existing": existing_status,
        "metadata_changes": changes,
        "issues": issues,
        "recommendation": recommendation,
    }


def main() -> None:
    """CLI entry point."""
    if len(sys.argv) != 3:
        print("Usage: prepare_update.py <YOUTUBE_URL> <OUTPUT_DIR>", file=sys.stderr)
        sys.exit(1)

    video_url = sys.argv[1]
    output_dir = Path(sys.argv[2])

    if not output_dir.exists():
        print(
            json.dumps(
                {"video_id": extract_video_id(video_url), "video_available": False}
            )
        )
        sys.exit(1)

    try:
        result = prepare_update(video_url, output_dir)
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
