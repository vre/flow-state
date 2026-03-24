---
name: session-sandvault
description: Use when delegating a task to an agent inside Sandvault macOS sandbox. Returns agent output (JSONL/JSON) for parsing.
allowed-tools:
  - Bash
---

# Sandvault Session

Like session-claude / session-codex but inside Sandvault sandbox. `sv` handles isolation and permission flags. Sandbox user is a different macOS user with a different home — files move via shared bare git repo.

## Variables

- `${SHARED}` — `/Users/Shared/sv-${USER}`
- `${REPO}` — bare repo name in shared space (e.g., `myproject.git`)
- `${PROJECT_DIR}` — `${REPO%.git}` (e.g., `myproject`) — compute once to avoid nested quoting issues
- `${NAME}` — branch/worktree name
- `${PROMPT}` — task prompt
- `${THREAD_ID}` — Codex session ID (for resume)

## Prerequisites

User must have:
1. Sandvault installed and built (`sv build`)
2. Logged into Claude and Codex inside `sv shell` (one-time)
3. After brew upgrade of Claude/Codex: run once on host first to accept update prompts

If `sv shell -- echo ok` fails → STOP, tell user to set up Sandvault.

## Environment check

When setting up a project for sandbox use, verify the sandbox has the project's toolchain. Do not assume — check:
```bash
sv shell -- zsh -c "which <tool> && <tool> --version"
```

Examples:
- Android: `java`, `gradle`, `adb`, `JAVA_HOME`, `ANDROID_HOME`
- Python: `python3`, `uv`, `VIRTUAL_ENV`
- Node: `node`, `npm`/`bun`, `npx`
- Rust: `cargo`, `rustc`

If a required tool is missing → install via brew on host (sandbox shares `/opt/homebrew/bin`). If env vars are missing → copy the relevant exports from host's `~/.zprofile` to sandbox's `~/user/.zprofile` via `sv shell`.

## Sync setup

Sandbox user cannot write host user's files. Shared bare repo bridges the gap.

### If CWD is a git repo

Check if shared remote exists:
```bash
git remote get-url shared 2>/dev/null
```

If no shared remote → create the bridge. Compute `${PROJECT_DIR}` (repo name without `.git`) first to avoid nested quoting issues:
```bash
PROJECT_DIR="${REPO%.git}"
git clone --bare "$(pwd)" "${SHARED}/${REPO}"
git -C "${SHARED}/${REPO}" config core.sharedRepository group
chgrp -R "sandvault-${USER}" "${SHARED}/${REPO}"
chmod -R g+w "${SHARED}/${REPO}"
git remote add shared "${SHARED}/${REPO}"
sv shell -- zsh -c "git config --global --add safe.directory ${SHARED}/${REPO} && git config --global --add safe.directory ${SHARED}/${PROJECT_DIR}"
```

Push current branch:
```bash
git push shared ${NAME}
```

Sandbox user clones (first time) or fetches:
```bash
sv shell -- zsh -c "cd ${SHARED} && { [ -d ${PROJECT_DIR} ] && cd ${PROJECT_DIR} && git fetch || git clone ${REPO} && cd ${PROJECT_DIR}; }"
```

### If CWD is not a git repo

Copy to shared space:
```bash
rsync -a --exclude node_modules --exclude .git "$(pwd)/" "${SHARED}/$(basename "$(pwd)")/"
```

Sandbox works on the copy. Results must be rsynced back manually.

## Delegate to Codex

Pass prompt via stdin (`-`) to avoid shell quoting issues. Use `sv shell PATH --` (not `sv codex --` which does not support `exec` subcommand).

First run:
```bash
echo "${PROMPT}" | sv shell "${SHARED}/${PROJECT_DIR}" -- codex exec --json -
```

Resume:
```bash
echo "${PROMPT}" | sv shell "${SHARED}/${PROJECT_DIR}" -- codex exec resume --json ${THREAD_ID} -
```

## Delegate to Claude

First run:
```bash
echo "${PROMPT}" | sv shell "${SHARED}/${PROJECT_DIR}" -- claude -p --output-format json
```

Resume (`-c` continues most recent in cwd):
```bash
echo "${PROMPT}" | sv shell "${SHARED}/${PROJECT_DIR}" -- claude -p -c --output-format json
```

## Get results back

After agent finishes, push from sandbox and fetch on host:
```bash
sv shell -- zsh -c "cd ${SHARED}/${PROJECT_DIR} && git push origin ${NAME}"
git fetch shared
git log shared/${NAME} --oneline -5
```

Merge or cherry-pick as needed.

## Parse response

Codex: first JSONL line `{"type":"thread.started","thread_id":"<id>"}` → set `${THREAD_ID}`. Messages: `item.type == "agent_message"` → `item.text`.

Claude: JSON `{"type":"result","result":"...","session_id":"..."}`.

If error or empty output → show stderr, STOP.
Bash timeout >= 300000.
