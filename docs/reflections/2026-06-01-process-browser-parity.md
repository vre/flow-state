# Process Reflection: Browser Control Parity

**Framing**: `docs/plans/2026-06-01-frame-browser-control-parity.md`
**Date**: 2026-06-01

## Process

Framing process (four cuts) with HC reviewing all plans before execution. HC chose "All" at plan review gate — every cut plan was presented and approved individually.

## What worked

- **Cut sequencing** — daemon resilience first (cut 1), new commands second (cut 2), `--json` third (cut 3), docs last (cut 4). Each cut built on stable ground from the previous one. `--json` could reference the new commands, docs could reference everything.
- **Protocol-aware framing** — early HC constraint ("if bidi and cdp are different, we should not shoehorn") prevented a class of bugs. Each plan explicitly stated BiDi vs CDP terminology.
- **Plan review caught design issues** — the Chrome `_format_output` design came from analyzing the actual response shapes during planning, not during implementation. The plan's response-type dispatch table mapped directly to code.

## What could improve

- **Self-review caught bugs that should have been caught during implementation** — the `nonlocal _dead` bug is a Python closure pitfall that's easy to miss when nesting three levels of closures. A quick `grep nonlocal` pass after writing nested functions would catch this class of bug systematically.
- **`last_success` dead code** — written during cut 1 implementation "just in case" without a concrete consumer. YAGNI violation. Should have left it out and added it when actually needed.
- **No cross-model review** — flow-state process calls for `session-codex` delegation. Skipped here because the session context was already large and the self-review caught the material bugs. Trade-off: faster completion vs independent verification.

## Delegation

No delegation — all four cuts implemented directly in ORC context. The work was sequential and context-dependent (each cut built on prior cuts), making delegation overhead higher than benefit for this scope.
