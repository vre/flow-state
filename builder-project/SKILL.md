---
name: project-builder
description: Use when creating a new skill, MCP server, or CLI tool project.
keywords: project, scaffold, init, generator, python
allowed-tools:
  - Bash
  - Read
  - Write
  - AskUserQuestion
---

# Project Builder

## Step 0: Challenge

Before scaffolding, research and challenge:

1. What tools/APIs already exist in this domain? Check installed CLIs, existing skills, MCP servers.
2. Does this need code, or does a SKILL.md with raw commands suffice?
3. What's the minimum that solves the actual problem?

Present findings to user with recommendation. If no scaffold needed → suggest alternative, STOP.

## Step 1: Discovery

AskUserQuestion (single call, two questions):

1. question: "What type of project?" header: "Type" options: Skill, MCP server, CLI tool
2. question: "Which license?" header: "License" options: MIT (Recommended), Apache 2.0

Then ask conversationally, one at a time:

1. "What should the project be called? Use kebab-case, e.g. `my-tool`."
2. "In one sentence, what problem does this solve?"
3. "What are the 2-3 key things it should do?"

Set `${TYPE}` = skill|mcp|cli, `${NAME}`, `${LICENSE}`, `${PROBLEM}`, `${CAPABILITIES}`.

## Step 2: Create project structure

```bash
python3 ./project-builder/project_builder/build_project.py ${TYPE} ${NAME} <output_dir>
```

Creates: full directory tree with template files, git repo, verified tests + lint.

If script exits non-zero: show error output, `STOP`.

## Step 3: Fill template files

Using discovery answers, fill: README.md, DEVELOPMENT.md, TESTING.md, CHANGELOG.md, LICENSE, marketplace.json, CLAUDE.md (`## Tech Stack` + `## Project Structure`). Type-specific: SKILL.md stub / server.py docstring / cli.py help.

## Done

Show tree. Suggest: invoke skill-builder / mcp-builder / cli-tool-builder next.
