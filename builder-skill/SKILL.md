---
name: building-skills
description: Use when creating new skills or converting workflows into SKILL.md
keywords: skill, SKILL.md, workflow
allowed-tools:
  - Bash
  - Read
  - Write
  - Task
  - AskUserQuestion
---

# Building Skills

## Step 0: Gate

Single command ≤2 flags, no pipes → "Could be: `{cmd}`. Need a skill?" If no → STOP.

## Step 1: Route

- New skill → Read and follow `./subskills/skill_only.md`
- Builder skill (scripts/templates/tests) → `./subskills/builder_skill.md`
- Bottling session → Document workflow first, then `./subskills/skill_only.md`
- From historian → Needs `mcp__claude-historian-mcp__*`. Missing → STOP.

## Step 2: Validate

```bash
python3 ./scripts/validate_structure.py <SKILL.md path>
```

Fix issues → re-validate. DONE.
