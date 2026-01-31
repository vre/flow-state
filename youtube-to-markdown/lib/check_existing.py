"""Library functions for checking existing YouTube video extractions."""

import re
from pathlib import Path

from lib.intermediate_files import get_key_intermediate_files
from lib.shared_types import extract_video_id


def find_existing_files(video_id: str, output_dir: Path) -> dict:
    """Find existing summary, comment, and intermediate files for a video ID."""
    # Use broad pattern first, then filter
    all_files = list(output_dir.glob(f"youtube - * ({video_id}).md"))

    # Filter out backups
    all_files = [f for f in all_files if "_backup_" not in f.name]

    summary_file = None
    comment_file = None
    transcript_file = None

    for f in all_files:
        name = f.name
        if " - comments " in name:
            comment_file = f
        elif " - transcript " in name:
            transcript_file = f
        else:
            # Main summary file (no suffix before video ID)
            summary_file = f

    # Check for intermediate files from incomplete extraction
    base_name = f"youtube_{video_id}"
    key_files = get_key_intermediate_files(base_name)
    found_intermediate = [str(output_dir / f) for f in key_files if (output_dir / f).exists()]

    return {
        "summary_file": str(summary_file) if summary_file else None,
        "comment_file": str(comment_file) if comment_file else None,
        "transcript_file": str(transcript_file) if transcript_file else None,
        "intermediate_files": found_intermediate if found_intermediate else None,
    }


def detect_v1_summary(content: str) -> bool:
    """Detect if summary uses v1.0 format (universal W5H for all videos).

    V1.0 markers:
    - Contains **What**: AND **Why**: AND **How**: pattern
    - Does NOT contain type-specific markers
    """
    has_w5h = all(marker in content for marker in ["**What**:", "**Why**:", "**How**:"])

    # Type-specific markers from v2.0
    type_markers = [
        "### Prerequisites",  # TUTORIAL
        "**Result**:",  # TUTORIAL
        "- **[",  # TIPS bullet pattern
    ]
    has_type_markers = any(marker in content for marker in type_markers)

    return has_w5h and not has_type_markers


def detect_comments_state(content: str) -> str:
    """Detect comment file state.

    Returns:
        'curated_only': Has Curated Comments but no Comment Insights section
        'v1': Has Comment Insights but no type-specific sections
        'v2': Has Comment Insights with type-specific sections
    """
    has_insights = "## Comment Insights" in content

    if not has_insights:
        return "curated_only"

    # Has insights - check for v2 type-specific sections
    type_sections = [
        "**Common Failures**",
        "**Success Patterns**",
        "**What Worked/Didn't**",
        "**Alternatives Mentioned**",
        "**Points of Agreement**",
        "**Points of Debate**",
        "**Related Stories**",
        "**Corrections/Extensions**",
        "**Debates**",
    ]

    if any(section in content for section in type_sections):
        return "v2"

    return "v1"


def detect_v1_comments(content: str) -> bool:
    """Detect if comment insights use v1.0 format (no type-specific sections).

    DEPRECATED: Use detect_comments_state() instead.
    Kept for backward compatibility.
    """
    state = detect_comments_state(content)
    # v1 or curated_only both count as "needs update" in old logic
    return state != "v2"


def has_section_content(content: str, section: str) -> bool:
    """Check if section header exists AND has non-empty content after it."""
    pattern = rf"{re.escape(section)}\s*\n(.*?)(?=\n## |\Z)"
    match = re.search(pattern, content, re.DOTALL)
    return match is not None and len(match.group(1).strip()) > 0


def validate_summary_integrity(content: str) -> tuple[bool, list[str]]:
    """Validate that summary file has all required elements with content.
    Returns (is_valid, list_of_issues).
    """
    issues = []

    if not has_section_content(content, "## Video"):
        issues.append("empty_video_section")

    if not has_section_content(content, "## Summary"):
        issues.append("empty_summary_section")
    elif "**TL;DR**" not in content:
        issues.append("missing_tldr")

    return (len(issues) == 0, issues)


