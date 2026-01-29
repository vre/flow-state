"""
Update preparation library.
"""

from pathlib import Path

from lib.check_existing import check_existing, extract_metadata_from_file
from lib.intermediate_files import get_key_intermediate_files
from lib.shared_types import (
    extract_video_id,
    FileOperationError,
    RealFileSystem,
    RealCommandRunner,
)
from lib.youtube_extractor import YouTubeDataExtractor


class VideoUnavailableError(Exception):
    """Video is no longer available on YouTube."""
    pass


def parse_count(value: str | None) -> int | None:
    """Parse formatted count string back to integer."""
    if value is None or value == "N/A":
        return None
    value = value.replace(",", "")
    try:
        if value.endswith("B"):
            return int(float(value[:-1]) * 1_000_000_000)
        if value.endswith("M"):
            return int(float(value[:-1]) * 1_000_000)
        if value.endswith("K"):
            return int(float(value[:-1]) * 1_000)
        return int(value)
    except (ValueError, TypeError):
        return None


def format_count_compact(value: int | None) -> str:
    """Format count to compact form (1.2M, 500K, etc.)."""
    if value is None:
        return "N/A"
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.1f}B"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return str(value)


def compare_counts(old: int | None, new: int | None) -> dict:
    """
    Compare two count values.

    Returns dict with:
    - changed: bool - whether the value changed
    - significant: bool - whether the change is significant (>50% increase)
    """
    if old is None and new is None:
        return {"changed": False, "significant": False}
    if old is None or new is None:
        return {"changed": True, "significant": False}

    changed = old != new
    # Significant = >50% increase (decreases are not significant)
    significant = changed and new > old and ((new - old) / old > 0.5) if old > 0 else False

    return {"changed": changed, "significant": significant}


def compare_strings(old: str | None, new: str | None) -> dict:
    """Compare two string values."""
    return {"changed": old != new}


def detect_issues(existing: dict, changes: dict) -> list[str]:
    """
    Detect issues based on existing file state and changes.

    Returns list of issue descriptions.
    """
    issues = []

    # Check format versions
    if existing.get("summary_v1"):
        issues.append("summary_v1: outdated format")
    if existing.get("comments_v1"):
        issues.append("comments_v1: outdated format")

    # Check for significant comment increase
    comment_change = changes.get("comment_count", {})
    if comment_change.get("changed") and comment_change.get("significant"):
        issues.append("comment_count increased significantly")

    # Check for title change
    title_change = changes.get("title", {})
    if title_change.get("changed"):
        issues.append("title changed")

    # Check summary issues
    if existing.get("summary_issues"):
        issues.append("summary_invalid: " + ", ".join(existing["summary_issues"]))

    return issues


def generate_recommendation(existing: dict, changes: dict, issues: list[str]) -> dict:
    """
    Generate update recommendation based on analysis.

    Returns dict with action and details.
    """
    files_to_backup = []

    # Title change triggers full refresh
    if any("title changed" in issue for issue in issues):
        if existing.get("summary_file"):
            files_to_backup.append(existing["summary_file"])
        if existing.get("comment_file"):
            files_to_backup.append(existing["comment_file"])
        if existing.get("transcript_file"):
            files_to_backup.append(existing["transcript_file"])
        return {
            "action": "full_refresh",
            "reason": "Title changed",
            "files_to_backup": files_to_backup,
        }

    # Summary v1 upgrade
    if any("summary_v1" in issue for issue in issues):
        if existing.get("summary_file"):
            files_to_backup.append(existing["summary_file"])
        return {
            "action": "update_summary",
            "reason": "Summary uses outdated v1 format",
            "files_to_backup": files_to_backup,
        }

    # Comments v1 upgrade
    if any("comments_v1" in issue for issue in issues):
        if existing.get("comment_file"):
            files_to_backup.append(existing["comment_file"])
        return {
            "action": "update_comments",
            "reason": "Comments use outdated v1 format",
            "files_to_backup": files_to_backup,
        }

    # Significant comment increase
    if any("comment_count increased" in issue for issue in issues):
        if existing.get("comment_file"):
            files_to_backup.append(existing["comment_file"])
        return {
            "action": "update_comments",
            "reason": "Significant new comments",
            "files_to_backup": files_to_backup,
        }

    # Extend with comments if missing
    if existing.get("summary_file") and not existing.get("comment_file"):
        return {
            "action": "extend",
            "reason": "Add comments to existing summary",
            "suggested_output": "D",
            "files_to_backup": [],
        }

    # Check if any changes at all
    any_changes = any(
        changes.get(field, {}).get("changed", False)
        for field in ["views", "likes", "comment_count", "title"]
    )

    if any_changes and not issues:
        return {
            "action": "metadata_only",
            "reason": "Metadata changed (no content update needed)",
            "files_to_backup": [],
        }

    return {
        "action": "none",
        "reason": "No updates needed",
        "files_to_backup": [],
    }


