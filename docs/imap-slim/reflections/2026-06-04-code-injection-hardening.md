# Code Reflection: Injection Hardening

**Plan**: `docs/plans/2026-06-04-injection-hardening.md`
**Date**: 2026-06-04

## What was done

Three-part change across imap-slim-mcp and both browser-control tools:

1. Added `kind` parameter with `[A-Za-z0-9_]+` validation to `wrap_untrusted` in imap-slim-mcp. Default `"EMAIL"` preserves existing behavior.
2. Copied `injection_defense.py` to `chrome-control/` and `firefox-control/` with source-pointer comment.
3. Added `_sanitize_result` (recursive key+value sanitization) to both browser tools, wired into `dispatch_safe` / `_dispatch_safe_daemon`.

## What changed from plan

Nothing — implementation matched plan exactly.

## Lessons learned

- Unconditional sanitization at the dispatch boundary is the right abstraction. No per-command logic, no exclusion list to maintain. `sanitize_external_text` is a no-op on clean strings, so there's no cost to over-applying it.
- The `from injection_defense import sanitize_external_text` import gets grouped with third-party imports by ruff (same isort category as `aiohttp`). Not ideal but correct — ruff treats same-directory imports as first-party by default only when there's a `pyproject.toml` declaring the package.
