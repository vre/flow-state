"""Channel listing and video matching library.

Lists channel videos via yt-dlp flat-playlist, matches against
locally extracted files, and checks comment growth.
"""

import json
import re
import subprocess
from pathlib import Path

from lib.check_existing import extract_metadata_from_file
from lib.prepare_update import parse_count
from lib.shared_types import format_count

CHECKED_SELECTION_RE = re.compile(r"^- \[[xX]\] \*\*.+?\*\* .*?\(([A-Za-z0-9_-]{11})\)\s*$")


def parse_channel_entry(entry: dict) -> dict:
    """Parse a single yt-dlp flat-playlist JSON entry into normalized dict.

    Args:
        entry: Raw JSON dict from yt-dlp --flat-playlist --dump-json.

    Returns:
        Dict with video_id, title, views, view_count, description, duration, url.
    """
    view_count = entry.get("view_count")
    if view_count is not None:
        views = format_count(view_count)
    else:
        views = "N/A"

    return {
        "video_id": entry["id"],
        "title": entry.get("title", "Untitled"),
        "views": views,
        "view_count": view_count,
        # Keep enough text for model-based cleanup without exploding context size.
        "description": (entry.get("description") or "")[:500],
        "duration": entry.get("duration_string", "N/A"),
        "url": entry.get("url") or entry.get("webpage_url", ""),
    }


def parse_channel_metadata(entry: dict) -> dict:
    """Extract channel-level metadata from a flat-playlist entry.

    Args:
        entry: Any entry from yt-dlp --flat-playlist --dump-json
               (playlist_* fields are the same on every entry).

    Returns:
        Dict with name, id, url, total_videos, verified.
    """
    return {
        "name": entry.get("playlist_channel"),
        "id": entry.get("playlist_channel_id"),
        "url": entry.get("playlist_webpage_url"),
        "total_videos": entry.get("playlist_count") or entry.get("n_entries"),
        "verified": entry.get("channel_is_verified", False),
    }


def _normalize_channel_url(url: str) -> str:
    """Ensure channel URL points to /videos tab.

    Accepts full URLs or bare channel IDs (UC..., 24 chars).
    YouTube channel URLs without /videos return Videos + Shorts + Live
    as separate playlists, breaking --playlist-items pagination.
    """
    url = url.strip()
    # Bare channel ID: UCxxxxxxxxxxxxxxxxxxxxxxxx
    if re.match(r"^UC[A-Za-z0-9_-]{22}$", url):
        return f"https://www.youtube.com/channel/{url}/videos"
    url = url.rstrip("/")
    if url.endswith("/videos"):
        return url
    # Strip other tabs if present
    for tab in ("/shorts", "/live", "/streams", "/playlists", "/community"):
        if url.endswith(tab):
            url = url[: -len(tab)]
            break
    return url + "/videos"


