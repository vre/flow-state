"""Shared types, protocols, and exceptions for youtube-comment-analysis."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


# Custom exceptions
class YTCommentError(Exception):
    """Base exception for youtube-comment-analysis."""
    pass


class VideoIDExtractionError(YTCommentError):
    """Failed to extract video ID from URL."""
    pass


class YTDLPNotFoundError(YTCommentError):
    """yt-dlp command not found."""
    pass


class VideoDataFetchError(YTCommentError):
    """Failed to fetch video data from YouTube."""
    pass


class TemplateNotFoundError(YTCommentError):
    """Template file not found."""
    pass


# Data classes
@dataclass(frozen=True)
class Comment:
    """Represents a YouTube comment."""
    id: str
    author: str
    text: str
    like_count: int
    parent: str  # 'root' for top-level, otherwise parent comment ID


@dataclass(frozen=True)
class VideoData:
    """Represents YouTube video data."""
    title: str
    video_id: str
    comments: list[Comment]


# Protocols for dependency injection
class CommandRunner(Protocol):
    """Protocol for running external commands."""

    def run(self, cmd: list[str], capture_stdout: bool = False) -> tuple[int, str, str]:
        """
        Run a command and return (returncode, stdout, stderr).

        Args:
            cmd: Command and arguments as list
            capture_stdout: If True, capture stdout to string, otherwise to file-like object

        Returns:
            Tuple of (returncode, stdout, stderr)
        """
        ...


class FileSystem(Protocol):
    """Protocol for file system operations."""

    def read_text(self, path: Path) -> str:
        """Read text from file."""
        ...

    def write_text(self, path: Path, content: str) -> None:
        """Write text to file."""
        ...

    def exists(self, path: Path) -> bool:
        """Check if path exists."""
        ...

    def mkdir(self, path: Path, parents: bool = False, exist_ok: bool = False) -> None:
        """Create directory."""
        ...

    def remove(self, path: Path) -> None:
        """Remove file."""
        ...
