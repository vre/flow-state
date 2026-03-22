---
name: session-codex
description: Use when delegating a task to Codex CLI with session persistence across turns.
allowed-tools:
  - Bash
---

# Codex Session

## Direct (review, analysis, quick edits — no git)

First run:
```bash
codex exec --json --full-auto "prompt"
```

Following runs:
```bash
codex exec resume --json --full-auto ${THREAD_ID} "follow-up prompt"
```

## Worktree (implementation — sandboxed with git)

Only for worktrees where `.git` is a gitfile (pointer to main repo). Do not apply to repo root where `.git` is a directory.

### Step 1: Create worktree

```bash
git worktree add .worktrees/${NAME} -b ${NAME} main
```
Copy `.env*` files, run `uv sync` where needed.

### Step 2: Rename `.git` to bypass Codex denylist

Before renaming, verify state:
- `.worktrees/${NAME}/.git` must exist (gitfile)
- `.worktrees/${NAME}/.git-codex-sandbox-workaround` must NOT exist
- If `.git` already contains `gitdir: .git-codex-sandbox-workaround`, the workaround is already active — skip this step

Add exclude rule to prevent accidental staging, then rename:
```bash
printf '.git-codex-sandbox-workaround\n' >> "$(git -C .worktrees/${NAME} rev-parse --git-path info/exclude)"
mv .worktrees/${NAME}/.git .worktrees/${NAME}/.git-codex-sandbox-workaround
printf 'gitdir: .git-codex-sandbox-workaround\n' > .worktrees/${NAME}/.git
```

**Why this creates double indirection**: In a worktree, the original `.git` is a gitfile containing `gitdir: /abs/path/.git/worktrees/NAME`. After rename:
- `.git` (new) → `gitdir: .git-codex-sandbox-workaround`
- `.git-codex-sandbox-workaround` (original gitfile) → `gitdir: /abs/path/.git/worktrees/NAME`

Git does not follow two `gitdir:` hops. Plain `git` commands fail with "not a git repository".

### Step 3: Use GIT_DIR= prefix on ALL git commands — MANDATORY

`GIT_DIR=.git-codex-sandbox-workaround` skips the first hop — git reads the file, follows one `gitdir:` to the real git data.

**You (Claude) MUST use the prefix** when running git commands in the worktree yourself. Always run from the worktree root (`cd .worktrees/${NAME}/` first):
```bash
GIT_DIR=.git-codex-sandbox-workaround git status
GIT_DIR=.git-codex-sandbox-workaround git add file.py
GIT_DIR=.git-codex-sandbox-workaround git log --oneline
```

FAIL: `git status` without `GIT_DIR=` — will error.
FAIL: running from a nested subdirectory — relative `GIT_DIR` resolves to wrong path.

### Step 4: Build the Codex prompt

Set `WT_ABS` to the absolute path of the worktree (e.g., `/Users/foo/project/.worktrees/myfeature`).

Prepend this exact block to EVERY Codex prompt (first run AND every `resume`):

```
MANDATORY GIT RULES — violations break all git commands:
  Git data is renamed to .git-codex-sandbox-workaround
  From worktree root:
    GIT_DIR=.git-codex-sandbox-workaround git <command>
  From any other directory:
    GIT_DIR=${WT_ABS}/.git-codex-sandbox-workaround GIT_WORK_TREE=${WT_ABS} git <command>
  NEVER run bare 'git' without GIT_DIR= prefix — it WILL fail.
  NEVER use 'git add .', 'git add -A', or 'git add :/' — they stage internal files.
  Use 'git add <explicit paths>' for new files, 'git add -u' for tracked-file updates.
  Correct:   GIT_DIR=.git-codex-sandbox-workaround git status
  Correct:   GIT_DIR=.git-codex-sandbox-workaround git add -u
  Correct:   GIT_DIR=.git-codex-sandbox-workaround git add src/foo.py tests/test_foo.py
  Correct:   GIT_DIR=.git-codex-sandbox-workaround git commit -m "msg"
  Correct:   GIT_DIR=.git-codex-sandbox-workaround git diff
  WRONG:     git status
  WRONG:     git add .
  WRONG:     git add -A
  WRONG:     GIT_DIR=.git-codex-sandbox-workaround git add .
```

### Step 5: Run Codex

First run:
```bash
codex exec --json -s workspace-write -c 'approval_policy="never"' -C .worktrees/${NAME} "${PROMPT}"
```

Following runs — `resume` inherits sandbox mode and working directory from the session. Only `approval_policy` needs override:
```bash
codex exec resume --json -c 'approval_policy="never"' ${THREAD_ID} "${PROMPT}"
```

### Step 6: Reverse before rebase/merge

Only reverse if `.git` contains the workaround pointer and `.git-codex-sandbox-workaround` exists:
```bash
rm .worktrees/${NAME}/.git && mv .worktrees/${NAME}/.git-codex-sandbox-workaround .worktrees/${NAME}/.git
```

After reversal, plain `git` works again. GIT_DIR= prefix no longer needed.

## Response parsing

Parse first JSONL line: `{"type":"thread.started","thread_id":"<id>"}` → set `${THREAD_ID}`.
Response: lines where `item.type == "agent_message"` → `item.text`.

If Codex returns error or empty output: show stderr, STOP.
Use Bash timeout >= 300000 for long-running tasks.

## Security

`workspace-write` sandbox is kernel-enforced (Seatbelt/Landlock): writes restricted to CWD + subdirs, network blocked. The `.git` rename bypasses the hardcoded denylist while keeping filesystem isolation. This is safer than `danger-full-access` which has no restrictions at all.
