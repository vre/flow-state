"""Tests for build_project.py."""

import json
import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from project_builder.build_project import (
    create_base,
    create_cli,
    create_mcp,
    create_skill,
    dry_run_report,
    init_git,
    to_pkg_name,
)

PROJECT_BUILDER_ROOT = str(Path(__file__).parents[2] / "project-builder")


class TestNameConversion:
    def test_kebab_to_snake(self):
        assert to_pkg_name("my-tool") == "my_tool"

    def test_already_snake(self):
        assert to_pkg_name("my_tool") == "my_tool"

    def test_single_word(self):
        assert to_pkg_name("tool") == "tool"

    def test_multiple_hyphens(self):
        assert to_pkg_name("my-cool-tool") == "my_cool_tool"


class TestCreateBase:
    def test_creates_project_directory(self, output_dir: Path):
        project_dir = create_base("test-project", output_dir)
        assert project_dir.exists()
        assert project_dir.name == "test-project"

    def test_creates_documentation_files(self, output_dir: Path):
        project_dir = create_base("test-project", output_dir)
        for name in ["CLAUDE.md", "README.md", "CHANGELOG.md", "DEVELOPMENT.md", "TESTING.md", "LICENSE"]:
            assert (project_dir / name).exists(), f"Missing {name}"

    def test_creates_agents_symlink(self, output_dir: Path):
        project_dir = create_base("test-project", output_dir)
        agents = project_dir / "AGENTS.md"
        assert agents.is_symlink()
        assert agents.resolve() == (project_dir / "CLAUDE.md").resolve()

    def test_creates_config_files(self, output_dir: Path):
        project_dir = create_base("test-project", output_dir)
        for name in [".gitignore", ".markdownlint.json", ".pre-commit-config.yaml"]:
            assert (project_dir / name).exists(), f"Missing {name}"

    def test_creates_pyproject_toml(self, output_dir: Path):
        project_dir = create_base("test-project", output_dir)
        pyproject = project_dir / "pyproject.toml"
        assert pyproject.exists()
        content = pyproject.read_text()
        assert 'name = "test-project"' in content
        assert "hatchling" in content
        assert "ruff" in content

    def test_creates_marketplace_json(self, output_dir: Path):
        project_dir = create_base("test-project", output_dir)
        mp = project_dir / ".claude-plugin" / "marketplace.json"
        assert mp.exists()
        data = json.loads(mp.read_text())
        assert data["name"] == "test-project"

    def test_creates_tests_directory(self, output_dir: Path):
        project_dir = create_base("test-project", output_dir)
        assert (project_dir / "tests" / "conftest.py").exists()
        assert (project_dir / "tests" / "test_test_project.py").exists()

    def test_placeholder_test_content(self, output_dir: Path):
        project_dir = create_base("test-project", output_dir)
        content = (project_dir / "tests" / "test_test_project.py").read_text()
        assert "assert True" in content

    def test_creates_docs_plans_directory(self, output_dir: Path):
        project_dir = create_base("test-project", output_dir)
        assert (project_dir / "docs" / "plans").is_dir()

    def test_creates_worktrees_directory(self, output_dir: Path):
        project_dir = create_base("test-project", output_dir)
        assert (project_dir / ".worktrees").is_dir()

    def test_empty_dirs_have_gitkeep(self, output_dir: Path):
        """Empty dirs need .gitkeep or git won't track them in worktrees/clones."""
        project_dir = create_base("test-project", output_dir)
        assert (project_dir / "docs" / "plans" / ".gitkeep").exists()
        assert (project_dir / ".worktrees" / ".gitkeep").exists()

    def test_gitignore_includes_worktrees(self, output_dir: Path):
        project_dir = create_base("test-project", output_dir)
        content = (project_dir / ".gitignore").read_text()
        assert ".worktrees/" in content

    def test_gitignore_includes_uv_lock(self, output_dir: Path):
        project_dir = create_base("test-project", output_dir)
        content = (project_dir / ".gitignore").read_text()
        assert "uv.lock" in content

    def test_gitignore_includes_claude(self, output_dir: Path):
        project_dir = create_base("test-project", output_dir)
        content = (project_dir / ".gitignore").read_text()
        assert ".claude/" in content

    def test_claude_md_has_persona(self, output_dir: Path):
        project_dir = create_base("test-project", output_dir)
        content = (project_dir / "CLAUDE.md").read_text()
        assert "Speak like a Finn" in content
        assert "NEVER START IMPLEMENTATION BEFORE APPROVAL" in content

    def test_claude_md_has_dev_process(self, output_dir: Path):
        project_dir = create_base("test-project", output_dir)
        content = (project_dir / "CLAUDE.md").read_text()
        assert "THE DEVELOPMENT PROCESS" in content
        assert "Context Management" in content

    def test_claude_md_excludes_implementing_sections(self, output_dir: Path):
        project_dir = create_base("test-project", output_dir)
        content = (project_dir / "CLAUDE.md").read_text()
        assert "Implementing Skills" not in content
        assert "Implementing MCPs" not in content
        assert "Implementing CLI Scripts" not in content

    def test_fails_if_project_dir_exists(self, output_dir: Path):
        (output_dir / "test-project").mkdir()
        with pytest.raises(FileExistsError):
            create_base("test-project", output_dir)

    def test_markdownlint_json_valid(self, output_dir: Path):
        project_dir = create_base("test-project", output_dir)
        data = json.loads((project_dir / ".markdownlint.json").read_text())
        assert data["default"] is True

    def test_pre_commit_config_has_ruff(self, output_dir: Path):
        project_dir = create_base("test-project", output_dir)
        content = (project_dir / ".pre-commit-config.yaml").read_text()
        assert "ruff" in content


