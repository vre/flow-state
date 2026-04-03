---
name: session-claude
description: Use when delegating a task to Claude Code CLI with session persistence across turns.
allowed-tools:
  - Bash
---

# Claude Session

Launch nested Claude via `unset CLAUDECODE &&` prefix — required to bypass nesting guard.
Pipe prompt via stdin — avoids shell quoting issues.

## Direct (review, analysis, quick edits — no git)

First run:
```bash
unset CLAUDECODE && echo "${PROMPT}" | claude -p --output-format json --permission-mode acceptEdits
```

Following runs (`-c` continues most recent conversation in cwd):
```bash
unset CLAUDECODE && echo "${PROMPT}" | claude -p -c --output-format json --permission-mode acceptEdits
```

Resume specific session:
```bash
unset CLAUDECODE && echo "${PROMPT}" | claude -p -r ${SESSION_ID} --output-format json
```

## Worktree (implementation — sandboxed, full git)

Claude prepares worktree, then launches nested Claude:

1. `git worktree add .worktrees/${NAME} -b ${NAME} main`
2. Copy `.env*` files, run `uv sync` where needed

Build the command from base + profile settings:

```bash
cd .worktrees/${NAME} && unset CLAUDECODE && echo "${PROMPT}" | claude -p --output-format json --settings '${SETTINGS_JSON}' --permission-mode dontAsk --allowedTools "Read" "Edit" "Write" "Glob" "Grep" "Bash"
```

Resume: append `-c` (most recent in worktree dir) or `-r ${SESSION_ID}`.

### Settings profiles

**code** — git, edit, test pure functions. No network.
```json
{"sandbox":{"enabled":true,"autoAllowBashIfSandboxed":true,"allowUnsandboxedCommands":false}}
```

**test** — code + localhost servers (dev server, browser tests, playwright).
```json
{"sandbox":{"enabled":true,"autoAllowBashIfSandboxed":true,"allowUnsandboxedCommands":false,"network":{"allowLocalBinding":true}}}
```

**e2e** — test + external domains (APIs, package registries).
```json
{"sandbox":{"enabled":true,"autoAllowBashIfSandboxed":true,"allowUnsandboxedCommands":false,"network":{"allowLocalBinding":true,"allowedDomains":["github.com","*.pypi.org","*.npmjs.org"]}}}
```

Choose profile matching the task. `autoAllowBashIfSandboxed` allows ALL Bash within sandbox — no need to whitelist individual commands.

## Response parsing

`--output-format json` → single JSON: `{"type":"result","result":"...","session_id":"..."}`.
`--output-format stream-json` → JSONL events (use for progress visibility).

Parse `session_id` from response → set `${SESSION_ID}` for `-r` resume.

If error or empty output: show stderr, STOP.
Use Bash timeout >= 300000 for long-running tasks.

## Sandbox boundary

Sandbox = **git repo root**, not CWD. Writes anywhere in repo OK, outside repo blocked (kernel-enforced). Git works because `.git/worktrees/` is inside repo.
