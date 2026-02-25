---
name: session-gemini
description: Use when delegating a task to Gemini CLI with session persistence across turns.
allowed-tools:
  - Bash
---

# Gemini Session

## Direct (review, analysis, quick edits — no git)

First run:
```bash
gemini -p "${PROMPT}" -o json --approval-mode auto_edit
```

Following runs:
```bash
gemini -p "${PROMPT}" -o json --approval-mode auto_edit -r ${SESSION_ID}
```

## Worktree (implementation — sandboxed with git)

Claude prepares worktree, then launches Gemini:

1. `git worktree add .worktrees/${NAME} -b ${NAME} main`
2. Copy `.env*` files (incl. `GOOGLE_API_KEY`), run `uv sync` where needed

Select sandbox profile via env var. Git works natively — `.git` is not denied.

### Profiles

**code** — git, edit, tests. No network.
```bash
cd .worktrees/${NAME} && SEATBELT_PROFILE=permissive-closed gemini -p "${PROMPT}" -o json -s -y
```

**test** — code + localhost (dev servers, browser tests).
```bash
cd .worktrees/${NAME} && SEATBELT_PROFILE=permissive-open gemini -p "${PROMPT}" -o json -s -y
```

**e2e** — test + controlled network via proxy.
```bash
cd .worktrees/${NAME} && SEATBELT_PROFILE=permissive-proxied gemini -p "${PROMPT}" -o json -s -y
```

Following runs — append `-r ${SESSION_ID}`:
```bash
cd .worktrees/${NAME} && SEATBELT_PROFILE=permissive-closed gemini -p "${PROMPT}" -o json -s -y -r ${SESSION_ID}
```

### Additional writable directories

Use `--include-directories` for paths outside worktree (max 5):
```bash
gemini -p "${PROMPT}" -o json -s -y --include-directories /path/to/shared
```

## Response parsing

`-o json` returns single JSON: `{"session_id":"...","response":"...","stats":{...}}`.
`-o stream-json` streams JSONL events.

Parse `session_id` from response → set `${SESSION_ID}` for `-r` resume.

If error or empty output: show stderr, STOP.
Use Bash timeout >= 300000 for long-running tasks.

## Sandbox profiles (macOS Seatbelt)

| Profile | Writes | Reads | Network |
|---|---|---|---|
| `permissive-open` | Project dir + caches | All | Full |
| `permissive-closed` | Project dir + caches | All | None |
| `permissive-proxied` | Project dir + caches | All | Via proxy |
| `restrictive-open` | Project dir | Project dir | Full |
| `restrictive-closed` | Project dir | Project dir | None |

Custom profiles: `.gemini/sandbox-macos-<name>.sb` in project dir.
Container sandbox (Docker/Podman): set `GEMINI_SANDBOX=docker` or `podman`.
