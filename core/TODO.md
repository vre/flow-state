# TODO

## Process & Tooling

- [ ] `/design` skill — collaborative UI/UX exploration: propose >2 non-functional HTML mockups, ask human about aspects to explore, suggest own ideas, iterate together before committing to a direction
- [ ] Plan templates — let plans accumulate organically, then derive small/standard templates from real patterns
- [ ] Review handoff automation — wrapper scripts (`message_a.py`, `message_b.py`) for the two-agent letterbox pattern (see `docs/core/research/2026-02-10-two-agent-development-automation.md`)
- [ ] Worktree setup script — copy `.env*` files from main (any directory level), run `uv sync` in dirs with pyproject.toml

## New Plugins

- [/] `project-builder` — scaffolds new projects (worktree: `.worktrees/builders/`)
- [/] `skill-builder` — scaffolds new skills (worktree: `.worktrees/builders/`)
- [/] `mcp-builder` — scaffolds new MCP servers (worktree: `.worktrees/builders/`)
- [/] `cli-tool-builder` — scaffolds new CLI tools (worktree: `.worktrees/builders/`)
