# 0002 — No daemon; the CLI is stateless

Status: accepted (v1.1.0)

## Context

A daemon was designed to share one IMAP connection across processes. Measured before building it:

```
imap-slim MCP processes running:  11
IMAP connections they hold:        0
```

Nothing connects until an action asks — `main()` is only `mcp.run()`. At a few commands every few
days there was no connection contention to solve.

`chrome-control`'s daemon exists because Chrome prompts on every new WebSocket connection. IMAP has
no such dialog, so that precedent does not transfer.

## Decision

No daemon. Each CLI invocation connects, acts and exits.

## Consequences

- Zero connections held between commands.
- Per-command cost is one login. **Revisit if usage becomes frequent enough for that to matter** —
  the full daemon design, including the threat model for an unauthenticated socket carrying
  keychain-unlocked mail, is in `plans/2026-09-07-cut4b-daemon.md`.
- Anything reintroducing a daemon must handle: a socket probe cannot distinguish a dead daemon from
  a busy one, so liveness needs a lock held for the process lifetime.