class TestCreateSkill:
    def test_creates_skill_md(self, output_dir: Path):
        project_dir = create_base("my-skill", output_dir)
        create_skill("my-skill", project_dir)
        assert (project_dir / "SKILL.md").exists()

    def test_skill_md_has_frontmatter(self, output_dir: Path):
        project_dir = create_base("my-skill", output_dir)
        create_skill("my-skill", project_dir)
        content = (project_dir / "SKILL.md").read_text()
        assert "---" in content
        assert "name: my-skill" in content
        assert "keywords:" in content

    def test_creates_scripts_directory(self, output_dir: Path):
        project_dir = create_base("my-skill", output_dir)
        create_skill("my-skill", project_dir)
        assert (project_dir / "scripts").is_dir()

    def test_creates_stub_script(self, output_dir: Path):
        project_dir = create_base("my-skill", output_dir)
        create_skill("my-skill", project_dir)
        assert (project_dir / "scripts" / "10_example.py").exists()

    def test_creates_subskills_directory(self, output_dir: Path):
        project_dir = create_base("my-skill", output_dir)
        create_skill("my-skill", project_dir)
        assert (project_dir / "subskills").is_dir()

    def test_subskills_has_gitkeep(self, output_dir: Path):
        """Empty subskills/ needs .gitkeep to survive git worktrees/clones."""
        project_dir = create_base("my-skill", output_dir)
        create_skill("my-skill", project_dir)
        assert (project_dir / "subskills" / ".gitkeep").exists()

    def test_creates_python_package(self, output_dir: Path):
        project_dir = create_base("my-skill", output_dir)
        create_skill("my-skill", project_dir)
        assert (project_dir / "my_skill" / "__init__.py").exists()

    def test_skill_md_is_stub(self, output_dir: Path):
        project_dir = create_base("my-skill", output_dir)
        create_skill("my-skill", project_dir)
        content = (project_dir / "SKILL.md").read_text()
        assert "TODO" in content

    def test_marketplace_has_skills_field(self, output_dir: Path):
        project_dir = create_base("my-skill", output_dir)
        create_skill("my-skill", project_dir)
        mp = project_dir / ".claude-plugin" / "marketplace.json"
        data = json.loads(mp.read_text())
        assert "skills" in data["plugins"][0]
        assert data["plugins"][0]["skills"] == ["./"]


class TestCreateMcp:
    def test_creates_mcp_json(self, output_dir: Path):
        project_dir = create_base("my-mcp", output_dir)
        create_mcp("my-mcp", project_dir)
        assert (project_dir / ".mcp.json").exists()

    def test_mcp_json_has_plugin_root(self, output_dir: Path):
        project_dir = create_base("my-mcp", output_dir)
        create_mcp("my-mcp", project_dir)
        content = (project_dir / ".mcp.json").read_text()
        assert "${CLAUDE_PLUGIN_ROOT}" in content

    def test_creates_server_py(self, output_dir: Path):
        project_dir = create_base("my-mcp", output_dir)
        create_mcp("my-mcp", project_dir)
        assert (project_dir / "my_mcp" / "server.py").exists()

    def test_server_py_has_fastmcp(self, output_dir: Path):
        project_dir = create_base("my-mcp", output_dir)
        create_mcp("my-mcp", project_dir)
        content = (project_dir / "my_mcp" / "server.py").read_text()
        assert "FastMCP" in content

    def test_creates_init_with_main(self, output_dir: Path):
        project_dir = create_base("my-mcp", output_dir)
        create_mcp("my-mcp", project_dir)
        content = (project_dir / "my_mcp" / "__init__.py").read_text()
        assert "main" in content

    def test_pyproject_has_mcp_deps(self, output_dir: Path):
        project_dir = create_base("my-mcp", output_dir)
        create_mcp("my-mcp", project_dir)
        content = (project_dir / "pyproject.toml").read_text()
        assert "mcp" in content
        assert "pydantic" in content

    def test_pyproject_has_entry_point(self, output_dir: Path):
        project_dir = create_base("my-mcp", output_dir)
        create_mcp("my-mcp", project_dir)
        content = (project_dir / "pyproject.toml").read_text()
        assert 'my-mcp = "my_mcp:main"' in content

    def test_marketplace_no_skills_field(self, output_dir: Path):
        project_dir = create_base("my-mcp", output_dir)
        create_mcp("my-mcp", project_dir)
        mp = project_dir / ".claude-plugin" / "marketplace.json"
        data = json.loads(mp.read_text())
        assert "skills" not in data["plugins"][0]


