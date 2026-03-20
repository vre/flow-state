"""Shared helpers for builder-mcp tests."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

SCRIPTS_DIR = Path(__file__).parents[2] / "builder-mcp" / "scripts"


def load_builder_mcp_script(name: str) -> ModuleType:
    """Load a builder-mcp script module under a unique test-only name.

    Args:
        name: Script filename without the ``.py`` suffix.

    Returns:
        Loaded Python module.

    Raises:
        ImportError: If the script cannot be loaded.
    """
    script_path = SCRIPTS_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"builder_mcp_{name}", script_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load script: {script_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
