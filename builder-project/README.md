# project-builder

Project scaffolding skill for creating new skill, MCP server, or CLI tool projects. Front-loads deterministic dev infrastructure so builder skills can focus on domain logic.

## What it does

1. Asks discovery questions (type, license, optional plugin, output directory, problem, capabilities)
2. Runs `build_project.py` to create the full directory structure with configs, tests, and git
3. Fills template files (README, CLAUDE.md, CHANGELOG, TODO, ARCHITECTURE, etc.) using discovery answers
4. Optionally links sibling skills into `.claude/skills/` as local relative symlinks

## Usage

### As a skill

Invoke the `project-builder` skill in Claude Code. It walks through discovery and scaffolding.

### Script directly

```bash
# Create a skill project
python3 project-builder/project_builder/build_project.py skill my-skill /path/to/output

# Create a standalone MCP server project
python3 project-builder/project_builder/build_project.py mcp my-mcp /path/to/output

# Create a plugin-enabled MCP server project
python3 project-builder/project_builder/build_project.py mcp my-mcp /path/to/output --plugin

# Create a standalone CLI tool project
python3 project-builder/project_builder/build_project.py cli my-cli /path/to/output

# Create a plugin-enabled CLI tool project
python3 project-builder/project_builder/build_project.py cli my-cli /path/to/output --plugin

# Preview without creating
python3 project-builder/project_builder/build_project.py --dry-run skill my-skill /path/to/output
```

### Exit codes

- 0: Success
- 1: Error (with suggestion)
- 2: Usage error (shows help)

## Generated structure

All types get: pyproject.toml (hatchling + ruff), pytest, pre-commit hooks, CLAUDE.md, TODO.md, ARCHITECTURE.md, `.claude/settings.json`, `.claude/skills/`, `docs/plans/`, `docs/research/`, `docs/reflections/`, git repo, `.worktrees/`.

Plugin scaffold is conditional:
- `skill` always gets `.claude-plugin/marketplace.json`
- `mcp` and `cli` only get `.claude-plugin/marketplace.json` when `--plugin` is passed

Type-specific additions:

- **Skill**: SKILL.md, scripts/, subskills/, Python package
- **MCP**: .mcp.json, server.py (FastMCP dispatcher), Python package with main()
- **CLI**: cli.py (argparse scaffold), Python package with main()

## Development

```bash
cd project-builder
uv sync
uv run pytest tests/project-builder/ -q
ruff check project-builder/
```
