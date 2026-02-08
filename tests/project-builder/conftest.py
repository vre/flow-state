"""Shared fixtures for project-builder tests."""

import sys
from pathlib import Path

import pytest

# Add project-builder directory to Python path for lib imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "project-builder"))


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    """Provide a temporary output directory."""
    return tmp_path


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """Provide a pre-created project directory path."""
    d = tmp_path / "test-project"
    d.mkdir()
    return d
