# Session Codex Skill

Delegates tasks to OpenAI Codex CLI with session persistence. Two modes: direct (review/analysis) and worktree (implementation with sandboxed git).

## The problem

`codex exec --json` runs non-interactively — no terminal for approval prompts. `--full-auto` mode creates two conflicts:

1. **Approvals can hang**: `--full-auto` uses `approval_policy="on-request"`, prompts that nobody can answer. Observed with `rg` in practice.
2. **Git is blocked**: `--full-auto` uses `-s workspace-write`, restricting to cwd file operations. Codex hardcodes `.git` as read-only in all sandbox modes except `danger-full-access`.

## The solution: `.git` rename + `workspace-write`

Codex's denylist checks literal path names: `.git`, `.codex`, `.agents`. Renaming the git directory to `.git-codex-sandbox-workaround` bypasses the denylist while keeping kernel-enforced sandbox restrictions.

Setup:
```bash
git worktree add .worktrees/${NAME} -b ${NAME} main
mv .worktrees/${NAME}/.git .worktrees/${NAME}/.git-codex-sandbox-workaround
printf 'gitdir: .git-codex-sandbox-workaround\n' > .worktrees/${NAME}/.git
```

Git reads the `.git` pointer file, resolves to `.git-codex-sandbox-workaround`, and operates normally. Codex's sandbox allows writes to `.git-codex-sandbox-workaround` because it's not in the denylist.

**Tested**: `git status`, `git add`, `git commit` all succeed under `workspace-write` sandbox with this rename.

## Modes

### Direct (`--full-auto`)

For review, analysis, quick edits. Sandbox restricts to cwd + subdirs, no git. Known issue: may hang on commands outside sandbox boundary.

### Worktree (`-s workspace-write` + `.git` rename)

For writing code, running tests, committing. Kernel-enforced sandbox restricts writes to CWD + subdirs. Network blocked. Git works via renamed directory.

Every prompt must instruct Codex: `GIT_DIR=.git-codex-sandbox-workaround` before all git commands.

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

`resume` does not support `-s` or `-C` — use `-c` config overrides. Working directory inherited from session.

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
