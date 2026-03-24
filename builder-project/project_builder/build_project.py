"""Build project structure for skills, MCP servers, or CLI tools.

Usage: python3 -m project_builder.build_project <type> <name> <output_dir> [--plugin] [--dry-run]

Arguments:
  type          Project type: skill, mcp, cli
  name          Project name (kebab-case, e.g. my-tool)
  output_dir    Parent directory for the project

Options:
  --plugin      Create Claude plugin scaffolding for mcp/cli projects
  --dry-run     Show what would be created, create nothing
  --help        Show this help text

Exit codes:
  0  Success
  1  Error
  2  Usage error
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def to_pkg_name(name: str) -> str:
    """Convert kebab-case to snake_case for Python package names."""
    return name.replace("-", "_")


# --- File content templates (deterministic, no Jinja) ---

CLAUDE_MD = """\
# Ways of Working for LLM

NEVER START IMPLEMENTATION BEFORE APPROVAL. Autopilot is FAILURE.

Speak like a Finn or a Dutch - blunt, direct, concise and factual. No flattery or empty
compliments. Nothing is done before proven done, nothing is great before proven great. Never
say: "Good thinking", "Great idea", "You're right", "Good point", "You're absolutely right",
"Good choice", "Good feedback", "Excellent find", "This is excellent".

Base answers on scientific facts, logic, and documented information. State clearly when
uncertain or when evidence is insufficient. Show your reasoning when making claims. Cite
sources when they add clarity or evidence: `[1]` in body, `[1]: <url> "description"` in references.

Present findings, suggestions, and proposed changes first. Prioritize precision over
simplification. No unnecessary jargon. Use analogies and explain domain-specific concepts when
needed. Reply in user's language. Write text in English unless file is in other language.

You are a deep expert in your subject area. Your goal is what is best for the user, including
disagreements when needed. Be critical, analytical, forward-looking. Present your own
perspective with justification. Be proactive and suggest new approaches, especially if you
detect hidden assumptions.

## THE DEVELOPMENT PROCESS

1. Plan Phase Rules
   - Work in cooperation with the human companion, don't push to proceed before they say so.
   - ALWAYS WRITE THE PLAN: 'docs/plans/' for project-specific
   - Use 'docs/research/' for discovery notes and 'docs/reflections/' for implementation reflections
   - Define measurable acceptance criteria and validation approach
   - Mission Command: include intent, goal, proper guidance with constraints and necessary situational context
   - Use exact requirements, no temporal references ("current best practices", "latest version")
   - Create git worktree under '.worktrees/[short_description]' for isolated development
   - Track pending work in TODO.md during implementation
2. Implementation Phase Rules
   - Implement ONLY what is explicitly requested - no unrequested additions
   - Don't touch working code. New ideas -> new branch, not mutation of existing features.
   - NO CODE before tests + YAGNI + KISS + DRY + Avoid Wordiness
   - Testability: Pure functions + thin `main()` glue. No DI frameworks.
   - Use `uv` for python development environment management
   - Type hints throughout
   - Google style docstrings
   - For every todo do `git add` for new files, `git commit -a -m "{minimal description}"`
3. Reflect Phase Rules
   - Mark status: `[x]` done `[-]` not done `[>]` deferred `[_]` skipped `[+]` discovered `[?]` unclear
   - Add "## Reflection": what went well, what changed from plan, lessons learned
4. Merge Phase Rules
   - Validate what was created with skeptic's eye
   - Update Documentation: CHANGELOG.md, TESTING.md, DEVELOPMENT.md, README.md, ARCHITECTURE.md
   - Ask final acceptance from the human companion

## Context Management

- If context exceeds 50%: restate current task before continuing
- At 60%: consider nuking the chat and starting fresh
- After compaction: confirm task state with user before resuming work
- Single-purpose conversations - mixing unrelated topics degrades performance ~40%
"""

GITIGNORE = """\
# Python
__pycache__/
.pytest_cache
.coverage
htmlcov/
*.py[cod]
*$py.class
*.so
.Python
*.egg-info/
dist/
build/
.eggs/
.ruff_cache

# Virtual environments
venv/
env/
.venv/
uv.lock