def validate_transcript_integrity(content: str) -> tuple[bool, list[str]]:
    """Validate transcript file has required elements with content."""
    issues = []

    if not has_section_content(content, "## Transcription"):
        issues.append("empty_transcription_section")

    return (len(issues) == 0, issues)


def validate_comments_integrity(content: str) -> tuple[bool, list[str]]:
    """Validate comments file has required elements with content."""
    issues = []

    if not has_section_content(content, "## Comment Insights"):
        issues.append("empty_insights_section")

    return (len(issues) == 0, issues)


def extract_metadata_from_file(content: str) -> dict:
    """Extract metadata from existing summary file.

    Supports both formats:
    - New: "- **Engagement:** 2.2M views · 71.2K likes · 2.2K comments"
    - Old: "- **Views:** 2,183,167 | Likes: 71,220 | Duration: 05:28"
    """
    metadata = {
        "title": None,
        "views": None,
        "likes": None,
        "comments": None,
        "published": None,
        "extracted": None,
    }

    # Extract title: **Title:** [Title Text](url) · duration
    title_match = re.search(r"\*\*Title:\*\*\s*\[([^\]]+)\]", content)
    if title_match:
        metadata["title"] = title_match.group(1)

    # Try new engagement format first
    engagement_match = re.search(
        r"\*\*Engagement:\*\*\s*([^\s]+)\s*views\s*·\s*([^\s]+)\s*likes\s*·\s*([^\s]+)\s*comments",
        content,
    )
    if engagement_match:
        metadata["views"] = engagement_match.group(1)
        metadata["likes"] = engagement_match.group(2)
        metadata["comments"] = engagement_match.group(3)
    else:
        # Try old format: **Views:** X | Likes: Y | Duration: Z
        old_format_match = re.search(
            r"\*\*Views:\*\*\s*([^\s|]+)\s*\|\s*Likes:\s*([^\s|]+)",
            content,
        )
        if old_format_match:
            metadata["views"] = old_format_match.group(1)
            metadata["likes"] = old_format_match.group(2)

    # Parse published line
    published_match = re.search(
        r"\*\*Published:\*\*\s*(\d{4}-\d{2}-\d{2})\s*\|\s*Extracted:\s*(\d{4}-\d{2}-\d{2})",
        content,
    )
    if published_match:
        metadata["published"] = published_match.group(1)
        metadata["extracted"] = published_match.group(2)

    return metadata


def check_existing(video_url: str, output_dir: Path) -> dict:
    """Check if video has been processed and analyze existing files.

    Returns:
        Dictionary with:
        - exists: bool (final files exist)
        - has_intermediate: bool (incomplete extraction detected)
        - summary_file: path or None
        - comment_file: path or None
        - transcript_file: path or None
        - intermediate_files: list of paths or None
        - summary_v1: bool (if summary exists)
        - comments_v1: bool (if comments exist)
        - stored_metadata: dict (if summary exists)
    """
    video_id = extract_video_id(video_url)
    files = find_existing_files(video_id, output_dir)

    result = {
        "video_id": video_id,
        "exists": files["summary_file"] is not None,
        "has_intermediate": files["intermediate_files"] is not None,
        **files,
    }

    # Analyze summary if it exists
    if files["summary_file"]:
        content = Path(files["summary_file"]).read_text()
        result["summary_v1"] = detect_v1_summary(content)
        result["stored_metadata"] = extract_metadata_from_file(content)
        valid, issues = validate_summary_integrity(content)
        result["summary_valid"] = valid
        result["summary_issues"] = issues

    # Analyze transcript if it exists
    if files["transcript_file"]:
        content = Path(files["transcript_file"]).read_text()
        valid, issues = validate_transcript_integrity(content)
        result["transcript_valid"] = valid
        result["transcript_issues"] = issues

    # Analyze comments if they exist
    if files["comment_file"]:
        content = Path(files["comment_file"]).read_text()
        result["comments_state"] = detect_comments_state(content)
        result["comments_v1"] = result["comments_state"] != "v2"  # backward compat
        valid, issues = validate_comments_integrity(content)
        result["comments_valid"] = valid
        result["comments_issues"] = issues

    return result
