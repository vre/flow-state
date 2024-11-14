"""Pytest configuration for youtube-comment-analysis tests."""

import sys
from pathlib import Path

# Add youtube-comment-analysis directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "youtube-comment-analysis"))
