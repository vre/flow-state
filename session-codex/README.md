# Session Codex Skill

Delegates tasks to OpenAI Codex CLI with session persistence. Two modes: direct (review/analysis) and worktree (implementation with sandboxed git).

## The problem

`codex exec --json` runs non-interactively — no terminal for approval prompts. `--full-auto` mode creates two conflicts:

1. **Approvals can hang**: `--full-auto` uses `approval_policy="on-request"`, prompts that nobody can answer. Observed with `rg` in practice.
2. **Git is blocked**: `--full-auto` uses `-s workspace-write`, restricting to cwd file operations. Codex hardcodes `.git` as read-only in all sandbox modes except `danger-full-access`.

## The solution: `.git` rename + `workspace-write`

Only for worktrees where `.git` is a gitfile (pointer). Do not apply to repo root where `.git` is a directory.

Codex's denylist checks literal path names: `.git`, `.codex`, `.agents`. Renaming the gitfile to `.git-codex-sandbox-workaround` bypasses the denylist while keeping kernel-enforced sandbox restrictions.

Setup:
```bash
git worktree add .worktrees/${NAME} -b ${NAME} main
# Exclude workaround file from git add
printf '.git-codex-sandbox-workaround\n' >> "$(git -C .worktrees/${NAME} rev-parse --git-path info/exclude)"
# Rename gitfile
mv .worktrees/${NAME}/.git .worktrees/${NAME}/.git-codex-sandbox-workaround
printf 'gitdir: .git-codex-sandbox-workaround\n' > .worktrees/${NAME}/.git
```

### Why GIT_DIR= prefix is required

In a worktree, `.git` is a gitfile containing `gitdir: /abs/path/.git/worktrees/NAME`. After rename, there are two `gitdir:` hops:
1. `.git` → `gitdir: .git-codex-sandbox-workaround`
2. `.git-codex-sandbox-workaround` → `gitdir: /abs/path/.git/worktrees/NAME`

Git does not follow two levels of `gitdir:` — plain `git` commands fail with "not a git repository".

`GIT_DIR=.git-codex-sandbox-workaround` skips the first hop. Git reads the file, follows one `gitdir:` to the real git data. All git operations work with this prefix.

**Constraints**: The relative `GIT_DIR` path only works from the worktree root. From nested directories, use absolute paths with `GIT_WORK_TREE`. Never use `git add .` or `git add -A` — use explicit paths or `git add -u`.

**Every Codex prompt must include the GIT_DIR instruction** — see SKILL.md for the exact prompt prefix block.

**Tested**: `git status`, `git add <path>`, `git add -u`, `git commit`, `git log`, `git diff` all succeed under `workspace-write` sandbox with `GIT_DIR=.git-codex-sandbox-workaround` prefix.

## Modes

### Direct (`--full-auto`)

For review, analysis, quick edits. Sandbox restricts to cwd + subdirs, no git. Known issue: may hang on commands outside sandbox boundary.

### Worktree (`-s workspace-write` + `.git` rename)

For writing code, running tests, committing. Kernel-enforced sandbox restricts writes to CWD + subdirs. Network blocked. Git works via renamed directory.

Every prompt must instruct Codex: `GIT_DIR=.git-codex-sandbox-workaround` before all git commands. Never `git add .` / `git add -A`.

## Security comparison

| | session-codex (old) | session-codex (new) | session-claude |
|---|---|---|---|
| Sandbox mode | `danger-full-access` | `workspace-write` | Kernel sandbox |
| Filesystem | Entire machine | CWD + subdirs only | CWD (repo root in practice) |
| Network | Unrestricted | Blocked | Configurable (profiles) |
| Git | Works (no sandbox) | Works (rename workaround) | Works (natively) |
| Mechanism | None | Seatbelt/Landlock | Seatbelt/bubblewrap |

## Background: Codex CLI flags

Sandbox levels (`-s` on `exec` only, not `resume`):

- `read-only`: no writes
- `workspace-write`: cwd tree only, network blocked, `.git`/`.codex`/`.agents` hardcoded read-only
- `danger-full-access`: no restrictions

Approval policies (config key `approval_policy`, set via `-c`):

- `untrusted`: only pre-approved commands
- `on-request`: asks before running (`--full-auto` default)
- `on-failure`: asks on failure (deprecated)
- `never`: no prompts

`--full-auto` = `-s workspace-write` + `approval_policy="on-request"`.

`resume` inherits sandbox mode and working directory from the session. Only `approval_policy` needs override via `-c`.

## Why this works

Codex's Seatbelt profile (macOS) generates:
```scheme
(allow file-write*
  (require-all
    (subpath (param "WRITABLE_ROOT_0"))
    (require-not (subpath (param "WRITABLE_ROOT_0_RO_0")))  ; .git
    (require-not (subpath (param "WRITABLE_ROOT_0_RO_1")))  ; .codex
  ))
```

The `require-not` matches `.git` literally. `.git-codex-sandbox-workaround` does not match. The Landlock equivalent on Linux uses the same path-based denylist.
