# Code Reflection: Browser Control Parity

**Framing**: `docs/plans/2026-06-01-frame-browser-control-parity.md`
**Date**: 2026-06-01

## What was done

Four cuts closing feature gaps between firefox-control and chrome-control:

1. Firefox daemon resilience — reconnect loop (5 attempts), liveness probe (session.status every ~30s), `_dead` flag for clean shutdown, removed direct-connection CLI fallback
2. Firefox new commands — `open`, `status`, `targets`, `console-tail` via BiDi equivalents
3. `--json` flag for both tools — human-readable default, raw JSON on `--json`
4. Documentation and integration tests updated for all new functionality

## What changed from plan

- `last_success` timestamp was added to `_dispatch_safe_daemon` but never used. Intended for stale-connection detection but the liveness probe covers that use case. Dead code.
- `console-tail` doesn't call `session.unsubscribe` after collection. BiDi supports it but `BiDiConnection` has no `unsubscribe()` method. The subscription persists for the daemon's lifetime — harmless with idle timeout but technically a leak.

## Self-review findings

Two bugs caught and fixed:

1. **`_dead` nonlocal scope** — `_dispatch_safe_daemon` assigned `_dead = True` on reconnect-then-fail without declaring `nonlocal _dead`. Created a local variable; daemon wouldn't shut down after total connection failure.
2. **Chrome `--json` error exit code** — `--json` mode printed error JSON but exited 0. Fixed to exit 2, matching Firefox behavior.

## Protocol terminology

Preserved BiDi vs CDP terminology throughout:
- Firefox: `contexts`/`context`/`result` (BiDi)
- Chrome: `targets`/`id`/`value` (CDP)

No shoehorning — each tool speaks its native protocol's language.

## Numbers

- 5 commits (4 cuts + 1 self-review fix)
- ~330 new/changed lines in firefoxctl.py
- ~50 new/changed lines in chromectl.py
- ~130 new lines in firefox integration test
- 876 total lines added across 13 files (including plans and docs)
