# Process Improvements from Cycle Reflections

## Problem

Two completed cycles (imap-stream-mcp v0.7.0, youtube-to-markdown v2.12.0) surfaced recurring process issues in CLAUDE.md. These need to be addressed as a batch to avoid ad-hoc main edits.

**Sources:**
- `docs/imap-stream-mcp/reflections/2026-03-03-cycle-snippet-preview.md`
- `docs/youtube-to-markdown/reflections/2026-03-07-cycle-long-transcript-fix.md`
- `docs/core/research/2026-02-25-agent-sandbox-session-delegation.md`
- HC feedback (2026-03-07 session)

## Changes

### 1. Merge: resolve conflicts in worktree, not during merge

**Evidence:** Both cycles hit rebase failures during Merge Phase. v0.7.0: diverged remote roots (reflection L31). v2.12.0: worktree branched from old fork point, rebase hit conflicts across 100+ skipped commits — aborted, squash merged directly (reflection L20).

**Current text (L94):**
> In worktree: `git pull --rebase origin main`. Test and validate after each rebase step. If conflicts: validate that existing functionality from main was not broken.

**New text:**
> In worktree: `git pull --rebase origin main`. Resolve all conflicts in worktree. Test and validate after each rebase step — merge step on main must be clean.

**Rationale:** Main can advance between review and merge, so rebase is still needed. If main moves after worktree rebase, rebase again. The key principle: all conflict resolution happens in the worktree. The `git merge --squash` on main should always be conflict-free.

### 2. Codex sandbox `.git` workaround in worktree setup

**Evidence:** Both cycles: Codex can't commit in sandbox (`.git` read-only). v0.7.0: `index.lock`. v2.12.0: `.git` metadata outside writable roots. Manual commits after each Codex run every time.

**Research (proven):** `docs/core/research/2026-02-25-agent-sandbox-session-delegation.md` L109-121:
```bash
mv .git .git-codex-sandbox-workaround
printf 'gitdir: .git-codex-sandbox-workaround\n' > .git
```
Tested: `git status`, `git add`, `git commit` all succeed under `workspace-write` sandbox.

**Add to IMPLEMENTATION SETUP (after worktree setup line):**
> Codex sandbox git workaround: in worktree, `mv .git .git-codex-sandbox-workaround && printf 'gitdir: .git-codex-sandbox-workaround\n' > .git` — enables git inside Codex `workspace-write` sandbox. Reverse before rebase/merge: `rm .git && mv .git-codex-sandbox-workaround .git`.

### 3. Reflection ownership: ORC delegates, agents write

**Evidence:** HC feedback: planning reflection should be written by the planning reviewer (Codex session — it has the planning context). Cycle reflection should be written by the implementing agent (IMP — it has the implementation context). ORC delegates, does not write either.

**Current (PLANNING END):**
> Write `docs/<plugin/core>/reflections/<yyyy-mm-dd>-planning-<short-name>.md` — problems encountered, how resolved, what was learned about planning.

**New:**
> Delegate planning reflection via `session-codex` `continue`: reviewer writes `docs/<plugin/core>/reflections/<yyyy-mm-dd>-planning-<short-name>.md` — problems encountered, how resolved, what was learned about planning.

**Current (MERGE):**
> Write `docs/<plugin/core>/reflections/<yyyy-mm-dd>-cycle-<short-name>.md` — plan→impl translation, review iterations and root causes, delegation effectiveness, process improvements.

**New:**
> Delegate cycle reflection to IMP via `session-codex` `continue`: IMP writes `docs/<plugin/core>/reflections/<yyyy-mm-dd>-cycle-<short-name>.md` — plan→impl translation, review iterations and root causes, delegation effectiveness, process improvements.

### 4. Run tests on main after squash merge, before commit

**Evidence:** v2.12.0 did this. v0.7.0 didn't explicitly. Should be standard — squash merge can introduce subtle issues.

**Current:**
> Ask HC permission → on main: `git merge --squash .worktrees/<name>`, Linux-style commit message. No co-authors.

**New:**
> Ask HC permission → on main: `git merge --squash .worktrees/<name>`, Linux-style commit message. No co-authors. Run tests on main after merge, before commit.

## Implementation Tasks

- [x] 1. Update CLAUDE.md L94: merge conflicts in worktree
- [x] 2. Add Codex `.git` workaround to IMPLEMENTATION SETUP
- [x] 3. Update PLANNING END: delegate planning reflection via session-codex
- [x] 4. Update MERGE: delegate cycle reflection to IMP, add test-after-merge
- [x] 5. Verify line count stays under ~150 lines (148 lines)
- [+] 6. Added worktree limitation note to Codex sandbox workaround

## Acceptance Criteria

- [x] CLAUDE.md reflects all 4 changes
- [x] Line count ≤ 155 (actual: 148)
- [x] No contradictions introduced between sections
- [x] Changes are traceable to specific reflection evidence
