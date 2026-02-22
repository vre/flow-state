---
name: project-builder
description: Use when user wants to create a new skill, MCP server, or CLI tool project. Creates full project scaffold with dev infrastructure.
keywords: project, scaffold, init, generator, python
allowed-tools:
  - Bash
  - Read
  - Write
  - AskUserQuestion
---

# Project Builder

## Step 0: Discovery

AskUserQuestion (single call, two questions):

1. question: "What type of project?" header: "Type" options: Skill, MCP server, CLI tool
2. question: "Which license?" header: "License" options: MIT (Recommended), Apache 2.0

Then ask conversationally, one at a time:

1. "What should the project be called? Use kebab-case, e.g. `my-tool`."
2. "In one sentence, what problem does this solve?"
3. "What are the 2-3 key things it should do?"

Set `${TYPE}` = skill|mcp|cli, `${NAME}`, `${LICENSE}`, `${PROBLEM}`, `${CAPABILITIES}`.

## Step 1: Create project structure

```bash
python3 ./project-builder/project_builder/build_project.py ${TYPE} ${NAME} <output_dir>
```

Creates: full directory tree with template files, git repo, verified tests + lint.

If script exits non-zero: show error output, `STOP`.

## Step 2: Fill template files

Using discovery answers, write content into the created project's files:

- README.md: purpose from `${PROBLEM}`, features from `${CAPABILITIES}`, basic usage
- DEVELOPMENT.md: setup with `uv`, running tests, linting
- TESTING.md: test structure, running tests
- CHANGELOG.md: initial 0.1.0 entry
- LICENSE: `${LICENSE}` text
- marketplace.json: description, keywords from `${CAPABILITIES}`
- CLAUDE.md: append `## Tech Stack` and `## Project Structure` sections
- Type-specific: SKILL.md: leave as stub -- skill-builder fills this / server.py docstring / cli.py help text

## Done

Show created files tree. Suggest: invoke skill-builder / mcp-builder / cli-tool-builder to write first failing domain test.
