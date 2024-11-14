#!/usr/bin/env python3
"""
Extracts YouTube video comments.

Usage: extract_comments.py <YOUTUBE_URL> <OUTPUT_DIR>
Output: Creates youtube_{VIDEO_ID}_name.txt, youtube_{VIDEO_ID}_comments.md
"""

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from types_and_exceptions import (
    Comment,
    CommandRunner,
    FileSystem,
    VideoData,
    VideoDataFetchError,
    VideoIDExtractionError,
    YTDLPNotFoundError,
)


# Business logic functions (pure, testable)
def extract_video_id(url: str) -> str:
    """
    Extract video ID from YouTube URL.

    Args:
        url: YouTube URL (supports youtube.com and youtu.be formats)

    Returns:
        Video ID string

    Raises:
        VideoIDExtractionError: If video ID cannot be extracted
    """
    # Handle youtu.be format
    if "youtu.be/" in url:
        video_id = url.split("youtu.be/")[-1].split("?")[0]
        if video_id:
            return video_id

    # Handle youtube.com format with v= parameter
    match = re.search(r"[?&]v=([^&]+)", url)
    if match:
        return match.group(1)

    raise VideoIDExtractionError(f"Could not extract video ID from URL: {url}")


def parse_video_data(json_data: dict[str, Any]) -> VideoData:
    """
    Parse video data from yt-dlp JSON output.

    Args:
        json_data: JSON data from yt-dlp

    Returns:
        VideoData object with title and comments
    """
    title = json_data.get("title", "Untitled")
    video_id = json_data.get("id", "")

    comments_raw = json_data.get("comments", [])
    comments = [
        Comment(
            id=c.get("id", ""),
            author=c.get("author", "Unknown"),
            text=c.get("text", ""),
            like_count=c.get("like_count", 0),
            parent=c.get("parent", "root"),
        )
        for c in comments_raw
    ]

    return VideoData(title=title, video_id=video_id, comments=comments)


def build_comment_hierarchy(
    comments: list[Comment],
) -> tuple[dict[str, Comment], dict[str, list[Comment]]]:
    """
    Build comment hierarchy from flat list.

    Args:
        comments: Flat list of comments

    Returns:
        Tuple of (comment_by_id, replies_by_parent) dictionaries
    """
    comment_by_id: dict[str, Comment] = {}
    replies_by_parent: dict[str, list[Comment]] = {}

    for comment in comments:
        comment_by_id[comment.id] = comment

        parent = comment.parent
        if parent not in replies_by_parent:
            replies_by_parent[parent] = []
        replies_by_parent[parent].append(comment)

    return comment_by_id, replies_by_parent


def format_comment_markdown(
    comment: Comment,
    depth: int,
    replies_by_parent: dict[str, list[Comment]],
    include_numbering: bool = False,
    number: int = 0,
) -> str:
    """
    Format a single comment and its replies as markdown.

    Uses heading levels 3-5 for depths 0-2, flattens deeper levels to bullet lists.

    Args:
        comment: Comment to format
        depth: Nesting depth (0 = top-level)
        replies_by_parent: Dictionary mapping parent IDs to reply lists
        include_numbering: If True, include number in heading (top-level only)
        number: Number to use if include_numbering is True

    Returns:
        Formatted markdown string
    """
    lines: list[str] = []

    if depth == 0:
        # Top-level: ### (foldable in Obsidian)
        prefix = f"{number}. " if include_numbering else ""
        lines.append(f"### {prefix}{comment.author} ({comment.like_count} likes)\n")
        lines.append(f"{comment.text}\n")
    elif depth == 1:
        # First reply level: ####
        lines.append(f"#### {comment.author} ({comment.like_count} likes)\n")
        lines.append(f"{comment.text}\n")
    elif depth == 2:
        # Second reply level: #####
        lines.append(f"##### {comment.author} ({comment.like_count} likes)\n")
        lines.append(f"{comment.text}\n")
    else:
        # Deeper levels: flatten as bullet list
        lines.append(
            f"- **{comment.author} ({comment.like_count} likes)**: {comment.text}\n"
        )

        # Flatten all deeper replies (don't recurse)
        replies = replies_by_parent.get(comment.id, [])
        for reply in replies:
            lines.append(
                f"  - **{reply.author} ({reply.like_count} likes)**: {reply.text}\n"
            )
        if replies:
            lines.append("\n")
        return "\n".join(lines)

    # Recursively format replies for depth 0-2
    replies = replies_by_parent.get(comment.id, [])
    for reply in replies:
        lines.append(
            format_comment_markdown(reply, depth + 1, replies_by_parent)
        )

    return "\n".join(lines)


def generate_comments_markdown(comments: list[Comment], max_top_level: int = 50) -> str:
    """
    Generate markdown document with hierarchical comments.

    Args:
        comments: List of comments
        max_top_level: Maximum number of top-level comments to include

    Returns:
        Markdown formatted string
    """
    if not comments:
        return "No comments available\n"

    _, replies_by_parent = build_comment_hierarchy(comments)
    top_level = replies_by_parent.get("root", [])[:max_top_level]

    lines: list[str] = []
    for idx, comment in enumerate(top_level, 1):
        lines.append(
            format_comment_markdown(
                comment,
                depth=0,
                replies_by_parent=replies_by_parent,
                include_numbering=True,
                number=idx,
            )
        )

    return "\n".join(lines)


def count_comments_and_replies(comments: list[Comment]) -> tuple[int, int]:
    """
    Count top-level comments and total replies.

    Args:
        comments: List of comments

    Returns:
        Tuple of (top_level_count, reply_count)
    """
    _, replies_by_parent = build_comment_hierarchy(comments)
    top_level_count = len(replies_by_parent.get("root", []))
    reply_count = len(comments) - top_level_count
    return top_level_count, reply_count