def fetch_current_metadata(video_url: str, output_dir: Path) -> dict:
    """Fetch current video metadata from YouTube."""
    extractor = YouTubeDataExtractor(
        fs=RealFileSystem(), cmd=RealCommandRunner()
    )

    try:
        extractor.check_yt_dlp()
        raw_data = extractor.fetch_video_data(video_url, output_dir)

        return {
            "title": raw_data.get("title"),
            "views": raw_data.get("view_count"),
            "likes": raw_data.get("like_count"),
            "comments": raw_data.get("comment_count"),
        }
    except FileOperationError as e:
        error_str = str(e).lower()
        if "unavailable" in error_str or "private" in error_str:
            raise VideoUnavailableError(f"Video unavailable: {e}")
        raise


def prepare_update(video_url: str, output_dir: Path) -> dict:
    """
    Main entry point: analyze existing files and prepare update recommendation.
    """
    video_id = extract_video_id(video_url)
    existing = check_existing(video_url, output_dir)

    if not existing["exists"]:
        return {
            "status": "NEW",
            "video_id": video_id,
            "recommendation": "EXTRACT_NEW",
            "message": "No existing extraction found",
        }

    stored_meta = existing.get("stored_metadata", {})

    try:
        current_meta = fetch_current_metadata(video_url, output_dir)
    except VideoUnavailableError as e:
        return {
            "status": "UNAVAILABLE",
            "video_id": video_id,
            "existing_files": {
                "summary": existing.get("summary_file"),
                "transcript": existing.get("transcript_file"),
                "comments": existing.get("comment_file"),
            },
            "recommendation": "SKIP",
            "message": str(e),
        }

    # Build changes dict
    changes = {
        "views": compare_counts(
            parse_count(stored_meta.get("views")),
            current_meta.get("views")
        ),
        "likes": compare_counts(
            parse_count(stored_meta.get("likes")),
            current_meta.get("likes")
        ),
        "comment_count": compare_counts(
            parse_count(stored_meta.get("comments")),
            current_meta.get("comments")
        ),
        "title": compare_strings(stored_meta.get("title"), current_meta.get("title")),
    }

    issues = detect_issues(existing, changes)
    recommendation = generate_recommendation(existing, changes, issues)

    base_name = f"youtube_{video_id}"
    intermediate_patterns = get_key_intermediate_files(base_name)
    intermediate = [f for f in intermediate_patterns if (output_dir / f).exists()]

    return {
        "status": "EXISTS",
        "video_id": video_id,
        "existing_files": {
            "summary": existing.get("summary_file"),
            "transcript": existing.get("transcript_file"),
            "comments": existing.get("comment_file"),
        },
        "intermediate_files": intermediate,
        "stored_metadata": stored_meta,
        "current_metadata": {
            "title": current_meta.get("title"),
            "views": format_count_compact(current_meta.get("views")),
            "likes": format_count_compact(current_meta.get("likes")),
            "comments": format_count_compact(current_meta.get("comments")),
        },
        "changes": changes,
        "issues": issues,
        **recommendation,
    }
