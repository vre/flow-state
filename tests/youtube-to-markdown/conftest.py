"""Pytest configuration and shared fixtures."""

import sys
from pathlib import Path
from typing import Any

import pytest

# Add youtube-to-markdown directory to Python path for lib imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "youtube-to-markdown"))

from lib.shared_types import CommandResult


class MockFileSystem:
    """Mock file system for testing."""

    def __init__(self):
        self.files: dict[Path, str] = {}
        self.directories: set[Path] = set()

    def read_text(self, path: Path, encoding: str = "utf-8") -> str:
        if path not in self.files:
            raise FileNotFoundError(f"{path} not found")
        return self.files[path]

    def write_text(self, path: Path, content: str, encoding: str = "utf-8") -> None:
        self.files[path] = content

    def exists(self, path: Path) -> bool:
        return path in self.files or path in self.directories

    def mkdir(self, path: Path, parents: bool = True, exist_ok: bool = True) -> None:
        self.directories.add(path)

    def remove(self, path: Path) -> None:
        if path in self.files:
            del self.files[path]

    def glob(self, pattern: str, directory: Path) -> list[Path]:
        # Simple glob implementation for tests
        import fnmatch

        results = []
        for file_path in self.files.keys():
            if file_path.parent == directory:
                if fnmatch.fnmatch(file_path.name, pattern):
                    results.append(file_path)
        return results


class MockCommandRunner:
    """Mock command runner for testing."""

    def __init__(self):
        self.commands: list[list[str]] = []
        self.responses: dict[str, CommandResult] = {}

    def run(
        self,
        command: list[str],
        capture_output: bool = False,
        text: bool = False,
        check: bool = False,
        timeout: int | None = None,
        stdout: Any = None,
        stderr: Any = None,
    ) -> CommandResult:
        """Record command and return mocked response."""
        self.commands.append(command)

        # Build command key for lookup
        cmd_key = " ".join(command)

        # Return mocked response if available
        if cmd_key in self.responses:
            result = self.responses[cmd_key]
            if check and result.returncode != 0:
                raise Exception(f"Command failed: {cmd_key}")
            return result

        # Default successful response
        return CommandResult(returncode=0, stdout="", stderr="")

    def set_response(self, command: str, returncode: int = 0, stdout: str = "", stderr: str = ""):
        """Set mocked response for a command."""
        self.responses[command] = CommandResult(returncode, stdout, stderr)


@pytest.fixture
def mock_fs():
    """Provide mock file system."""
    return MockFileSystem()


@pytest.fixture
def mock_cmd():
    """Provide mock command runner."""
    return MockCommandRunner()


@pytest.fixture
def sample_video_data():
    """Sample video metadata from yt-dlp."""
    return {
        "title": "Test Video Title",
        "webpage_url": "https://youtube.com/watch?v=test123",
        "uploader": "Test Channel",
        "channel_url": "https://youtube.com/c/testchannel",
        "channel_follower_count": 1000000,
        "upload_date": "20240101",
        "view_count": 500000,
        "like_count": 10000,
        "duration": 3661,  # 1:01:01
        "description": "Test video description",
        "chapters": [
            {"start_time": 0, "end_time": 60, "title": "Introduction"},
            {"start_time": 60, "end_time": 120, "title": "Main Content"},
        ],
        "language": "en",
    }


@pytest.fixture
def sample_vtt_content():
    """Sample VTT file content."""
    return """WEBVTT
Kind: captions
Language: en

00:00:01.000 --> 00:00:03.000
First line of text

00:00:03.000 --> 00:00:05.000
First line of text

00:00:05.000 --> 00:00:07.000
Second line of text

00:00:07.000 --> 00:00:09.000
Third line of text
"""


@pytest.fixture
def sample_deduped_transcript():
    """Sample deduplicated transcript."""
    return """[00:00:01.000] First line of text
[00:00:05.000] Second line of text
[00:00:07.000] Third line of text
[00:00:09.000] Fourth line of text
[00:00:11.000] Fifth line of text"""


@pytest.fixture
def sample_template():
    """Sample markdown template for summary file."""
    return """## Quick Summary

{quick_summary}

## Video

{metadata}

## Summary

{summary}
"""


@pytest.fixture
def sample_transcript_template():
    """Sample markdown template for transcript file."""
    return """## Description

{description}

## Transcription

{transcription}
"""
