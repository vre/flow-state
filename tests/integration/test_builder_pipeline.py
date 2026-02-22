"""Integration tests for builder skill pipeline.

Verifies project-builder → skill-builder → cli-tool-builder produces clean output.
Requires git and uv in PATH (real subprocesses).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

WORKTREE_ROOT = Path(__file__).parents[2]

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("uv") is None,
    reason="Requires git and uv",
)


def _run(script: str, *args: str) -> subprocess.CompletedProcess:
    """Run a script under WORKTREE_ROOT via subprocess."""
    env = {**os.environ, "PYTHONPATH": str(WORKTREE_ROOT / "builder-project")}
    return subprocess.run(
        [sys.executable, str(WORKTREE_ROOT / script), *args],
        capture_output=True,
        text=True,
        env=env,
    )


class TestBuilderPipeline:
    """Verify the full pipeline produces clean output."""

    def test_project_builder_creates_stub_skill_md(self, tmp_path: Path):
        """project-builder SKILL.md should be a stub with TODO markers."""
        result = _run(
            "builder-project/project_builder/build_project.py",
            "skill",
            "test-proj",
            str(tmp_path),
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        skill_md = tmp_path / "test-proj" / "SKILL.md"
        assert skill_md.exists()
        content = skill_md.read_text()
        assert "TODO" in content
        assert "10_example.py" not in content

    def test_flat_cli_creates_single_file(self, tmp_path: Path):
        """--flat should produce one .py file, no package structure."""
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        result = _run(
            "builder-cli-tool/scripts/generate_cli.py",
            "--name",
            "test_tool",
            "--operations",
            '["list", "get"]',
            "--output",
            str(scripts_dir),
            "--flat",
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert (scripts_dir / "test_tool.py").exists()
        assert not (scripts_dir / "test_tool").is_dir()
        assert not any(p.name == "pyproject.toml" for p in scripts_dir.rglob("*"))
        assert not any(p.name == "__init__.py" for p in scripts_dir.rglob("*"))
        assert not any(p.is_dir() and p.name == "tests" for p in scripts_dir.rglob("*"))

    def test_validate_structure_passes_with_flat_script(self, tmp_path: Path):
        """validate_structure.py should accept a SKILL.md referencing a flat script."""
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text(
            "---\n"
            "name: test-skill\n"
            "description: Use when testing\n"
            "keywords: test\n"
            "allowed-tools:\n"
            "  - Bash\n"
            "---\n\n"
            "# Test Skill\n\n"
            "```bash\npython3 ./scripts/test_tool.py list\n```\n"
        )
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "test_tool.py").write_text("#!/usr/bin/env python3\nprint('hello')\n")
        (tmp_path / "tests").mkdir()

        result = _run(
            "builder-skill/scripts/validate_structure.py",
            str(skill_md),
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        output = json.loads(result.stdout)
        assert output["pass"] is True, f"issues: {output['issues']}"

    def test_full_pipeline_no_nesting(self, tmp_path: Path):
        """Full pipeline should produce flat scripts/ with no nested dirs."""
        # Step 1: project-builder creates scaffold
        result = _run(
            "builder-project/project_builder/build_project.py",
            "skill",
            "test-proj",
            str(tmp_path),
        )
        assert result.returncode == 0, f"project-builder stderr: {result.stderr}"
        project_dir = tmp_path / "test-proj"

        # Step 2: cli-tool-builder --flat creates single script
        result = _run(
            "builder-cli-tool/scripts/generate_cli.py",
            "--name",
            "test_tool",
            "--operations",
            '["create", "list", "clean"]',
            "--output",
            str(project_dir / "scripts"),
            "--flat",
        )
        assert result.returncode == 0, f"cli-tool-builder stderr: {result.stderr}"

        # Verify: scripts/ has no nested directories
        scripts_dir = project_dir / "scripts"
        assert scripts_dir.is_dir()
        nested_dirs = [p for p in scripts_dir.iterdir() if p.is_dir()]
        assert len(nested_dirs) == 0, f"Unexpected nested dirs: {nested_dirs}"

        # Verify: flat script exists alongside stub
        py_files = [p for p in scripts_dir.glob("*.py") if p.name != "10_example.py"]
        assert len(py_files) == 1, f"Expected 1 .py file, got: {py_files}"
        assert py_files[0].name == "test_tool.py"

        # Verify: no pyproject.toml under scripts/
        assert not any(p.name == "pyproject.toml" for p in scripts_dir.rglob("*"))
