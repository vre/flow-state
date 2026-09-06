# Process Reflection: Injection Hardening

**Plan**: `docs/plans/2026-06-04-injection-hardening.md`
**Date**: 2026-06-04

## Plan-to-implementation translation

Clean translation — plan specified exact choke points, exact code patterns, exact file locations. Implementation was mechanical.

## What went well

- Codex cross-review added value: dict key sanitization, `kind` validation, removal of contradictory scope constraint. All incorporated before implementation.
- Reusing the proven imap-slim-mcp module meant no new security research needed. Copy + wire.
- Single choke point per tool (dispatch_safe) kept the change minimal — 2 lines of wiring per tool plus the shared `_sanitize_result` function.

## What went poorly

- Created worktree in wrong repo (wiki instead of flow-state) on first attempt. EnterWorktree operates on CWD, which was the wiki. Should have used `git worktree add` directly in flow-state.

## Process improvements

- When creating worktrees for flow-state work from the wiki context, use `git -C ~/work/flow-state worktree add` directly rather than the EnterWorktree tool.