# I/O layer (uses injected dependencies)
class CommentExtractor:
    """Extract YouTube comments using dependency injection for testability."""

    def __init__(self, runner: CommandRunner, filesystem: FileSystem):
        """
        Initialize extractor with dependencies.

        Args:
            runner: Command runner for executing yt-dlp
            filesystem: File system interface for I/O
        """
        self.runner = runner
        self.filesystem = filesystem

    def check_yt_dlp(self) -> None:
        """
        Check if yt-dlp is installed.

        Raises:
            YTDLPNotFoundError: If yt-dlp is not installed
        """
        returncode, _, _ = self.runner.run(["yt-dlp", "--version"])
        if returncode != 0:
            raise YTDLPNotFoundError(
                "yt-dlp is not installed. Install options:\n"
                "  - macOS: brew install yt-dlp\n"
                "  - Ubuntu/Debian: sudo apt update && sudo apt install -y yt-dlp\n"
                "  - All systems: pip3 install yt-dlp"
            )

    def fetch_video_data(self, video_url: str, output_dir: Path) -> VideoData:
        """
        Fetch video data from YouTube using yt-dlp.

        Args:
            video_url: YouTube video URL
            output_dir: Directory to store temporary JSON file

        Returns:
            VideoData object

        Raises:
            VideoDataFetchError: If fetching or parsing fails
        """
        temp_json = output_dir / "video_data.json"

        try:
            # Run yt-dlp and capture output to file
            returncode, stdout, stderr = self.runner.run(
                [
                    "yt-dlp",
                    "--dump-single-json",
                    "--write-comments",
                    "--skip-download",
                    video_url,
                ],
                capture_stdout=True,
            )

            if returncode != 0:
                raise VideoDataFetchError(
                    f"Failed to extract video data: {stderr}"
                )

            # Write stdout to temp file
            self.filesystem.write_text(temp_json, stdout)

            # Read and parse JSON
            json_str = self.filesystem.read_text(temp_json)
            data = json.loads(json_str)

            return parse_video_data(data)

        except json.JSONDecodeError as e:
            raise VideoDataFetchError(f"Failed to parse JSON: {e}") from e
        except Exception as e:
            raise VideoDataFetchError(f"Failed to fetch video data: {e}") from e
        finally:
            # Clean up temp file
            if self.filesystem.exists(temp_json):
                self.filesystem.remove(temp_json)

    def extract_and_save(
        self, video_url: str, output_dir: Path
    ) -> tuple[Path, Path]:
        """
        Extract comments and save to files.

        Args:
            video_url: YouTube video URL
            output_dir: Output directory

        Returns:
            Tuple of (name_file_path, comments_file_path)

        Raises:
            VideoIDExtractionError: If video ID cannot be extracted
            VideoDataFetchError: If fetching fails
            YTDLPNotFoundError: If yt-dlp is not installed
        """
        # Validate yt-dlp is available
        self.check_yt_dlp()

        # Extract video ID
        video_id = extract_video_id(video_url)
        base_name = f"youtube_{video_id}"

        # Create output directory
        self.filesystem.mkdir(output_dir, parents=True, exist_ok=True)

        # Fetch video data
        video_data = self.fetch_video_data(video_url, output_dir)

        # Save video title
        name_file = output_dir / f"{base_name}_name.txt"
        self.filesystem.write_text(name_file, video_data.title)

        # Generate and save comments markdown
        comments_markdown = generate_comments_markdown(video_data.comments)
        comments_file = output_dir / f"{base_name}_comments.md"
        self.filesystem.write_text(comments_file, comments_markdown)

        # Print summary
        top_level, replies = count_comments_and_replies(video_data.comments)
        print(f"SUCCESS: {name_file}")
        if video_data.comments:
            print(f"COMMENTS: {comments_file} ({top_level} comments, {replies} replies)")
        else:
            print(f"COMMENTS: {comments_file} (no comments)")

        return name_file, comments_file


# Real implementations for production use
class SubprocessRunner:
    """Real command runner using subprocess."""

    def run(self, cmd: list[str], capture_stdout: bool = False) -> tuple[int, str, str]:
        """Run command using subprocess."""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
            )
            return result.returncode, result.stdout, result.stderr
        except FileNotFoundError:
            return 1, "", f"Command not found: {cmd[0]}"


class RealFileSystem:
    """Real file system implementation."""

    def read_text(self, path: Path) -> str:
        """Read text from file."""
        return path.read_text(encoding="utf-8")

    def write_text(self, path: Path, content: str) -> None:
        """Write text to file."""
        path.write_text(content, encoding="utf-8")

    def exists(self, path: Path) -> bool:
        """Check if path exists."""
        return path.exists()

    def mkdir(self, path: Path, parents: bool = False, exist_ok: bool = False) -> None:
        """Create directory."""
        path.mkdir(parents=parents, exist_ok=exist_ok)

    def remove(self, path: Path) -> None:
        """Remove file."""
        path.unlink()


def main() -> None:
    """Main entry point."""
    # Parse arguments
    if len(sys.argv) != 3:
        print("Usage: extract_comments.py <YOUTUBE_URL> <OUTPUT_DIR>", file=sys.stderr)
        sys.exit(1)

    video_url = sys.argv[1]
    output_dir = Path(sys.argv[2])

    # Validate arguments
    if not video_url:
        print("ERROR: No YouTube URL provided", file=sys.stderr)
        sys.exit(1)

    # Create extractor with real dependencies
    extractor = CommentExtractor(SubprocessRunner(), RealFileSystem())

    try:
        extractor.extract_and_save(video_url, output_dir)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
