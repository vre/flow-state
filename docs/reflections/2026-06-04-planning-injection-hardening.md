# Planning Reflection: Injection Hardening

## What went well

- imap-slim-mcp's `injection_defense.py` and wiki's `data-ingestion-safety.md` provided a clear reference implementation and threat model. No new security research needed.
- Identifying the single choke point (`_dispatch_safe_daemon` / `dispatch_safe`) simplified the design — one line change per tool instead of per-command wiring.

## What changed during planning

- Codex review identified key sanitization should also cover dict keys, not just values. `eval` and raw protocol commands can return page-controlled object keys.
- Removed the constraint "must not sanitize non-page-content fields" — unconditional sanitization is simpler and safe because `sanitize_external_text` is a no-op on clean strings.
- Added `kind` parameter validation (`[A-Za-z0-9_]+`) to prevent malformed delimiters.
- Added unit tests for `_sanitize_result` — Codex correctly flagged that manual-only browser testing was insufficient.
- Clarified that Firefox `_dispatch_safe` is dead code, only `_dispatch_safe_daemon` needs wiring.

## Lessons learned

- "Sanitize everything unconditionally" is simpler and safer than maintaining an exclusion list. The cost of sanitizing clean strings is zero (no markers = no changes).
- Cross-review caught the dict-key gap: eval results where page content appears in object property names, not just values. This is a real attack vector for pages that construct objects with injected key names.