# IDE
.claude/*
!.claude/settings.json
.vscode/
.idea/
*.swp
*.swo

# Git worktrees
.worktrees/

# OS
.DS_Store
Thumbs.db

# Temporary files
*.tmp
*.log
*.bak
temp/
tmp/
"""

MARKDOWNLINT_JSON = """\
{
  "default": true,
  "MD013": false,
  "MD022": false,
  "MD024": false,
  "MD025": false,
  "MD028": false,
  "MD031": false,
  "MD032": false,
  "MD033": false,
  "MD034": false,
  "MD036": false,
  "MD038": false,
  "MD040": false,
  "MD041": false
}
"""

PRE_COMMIT_CONFIG = """\
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.9.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/DavidAnson/markdownlint-cli2
    rev: v0.17.2
    hooks:
      - id: markdownlint-cli2
"""

CONFTEST = '"""Shared test fixtures."""\n'

SKILL_MD_TEMPLATE = """\
---
name: {name}
description: Use when TODO
keywords: TODO
allowed-tools:
  - Bash
  - Read
---

# {title}

TODO: Use skill-builder to fill this in.
"""

STUB_SCRIPT = """\
\"\"\"Stub orchestration script.\"\"\"

import sys

if len(sys.argv) < 2:
    print("Usage: 10_example.py <input>")
    sys.exit(2)

print("Processing: " + sys.argv[1])
"""

SERVER_PY_TEMPLATE = """\
\"\"\"Single-tool MCP server with action dispatcher.\"\"\"

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("{name}")


@mcp.tool()
def use_{pkg}(action: str, payload: str | None = None) -> str:
    \"\"\"Actions: help|list

    Examples:
      {{"action": "help"}} - Show usage
      {{"action": "list"}} - List items
    \"\"\"
    actions = {{
        "help": lambda: "Usage: ...",
        "list": lambda: "[]",
    }}
    if action not in actions:
        valid = ", ".join(actions)
        return f"Unknown action '{{action}}'. Valid: {{valid}}"
    return actions[action]()


def main():
    \"\"\"Run the MCP server.\"\"\"
    mcp.run()


if __name__ == "__main__":
    main()
"""

# Minimal CLI stub — replaced by cli-tool-builder's full template (POSIX flags, TTY detection, load_env).
# This stub proves infra works (tests pass, lint passes). Domain builder adds real patterns.
CLI_PY_TEMPLATE = """\
\"\"\"CLI tool with JSON output support.\"\"\"

import argparse
import json


def main():
    \"\"\"Entry point.\"\"\"
    parser = argparse.ArgumentParser(description="{name}")
    parser.add_argument("command", choices=["list", "get", "help"])
    parser.add_argument("--format", choices=["json", "text"], default="text")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    result = dispatch(args.command)

    if args.format == "json":
        print(json.dumps(result))
    else:
        print(result.get("message", str(result)))


def dispatch(command: str) -> dict:
    \"\"\"Route command to handler.\"\"\"
    commands = {{
        "list": lambda: {{"items": [], "count": 0}},
        "get": lambda: {{"error": "id required"}},
        "help": lambda: {{"message": "Usage: {name} [list|get|help]"}},
    }}
    return commands.get(command, commands["help"])()


if __name__ == "__main__":
    main()
"""

MCP_INIT_TEMPLATE = '"""MCP server package."""\n\nfrom .server import main\n\n__all__ = ["main"]\n'

CLI_INIT_TEMPLATE = '"""CLI tool package."""\n\nfrom .cli import main\n\n__all__ = ["main"]\n'


def _pyproject_toml(name: str, project_type: str) -> str:
    """Generate pyproject.toml content."""
    pkg = to_pkg_name(name)
    deps = "[]"
    scripts = ""

    if project_type == "mcp":
        deps = '[\n    "mcp>=1.0.0",\n    "pydantic>=2.0.0",\n]'
        scripts = f'\n[project.scripts]\n{name} = "{pkg}:main"\n'
    elif project_type == "cli":
        scripts = f'\n[project.scripts]\n{name} = "{pkg}.cli:main"\n'

    return f"""\
[project]
name = "{name}"
version = "0.1.0"
description = ""
requires-python = ">=3.10"
dependencies = {deps}

[dependency-groups]
dev = ["pytest>=9.0.0"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
{scripts}
[tool.ruff]
target-version = "py310"
line-length = 140

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "D"]
ignore = ["D100", "D101", "D102", "D104", "D105", "D107", "D200", "D205", "D301", "D415", "B008", "E501"]

[tool.ruff.lint.pydocstyle]
convention = "google"

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = ["D"]
"**/scripts/*.py" = ["D103"]

[tool.pyright]
pythonVersion = "3.10"
typeCheckingMode = "basic"
"""


def _marketplace_json(name: str, project_type: str) -> str:
    """Generate marketplace.json content."""
    plugin: dict = {
        "name": name,
        "source": "./",
        "description": "",
        "version": "0.1.0",
        "category": "",
        "keywords": [],
    }
    if project_type == "skill":
        plugin["skills"] = ["./"]

    data = {
        "name": name,
        "owner": {"name": "", "email": ""},
        "metadata": {
            "description": "",
            "version": "0.1.0",
            "pluginRoot": "./",
        },
        "plugins": [plugin],
    }
    return json.dumps(data, indent=2) + "\n"


def _mcp_json(name: str, plugin: bool = False) -> str:
    """Generate .mcp.json content."""
    directory = "${CLAUDE_PLUGIN_ROOT}" if plugin else "."
    data = {
        "mcpServers": {
            name: {
                "command": "uv",
                "args": ["--directory", directory, "run", name],
            }
        }
    }
    return json.dumps(data, indent=2) + "\n"


def _test_file(name: str) -> str:
    """Generate placeholder test."""
    return 'def test_placeholder():\n    """Verify test infrastructure works."""\n    assert True\n'


def _write_marketplace_json(project_dir: Path, name: str, project_type: str) -> None:
    """Create marketplace.json for plugin-enabled projects."""
    plugin_dir = project_dir / ".claude-plugin"
    plugin_dir.mkdir(exist_ok=True)
    (plugin_dir / "marketplace.json").write_text(_marketplace_json(name, project_type))


# --- Core functions ---


def create_base(name: str, output_dir: Path) -> Path:
    """Create common project structure shared by all types."""
    project_dir = output_dir / name
    if project_dir.exists():
        raise FileExistsError(f"Directory already exists: {project_dir}")

    project_dir.mkdir(parents=True)

    # Directories (empty dirs get .gitkeep so git tracks them in worktrees/clones)
    for docs_dir in ("plans", "research", "reflections"):
        (project_dir / "docs" / docs_dir).mkdir(parents=True, exist_ok=True)
        (project_dir / "docs" / docs_dir / ".gitkeep").touch()
    (project_dir / "tests").mkdir()
    (project_dir / ".worktrees").mkdir()
    (project_dir / ".worktrees" / ".gitkeep").touch()
    (project_dir / ".claude" / "skills").mkdir(parents=True)

    # Documentation stubs (LLM fills these)
    (project_dir / "README.md").write_text(f"# {name}\n")
    (project_dir / "CHANGELOG.md").write_text("# Changelog\n")
    (project_dir / "DEVELOPMENT.md").write_text("# Development\n")
    (project_dir / "TESTING.md").write_text("# Testing\n")
    (project_dir / "TODO.md").write_text("# TODO\n")
    (project_dir / "ARCHITECTURE.md").write_text("# Architecture\n\n<!-- Update this document when the structure changes. -->\n")
    (project_dir / "LICENSE").write_text("")

    # CLAUDE.md with full persona template
    (project_dir / "CLAUDE.md").write_text(CLAUDE_MD)
    os.symlink("CLAUDE.md", project_dir / "AGENTS.md")

    # Config files
    (project_dir / ".gitignore").write_text(GITIGNORE)
    (project_dir / ".markdownlint.json").write_text(MARKDOWNLINT_JSON)
    (project_dir / ".pre-commit-config.yaml").write_text(PRE_COMMIT_CONFIG)
    (project_dir / ".claude" / "settings.json").write_text("{}\n")

    # pyproject.toml (base — type-specific functions append to it)
    (project_dir / "pyproject.toml").write_text(_pyproject_toml(name, "base"))

    # Tests
    pkg = to_pkg_name(name)
    (project_dir / "tests" / "conftest.py").write_text(CONFTEST)
    (project_dir / "tests" / f"test_{pkg}.py").write_text(_test_file(name))

    return project_dir


def create_skill(name: str, project_dir: Path, plugin: bool = True) -> None:
    """Add skill-specific files to project."""
    _ = plugin
    pkg = to_pkg_name(name)

    # Skill directories
    (project_dir / "scripts").mkdir()
    (project_dir / "subskills").mkdir()
    (project_dir / "subskills" / ".gitkeep").touch()
    (project_dir / pkg).mkdir(exist_ok=True)

    # SKILL.md
    title = name.replace("-", " ").title()
    (project_dir / "SKILL.md").write_text(SKILL_MD_TEMPLATE.format(name=name, title=title))

    # Stub script
    (project_dir / "scripts" / "10_example.py").write_text(STUB_SCRIPT)

    # Package init
    (project_dir / pkg / "__init__.py").write_text("")

    # Update pyproject.toml (skill type, no entry points)
    (project_dir / "pyproject.toml").write_text(_pyproject_toml(name, "skill"))

    # Skill projects are always Claude plugins.
    _write_marketplace_json(project_dir, name, "skill")


def create_mcp(name: str, project_dir: Path, plugin: bool = False) -> None:
    """Add MCP server-specific files to project."""
    pkg = to_pkg_name(name)

    (project_dir / pkg).mkdir(exist_ok=True)

    # .mcp.json
    (project_dir / ".mcp.json").write_text(_mcp_json(name, plugin))

    # Server template
    (project_dir / pkg / "server.py").write_text(SERVER_PY_TEMPLATE.format(name=name, pkg=pkg))

    # Package init with main export
    (project_dir / pkg / "__init__.py").write_text(MCP_INIT_TEMPLATE)

    # Update pyproject.toml with MCP deps and entry point
    (project_dir / "pyproject.toml").write_text(_pyproject_toml(name, "mcp"))

    if plugin:
        _write_marketplace_json(project_dir, name, "mcp")


def create_cli(name: str, project_dir: Path, plugin: bool = False) -> None:
    """Add CLI tool-specific files to project."""
    pkg = to_pkg_name(name)

    (project_dir / pkg).mkdir(exist_ok=True)

    # CLI template
    (project_dir / pkg / "cli.py").write_text(CLI_PY_TEMPLATE.format(name=name))

    # Package init with main export
    (project_dir / pkg / "__init__.py").write_text(CLI_INIT_TEMPLATE)

    # Update pyproject.toml with entry point
    (project_dir / "pyproject.toml").write_text(_pyproject_toml(name, "cli"))

    if plugin:
        _write_marketplace_json(project_dir, name, "cli")


def init_git(project_dir: Path) -> None:
    """Initialize git repo with initial commit."""
    subprocess.run(
        ["git", "init"],
        cwd=project_dir,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "add", "."],
        cwd=project_dir,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "Initial project structure"],
        cwd=project_dir,
        capture_output=True,
        check=True,
    )


def init_uv(project_dir: Path) -> None:
    """Run uv sync to set up virtual environment."""
    subprocess.run(
        ["uv", "sync"],
        cwd=project_dir,
        capture_output=True,
        check=True,
    )


def verify(project_dir: Path) -> dict:
    """Run pytest and ruff to verify project is valid."""
    results: dict = {"pytest": None, "ruff": None}

    pytest_result = subprocess.run(
        ["uv", "run", "pytest", "tests/", "-q"],
        cwd=project_dir,
        capture_output=True,
        text=True,
    )
    results["pytest"] = {
        "returncode": pytest_result.returncode,
        "output": pytest_result.stdout + pytest_result.stderr,
    }

    ruff_result = subprocess.run(
        ["ruff", "check", "."],
        cwd=project_dir,
        capture_output=True,
        text=True,
    )
    results["ruff"] = {
        "returncode": ruff_result.returncode,
        "output": ruff_result.stdout + ruff_result.stderr,
    }

    return results


def dry_run_report(name: str, project_type: str, plugin: bool = False) -> list[dict]:
    """Return list of files that would be created without creating them."""
    pkg = to_pkg_name(name)
    include_plugin = project_type == "skill" or plugin

    common = [
        {"path": "CLAUDE.md", "description": "LLM behavioral config"},
        {"path": "AGENTS.md", "description": "Symlink to CLAUDE.md"},
        {"path": "README.md", "description": "Project description"},
        {"path": "CHANGELOG.md", "description": "Version history"},
        {"path": "DEVELOPMENT.md", "description": "Dev setup"},
        {"path": "TESTING.md", "description": "Test guide"},
        {"path": "TODO.md", "description": "Task tracking"},
        {"path": "ARCHITECTURE.md", "description": "Architecture notes"},
        {"path": "LICENSE", "description": "License file"},
        {"path": ".gitignore", "description": "Git ignore rules"},
        {"path": ".markdownlint.json", "description": "Markdown lint config"},
        {"path": ".pre-commit-config.yaml", "description": "Pre-commit hooks"},
        {"path": ".claude/settings.json", "description": "Shared Claude settings"},
        {"path": ".claude/skills/", "description": "Local skill symlinks"},
        {"path": "pyproject.toml", "description": "Build + lint config"},
        {"path": "docs/plans/", "description": "Plans directory"},
        {"path": "docs/research/", "description": "Research notes"},
        {"path": "docs/reflections/", "description": "Implementation reflections"},
        {"path": "tests/conftest.py", "description": "Test fixtures"},
        {"path": f"tests/test_{pkg}.py", "description": "Placeholder test"},
        {"path": ".worktrees/", "description": "Git worktree directory"},
    ]
    if include_plugin:
        common.append({"path": ".claude-plugin/marketplace.json", "description": "Plugin marketplace entry"})

    type_specific: dict[str, list[dict]] = {
        "skill": [
            {"path": "SKILL.md", "description": "Skill definition"},
            {"path": "scripts/10_example.py", "description": "Stub script"},
            {"path": "subskills/", "description": "Conditional flows"},
            {"path": f"{pkg}/__init__.py", "description": "Python package"},
        ],
        "mcp": [
            {"path": ".mcp.json", "description": "MCP dev config"},
            {"path": f"{pkg}/__init__.py", "description": "Package with main()"},
            {"path": f"{pkg}/server.py", "description": "MCP server template"},
        ],
        "cli": [
            {"path": f"{pkg}/__init__.py", "description": "Package with main()"},
            {"path": f"{pkg}/cli.py", "description": "CLI scaffold"},
        ],
    }

    return common + type_specific.get(project_type, [])


CREATORS = {
    "skill": create_skill,
    "mcp": create_mcp,
    "cli": create_cli,
}


def main() -> None:
    """Parse arguments and create project."""
    parser = argparse.ArgumentParser(
        prog="build_project",
        description="Initialize project structure for skills, MCP servers, or CLI tools.",
    )
    parser.add_argument(
        "type",
        choices=["skill", "mcp", "cli"],
        help="Project type",
    )
    parser.add_argument(
        "name",
        help="Project name (kebab-case, e.g. my-tool)",
    )
    parser.add_argument(
        "output_dir",
        help="Parent directory for the project",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be created, create nothing",
    )
    parser.add_argument(
        "--plugin",
        action="store_true",
        help="Create Claude plugin scaffolding for mcp/cli projects",
    )

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(2)

    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    plugin = args.type == "skill" or args.plugin

    if args.dry_run:
        report = dry_run_report(args.name, args.type, plugin)
        print(json.dumps({"dry_run": True, "files": report}, indent=2))
        sys.exit(0)

    try:
        project_dir = create_base(args.name, output_dir)
        CREATORS[args.type](args.name, project_dir, plugin)
        init_git(project_dir)
        init_uv(project_dir)
        verification = verify(project_dir)

        result = {
            "project_dir": str(project_dir),
            "type": args.type,
            "name": args.name,
            "package": to_pkg_name(args.name),
            "files": [f["path"] for f in dry_run_report(args.name, args.type, plugin)],
            "verification": verification,
        }
        print(json.dumps(result, indent=2))

    except FileExistsError as e:
        print(json.dumps({"error": str(e), "suggestion": "Choose a different name or remove the existing directory."}), file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(
            json.dumps({"error": f"Command failed: {e.cmd}", "output": (e.stdout or b"").decode() + (e.stderr or b"").decode()}),
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
