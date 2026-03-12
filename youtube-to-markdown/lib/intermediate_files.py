"""Intermediate work file patterns for YouTube to Markdown.

Single source of truth for work files created during extraction.
Used by finalize.py for cleanup and prepare_update.py for detection.
"""


def get_summary_work_files(base_name: str) -> list[str]:
    """Work files created during summary extraction."""
    return [
        f"{base_name}_warmup.tmp",
        f"{base_name}_title.txt",
        f"{base_name}_upload_date.txt",
        f"{base_name}_metadata.md",
        f"{base_name}_description.md",
        f"{base_name}_summary.md",
        f"{base_name}_summary_tight.md",
        f"{base_name}_quick_summary.md",
        f"{base_name}_chapters.json",
        f"{base_name}_heatmap.json",
        f"{base_name}_transcript.vtt",
        f"{base_name}_transcript_dedup.md",
        f"{base_name}_transcript_no_timestamps.txt",
    ]


def get_transcript_work_files(base_name: str) -> list[str]:
    """Work files created during transcript extraction."""
    return [
        f"{base_name}_warmup.tmp",
        f"{base_name}_title.txt",
        f"{base_name}_upload_date.txt",
        f"{base_name}_description.md",
        f"{base_name}_chapters.json",
        f"{base_name}_heatmap.json",
        f"{base_name}_transcript.vtt",
        f"{base_name}_transcript_dedup.md",
        f"{base_name}_transcript_no_timestamps.txt",
        f"{base_name}_transcript_paragraphs.txt",
        f"{base_name}_transcript_paragraphs.md",
        f"{base_name}_transcript_cleaned.md",
        f"{base_name}_headings.json",
        f"{base_name}_analysis.md",
        f"{base_name}_watch_guide_requested.flag",
        f"{base_name}_watch_guide.md",
        f"{base_name}_transcript.md",
    ]


def get_comments_work_files(base_name: str) -> list[str]:
    """Work files created during comments extraction."""
    return [
        f"{base_name}_warmup.tmp",
        f"{base_name}_title.txt",
        f"{base_name}_upload_date.txt",
        f"{base_name}_comments.md",
        f"{base_name}_comments_filtered.md",
        f"{base_name}_comments_prefiltered.md",
        f"{base_name}_comments_candidates.md",
        f"{base_name}_comment_insights.md",
        f"{base_name}_comment_insights_tight.md",
    ]


def get_warmup_work_files(base_name: str) -> list[str]:
    """Write permission warmup file."""
    return [f"{base_name}_warmup.tmp"]


def get_all_work_files(base_name: str) -> list[str]:
    """All possible work files (deduplicated)."""
    all_files = (
        get_warmup_work_files(base_name)
        + get_summary_work_files(base_name)
        + get_transcript_work_files(base_name)
        + get_comments_work_files(base_name)
    )
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for f in all_files:
        if f not in seen:
            seen.add(f)
            unique.append(f)
    return unique


def get_key_intermediate_files(base_name: str) -> list[str]:
    """Key intermediate files that indicate extraction started but didn't finish.

    If these exist without corresponding final files, extraction was interrupted.
    """
    return [
        f"{base_name}_metadata.md",
        f"{base_name}_transcript.vtt",
        f"{base_name}_comments.md",
    ]
