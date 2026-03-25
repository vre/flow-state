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
- `${SV_REPO}` — sandbox working copy: `~/repositories/${PROJECT_DIR}`
- `${NAME}` — branch/worktree name
- `${PROMPT}` — task prompt
- `${THREAD_ID}` — Codex session ID (for resume)

## Git remote naming

- Host: remote `sandvault` → `${SHARED}/${REPO}` (bare repo bridge)
- Host: remote `origin` → upstream (GitHub etc.)
- Sandbox: remote `origin` → `${SHARED}/${REPO}` (natural — it's where clone came from)

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
- Android: `java`, `gradle`, `adb`, `JAVA_HOME`, `ANDROID_HOME`. SDK managed via `sdkmanager` on host → `/opt/homebrew/share/android-commandlinetools/`, visible to both users. Emulator runs on host (needs GUI), sandbox agent connects via `adb` over localhost.
- Python: `python3`, `uv`, `VIRTUAL_ENV`
- Node: `node`, `npm`/`bun`, `npx`
- Rust: `cargo`, `rustc`

If a required tool is missing → install via brew on host (sandbox shares `/opt/homebrew/bin`). SDK components (e.g., `sdkmanager "platforms;android-34"`) also install to the shared brew prefix — but sandbox can't install them itself (no write access to brew dir), so install on host. If build tools complain about missing SDK components → install them on host, not sandbox.

If env vars are missing → copy the relevant exports from host's profile to sandbox's `~/user/.zprofile`. For multi-line or complex setup, write a script to shared space to avoid quoting issues:
```bash
cat > ${SHARED}/setup-env.sh << 'EOF'
#!/bin/zsh
echo 'export JAVA_HOME=/opt/homebrew/opt/openjdk@17' >> ~/user/.zprofile
echo 'export ANDROID_HOME=/opt/homebrew/share/android-commandlinetools' >> ~/user/.zprofile
EOF
chmod +x ${SHARED}/setup-env.sh
sv shell -- ${SHARED}/setup-env.sh
```

## Sync setup

Sandbox user cannot write host user's files. Shared bare repo bridges the gap.

### If CWD is a git repo

Check if shared remote exists:
```bash
git remote get-url sandvault 2>/dev/null
```

If no shared remote → create the bridge. Compute `${PROJECT_DIR}` (repo name without `.git`) first to avoid nested quoting issues:
```bash
PROJECT_DIR="${REPO%.git}"
git clone --bare "$(pwd)" "${SHARED}/${REPO}"
git -C "${SHARED}/${REPO}" config core.sharedRepository group
chgrp -R "sandvault-${USER}" "${SHARED}/${REPO}"
chmod -R g+w "${SHARED}/${REPO}"
git remote add sandvault "${SHARED}/${REPO}"
sv shell -- zsh -c "git config --global --add safe.directory ${SHARED}/${REPO} && git config --global --add safe.directory ~/repositories/${PROJECT_DIR}"
```

Push current branch:
```bash
git push sandvault ${NAME}
```

Sandbox user clones to `~/repositories/` (first time) or fetches:
```bash
sv shell -- zsh -c "mkdir -p ~/repositories && cd ~/repositories && { [ -d ${PROJECT_DIR} ] && cd ${PROJECT_DIR} && git fetch || git clone ${SHARED}/${REPO} ${PROJECT_DIR} && cd ${PROJECT_DIR}; }"
```

After clone/fetch, install project dependencies inside sandbox (e.g., `npm install`, `uv sync`).

### Shell quoting

`sv shell -- zsh -c "..."` breaks easily with quotes, dollars, semicolons. For anything beyond simple commands, write a script to shared space:
```bash
cat > ${SHARED}/task.sh << 'SCRIPT'
#!/bin/zsh
cd /Users/Shared/sv-vre/myproject
npm install
npx expo prebuild
SCRIPT
chmod +x ${SHARED}/task.sh
sv shell -- ${SHARED}/task.sh
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
echo "${PROMPT}" | sv shell "~/repositories/${PROJECT_DIR}" -- codex exec --json -
```

Resume:
```bash
echo "${PROMPT}" | sv shell "~/repositories/${PROJECT_DIR}" -- codex exec resume --json ${THREAD_ID} -
```

## Delegate to Claude

First run:
```bash
echo "${PROMPT}" | sv shell "~/repositories/${PROJECT_DIR}" -- claude -p --output-format json
```

Resume (`-c` continues most recent in cwd):
```bash
echo "${PROMPT}" | sv shell "~/repositories/${PROJECT_DIR}" -- claude -p -c --output-format json
```

## Get results back

After agent finishes, push from sandbox and fetch on host:
```bash
sv shell -- zsh -c "cd ~/repositories/${PROJECT_DIR} && git push origin ${NAME}"
git fetch sandvault
git log sandvault/${NAME} --oneline -5
```

Merge or cherry-pick as needed.

## Parse response

Codex: first JSONL line `{"type":"thread.started","thread_id":"<id>"}` → set `${THREAD_ID}`. Messages: `item.type == "agent_message"` → `item.text`.

Claude: JSON `{"type":"result","result":"...","session_id":"..."}`.

If error or empty output → show stderr, STOP.
Bash timeout >= 300000.
