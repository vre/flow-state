"""YouTube comment extraction library."""

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from lib.shared_types import (
    CommandRunner,
    Comment,
    CommentVideoData,
    FileSystem,
    VideoDataFetchError,
    VideoIdExtractionError,
    YTDLPNotFoundError,
)


def extract_video_id(url: str) -> str:
    """Extract video ID from YouTube URL."""
    if "youtu.be/" in url:
        video_id = url.split("youtu.be/")[-1].split("?")[0]
        if video_id:
            return video_id

    match = re.search(r"[?&]v=([^&]+)", url)
    if match:
        return match.group(1)

    raise VideoIdExtractionError(f"Could not extract video ID from URL: {url}")


def parse_video_data(json_data: dict[str, Any]) -> CommentVideoData:
    """Parse video data from yt-dlp JSON output."""
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

    return CommentVideoData(title=title, video_id=video_id, comments=comments)


def build_comment_hierarchy(
    comments: list[Comment],
) -> tuple[dict[str, Comment], dict[str, list[Comment]]]:
    """Build comment hierarchy from flat list."""
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
    """Format a single comment and its replies as markdown."""
    lines: list[str] = []

    if depth <= 3:
        heading_level = 3 + depth
        hashes = "#" * heading_level
        if depth == 0 and include_numbering:
            lines.append(f"{hashes} {number}. {comment.author} ({comment.like_count} likes)\n")
        else:
            lines.append(f"{hashes} {comment.author} ({comment.like_count} likes)\n")
        lines.append(f"{comment.text}\n")
    else:
        indent = "  " * (depth - 4)
        lines.append(f"{indent}- **{comment.author} ({comment.like_count} likes)**: {comment.text}\n")

    replies = replies_by_parent.get(comment.id, [])
    for reply in replies:
        lines.append(format_comment_markdown(reply, depth + 1, replies_by_parent))

    return "\n".join(lines)


def generate_comments_markdown(comments: list[Comment]) -> str:
    """Generate markdown document with hierarchical comments."""
    if not comments:
        return "No comments available\n"

    _, replies_by_parent = build_comment_hierarchy(comments)
    top_level = replies_by_parent.get("root", [])

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
    """Count top-level comments and total replies."""
    _, replies_by_parent = build_comment_hierarchy(comments)
    top_level_count = len(replies_by_parent.get("root", []))
    reply_count = len(comments) - top_level_count
    return top_level_count, reply_count


class CommentExtractor:
    """Extract YouTube comments using dependency injection for testability."""

    def __init__(self, runner: CommandRunner, filesystem: FileSystem):
        self.runner = runner
        self.filesystem = filesystem

    def check_yt_dlp(self) -> None:
        returncode, _, _ = self.runner.run(["yt-dlp", "--version"])
        if returncode != 0:
            raise YTDLPNotFoundError(
                "yt-dlp is not installed. Install options:\n"
                "  - macOS: brew install yt-dlp\n"
                "  - Ubuntu/Debian: sudo apt update && sudo apt install -y yt-dlp\n"
                "  - All systems: pip3 install yt-dlp"
            )

    def fetch_video_data(self, video_url: str, output_dir: Path) -> CommentVideoData:
        temp_json = output_dir / "video_data.json"

        try:
            returncode, stdout, stderr = self.runner.run(
                [
                    "yt-dlp",
                    "--dump-single-json",
                    "--write-comments",
                    "--skip-download",
                    "--extractor-args",
                    "youtube:comment_sort=top",
                    video_url,
                ],
                capture_stdout=True,
            )

            if returncode != 0:
                raise VideoDataFetchError(f"Failed to extract video data: {stderr}")

            self.filesystem.write_text(temp_json, stdout)
            json_str = self.filesystem.read_text(temp_json)
            data = json.loads(json_str)

            return parse_video_data(data)

        except json.JSONDecodeError as e:
            raise VideoDataFetchError(f"Failed to parse JSON: {e}") from e
        except Exception as e:
            raise VideoDataFetchError(f"Failed to fetch video data: {e}") from e
        finally:
            if self.filesystem.exists(temp_json):
                self.filesystem.remove(temp_json)

    def extract_and_save(self, video_url: str, output_dir: Path) -> tuple[Path, Path]:
        self.check_yt_dlp()
        video_id = extract_video_id(video_url)
        base_name = f"youtube_{video_id}"
        self.filesystem.mkdir(output_dir, parents=True, exist_ok=True)
        video_data = self.fetch_video_data(video_url, output_dir)

        title_file = output_dir / f"{base_name}_title.txt"
        if not self.filesystem.exists(title_file):
            self.filesystem.write_text(title_file, video_data.title)

        comments_markdown = generate_comments_markdown(video_data.comments)
        comments_file = output_dir / f"{base_name}_comments.md"
        self.filesystem.write_text(comments_file, comments_markdown)

        top_level, replies = count_comments_and_replies(video_data.comments)
        print(f"SUCCESS: {title_file}")
        if video_data.comments:
            print(f"COMMENTS: {comments_file} ({top_level} comments, {replies} replies)")
        else:
            print(f"COMMENTS: {comments_file} (no comments)")

        return title_file, comments_file


class SubprocessRunner:
    """Real command runner using subprocess."""

    def run(self, cmd: list[str], capture_stdout: bool = False) -> tuple[int, str, str]:
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
