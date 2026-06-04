# Planning Reflection: Browser-Control Hardening

## What went well

- Architecture review produced a concrete, prioritized issue list with user alignment on each item before planning started.
- Codex cross-review caught a real concurrency bug (shared `conn` without lock) and a misclassification risk (BiDiError vs transport errors) that self-review missed.

## What changed during planning

- Added AC13 (reconnect lock) — Codex identified concurrent handler race.
- Error classification narrowed: reconnect only on transport errors, not protocol errors.
- Chrome console-tail handler leak added to scope (same bug as Firefox, initially missed).
- `__aenter__` gets explicit timeout for `session.new` — removing `send()` timeout without this would create a hang risk.
- All `open_unix_connection` call sites enumerated (8 total across both tools) instead of just the main client path.

## Lessons learned

- Self-review missed concurrency and classification issues. The Codex review step is not ceremonial — it found substantive problems.
- "Remove hardcoded timeout" is not a simple deletion — every caller of the now-unbounded function must be audited for timeout coverage.