def list_channel_videos(
    channel_url: str,
    offset: int = 0,
    limit: int = 20,
) -> list[dict]:
    """Fetch channel video list via yt-dlp flat-playlist.

    Args:
        channel_url: YouTube channel URL (any tab, normalized to /videos).
        offset: Number of videos to skip (0-indexed).
        limit: Max videos to return.

    Returns:
        List of raw yt-dlp JSON dicts.
    """
    url = _normalize_channel_url(channel_url)
    start = offset + 1
    end = offset + limit
    result = subprocess.run(
        [
            "yt-dlp",
            "--flat-playlist",
            "--dump-json",
            "--sleep-requests",
            "0.5",
            "--playlist-items",
            f"{start}:{end}",
            url,
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )

    if result.returncode != 0 and not result.stdout.strip():
        raise RuntimeError(f"yt-dlp failed: {result.stderr.strip() or 'unknown error'}")

    entries = []
    for line in result.stdout.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # skip yt-dlp warning/error lines mixed with JSON

    return entries


def _is_summary_file(path: Path) -> bool:
    """Check if file is a main summary (not backup, comments, or transcript)."""
    name = path.name
    return "_backup_" not in name and " - comments " not in name and " - transcript " not in name


def _find_summary_for_video_id(video_id: str, output_dir: Path) -> Path | None:
    """Find summary file for a video ID in output_dir and one level of subdirs."""
    dirs = [output_dir] + [d for d in output_dir.iterdir() if d.is_dir()]
    for d in dirs:
        for f in d.glob(f"*youtube - * ({video_id}).md"):
            if _is_summary_file(f):
                return f
    return None


def match_existing_videos(
    video_list: list[dict],
    output_dir: Path,
) -> tuple[list[dict], list[dict]]:
    """Split video list into new and existing based on local files.

    Args:
        video_list: List of parsed video dicts (from parse_channel_entry).
        output_dir: Directory to search for existing extractions.

    Returns:
        Tuple of (new_videos, existing_videos).
        existing_videos entries have added 'stored_comments' field.
    """
    new_videos = []
    existing_videos = []

    for video in video_list:
        video_id = video["video_id"]
        summary_file = _find_summary_for_video_id(video_id, output_dir)

        if summary_file is None:
            new_videos.append(video)
        else:
            metadata = extract_metadata_from_file(summary_file.read_text())
            existing_video = {**video, "stored_comments": metadata.get("comments")}
            existing_videos.append(existing_video)

    return new_videos, existing_videos


def check_comment_growth(
    current_counts: dict[str, int],
    output_dir: Path,
) -> list[dict]:
    """Compare current comment counts against stored values.

    Args:
        current_counts: Dict of video_id -> current comment count from YouTube.
        output_dir: Directory with existing extractions.

    Returns:
        List of dicts with video_id, title, stored_comments, current_comments,
        growth_pct, needs_refresh.
    """
    results = []

    for video_id, current in current_counts.items():
        summary_file = _find_summary_for_video_id(video_id, output_dir)
        if summary_file is None:
            continue

        metadata = extract_metadata_from_file(summary_file.read_text())
        stored = parse_count(metadata.get("comments"))

        if stored is None or stored == 0:
            results.append(
                {
                    "video_id": video_id,
                    "title": metadata.get("title", "Unknown"),
                    "stored_comments": stored,
                    "current_comments": current,
                    "growth_pct": 0.0,
                    "needs_refresh": False,
                }
            )
            continue

        growth_pct = ((current - stored) / stored) * 100
        results.append(
            {
                "video_id": video_id,
                "title": metadata.get("title", "Unknown"),
                "stored_comments": stored,
                "current_comments": current,
                "growth_pct": round(growth_pct, 1),
                "needs_refresh": growth_pct > 10,
            }
        )

    return results


def find_output_dir(base_dir: Path, channel_id: str) -> Path | None:
    """Find existing subdirectory containing channel_id in its name.

    Args:
        base_dir: Parent directory to search.
        channel_id: YouTube channel ID to look for.

    Returns:
        Path to matching subdirectory, or None.
    """
    if not base_dir.exists():
        return None
    for item in base_dir.iterdir():
        if item.is_dir() and channel_id in item.name:
            return item
    return None


def suggest_output_dir(base_dir: Path, channel_name: str, channel_id: str) -> Path:
    """Suggest a channel subdirectory path.

    Args:
        base_dir: Parent directory.
        channel_name: Channel display name.
        channel_id: YouTube channel ID.

    Returns:
        Suggested Path (not created).
    """
    clean_name = re.sub(r'[<>:"/\\|?*]', "", channel_name)
    clean_name = clean_name.replace("..", "")
    return base_dir / f"{clean_name} ({channel_id})"


def check_view_growth(
    existing_videos: list[dict],
    output_dir: Path,
    threshold: float = 0.3,
) -> list[dict]:
    """Compare flat-playlist view_count vs stored views.

    Args:
        existing_videos: List of video dicts with 'view_count' (raw int from flat-playlist).
        output_dir: Directory with existing extractions.
        threshold: Fractional growth threshold (0.3 = 30%).

    Returns:
        List of videos exceeding threshold, each with video_id, title,
        stored_views, current_views, growth_pct, has_growth.
    """
    results = []

    for video in existing_videos:
        video_id = video["video_id"]
        current = video.get("view_count")
        if current is None:
            continue

        summary_file = _find_summary_for_video_id(video_id, output_dir)
        if summary_file is None:
            continue

        metadata = extract_metadata_from_file(summary_file.read_text())
        stored = parse_count(metadata.get("views"))

        if stored is None or stored == 0:
            continue

        growth = (current - stored) / stored
        if growth <= threshold:
            continue

        results.append(
            {
                "video_id": video_id,
                "title": video.get("title", "Unknown"),
                "stored_views": format_count(stored),
                "current_views": format_count(current),
                "growth_pct": round(growth * 100, 1),
                "has_growth": True,
            }
        )

    return results


def parse_selection_checkboxes(content: str) -> list[dict]:
    """Parse checked items from markdown checkbox file.

    Tracks which section each item belongs to for routing:
    "## New videos" → section="new", "## Videos with activity" → section="growth".

    Args:
        content: Markdown file content with checkbox lines.

    Returns:
        List of dicts with video_id and section ("new" or "growth").
    """
    if not content:
        return []

    results = []
    current_section = "new"

    for line in content.split("\n"):
        # Track section headers only when they are top-level.
        if line == "## New videos":
            current_section = "new"
            continue
        if line.startswith("## Videos with activity"):
            current_section = "growth"
            continue

        match = CHECKED_SELECTION_RE.match(line)
        if match:
            results.append({"video_id": match.group(1), "section": current_section})

    return results