class TestCreateCli:
    def test_creates_cli_py(self, output_dir: Path):
        project_dir = create_base("my-cli", output_dir)
        create_cli("my-cli", project_dir)
        assert (project_dir / "my_cli" / "cli.py").exists()

    def test_cli_py_has_argparse(self, output_dir: Path):
        project_dir = create_base("my-cli", output_dir)
        create_cli("my-cli", project_dir)
        content = (project_dir / "my_cli" / "cli.py").read_text()
        assert "argparse" in content

    def test_cli_py_has_format_json(self, output_dir: Path):
        project_dir = create_base("my-cli", output_dir)
        create_cli("my-cli", project_dir)
        content = (project_dir / "my_cli" / "cli.py").read_text()
        assert "json" in content

    def test_creates_init_with_main(self, output_dir: Path):
        project_dir = create_base("my-cli", output_dir)
        create_cli("my-cli", project_dir)
        content = (project_dir / "my_cli" / "__init__.py").read_text()
        assert "main" in content

    def test_pyproject_has_entry_point(self, output_dir: Path):
        project_dir = create_base("my-cli", output_dir)
        create_cli("my-cli", project_dir)
        content = (project_dir / "pyproject.toml").read_text()
        assert 'my-cli = "my_cli.cli:main"' in content

    def test_marketplace_no_skills_field(self, output_dir: Path):
        project_dir = create_base("my-cli", output_dir)
        create_cli("my-cli", project_dir)
        mp = project_dir / ".claude-plugin" / "marketplace.json"
        data = json.loads(mp.read_text())
        assert "skills" not in data["plugins"][0]


class TestInitGit:
    @patch("subprocess.run")
    def test_runs_git_init(self, mock_run, project_dir: Path):
        mock_run.return_value = subprocess.CompletedProcess([], 0)
        init_git(project_dir)
        calls = [c.args[0] for c in mock_run.call_args_list]
        assert any("git" in c and "init" in c for c in calls)

    @patch("subprocess.run")
    def test_runs_initial_commit(self, mock_run, project_dir: Path):
        mock_run.return_value = subprocess.CompletedProcess([], 0)
        init_git(project_dir)
        calls = [c.args[0] for c in mock_run.call_args_list]
        assert any("commit" in c for c in calls)


class TestDryRun:
    def test_returns_file_list(self):
        result = dry_run_report("test-project", "skill")
        assert isinstance(result, list)
        assert len(result) > 0

    def test_includes_common_files(self):
        result = dry_run_report("test-project", "skill")
        names = [r["path"] for r in result]
        assert any("CLAUDE.md" in n for n in names)
        assert any("pyproject.toml" in n for n in names)
        assert any("tests/" in n for n in names)

    def test_skill_includes_skill_md(self):
        result = dry_run_report("test-project", "skill")
        names = [r["path"] for r in result]
        assert any("SKILL.md" in n for n in names)

    def test_mcp_includes_server_py(self):
        result = dry_run_report("test-project", "mcp")
        names = [r["path"] for r in result]
        assert any("server.py" in n for n in names)

    def test_cli_includes_cli_py(self):
        result = dry_run_report("test-project", "cli")
        names = [r["path"] for r in result]
        assert any("cli.py" in n for n in names)


class TestMainCli:
    def _run_cli(self, *args: str) -> subprocess.CompletedProcess:
        env = {**os.environ, "PYTHONPATH": PROJECT_BUILDER_ROOT}
        return subprocess.run(
            ["python3", "-m", "project_builder.build_project", *args],
            capture_output=True,
            text=True,
            env=env,
        )

    def test_no_args_exits_2(self):
        result = self._run_cli()
        assert result.returncode == 2

    def test_no_args_shows_help(self):
        result = self._run_cli()
        assert "usage" in result.stderr.lower() or "usage" in result.stdout.lower()

    def test_help_flag(self):
        result = self._run_cli("--help")
        assert result.returncode == 0
        assert "skill" in result.stdout.lower()
        assert "mcp" in result.stdout.lower()
        assert "cli" in result.stdout.lower()
