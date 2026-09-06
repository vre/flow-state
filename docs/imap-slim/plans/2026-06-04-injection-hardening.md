# Browser-Control Prompt Injection Hardening

## Intent

Browser-control tools return web-page content (titles, URLs, eval results, console output, DOM text) to the LLM as tool responses. A malicious page can embed prompt-injection markers (`<|im_start|>`, `[INST]`, role XML, etc.) in any of these fields. Without sanitization, the LLM may interpret page content as instructions.

imap-slim-mcp already has `injection_defense.py` solving this for email. Browser-control needs the same protection.

## Goal

All text returned by `firefoxctl` and `chromectl` daemon dispatch is sanitized via `injection_defense.py` before reaching the LLM. The module is copied into both tools as a library file with a source pointer.

## Situational Context

- `imap-slim-mcp/injection_defense.py` (85 lines): production-proven module with NFKC normalization, invisible-char stripping, chat-template/role/instruction marker stripping, delimiter escaping. Exports `sanitize_external_text(text) -> (str, bool)` and `wrap_untrusted(text) -> str`.
- `wrap_untrusted` currently hardcodes `EXTERNAL_EMAIL_` prefix. Needs a `kind` parameter to generalize.
- Both browser tools are single-file scripts with `uv run` inline deps. Adding `injection_defense.py` as a second file is acceptable per HC direction ("library file in both projects").
- `wiki/docs/data-ingestion-safety.md` defines the three-layer defense: (1) NFKC + invisible strip, (2) marker strip, (3) nonce wrap. Layer 3 (wrap) is for prompt composition, not structured tool responses — browser-control only needs layers 1-2.
- Browser tools return results as JSON dicts via Unix socket. The LLM receives them as structured tool responses, not concatenated prompt text.
- All results are JSON-serializable (dict, list, str, int, float, bool, None). Firefox `_unpack_value` returns these types only. Chrome `returnByValue` returns JSON types only. No tuples/sets/custom containers.
- Firefox `_dispatch_safe` (line 590) is dead code — never called. Only `_dispatch_safe_daemon` is used.

## Constraints

- `injection_defense.py` must remain a standalone module with no external dependencies (stdlib only: `re`, `secrets`, `unicodedata`).
- Single import: `from injection_defense import sanitize_external_text`.
- Must not break existing output format — only string values within result dicts change when they contain injection markers. Clean strings pass through unchanged.

## Design

### Module adaptation

Copy `imap-slim-mcp/injection_defense.py` to `chrome-control/injection_defense.py` and `firefox-control/injection_defense.py`. Add source pointer comment at top:

```python
# Canonical source: imap-slim-mcp/injection_defense.py
# Keep in sync — copy, do not import across plugin boundaries.
```

Add `kind` parameter to `wrap_untrusted` with validation:

```python
def wrap_untrusted(text: str, kind: str = "EMAIL") -> str:
    if not re.fullmatch(r"[A-Za-z0-9_]+", kind):
        raise ValueError(f"kind must be alphanumeric/underscore, got: {kind!r}")
    nonce = secrets.token_hex(4)
    tag = kind.upper()
    return f"[EXTERNAL_{tag}_{nonce}_START]\n{text}\n[EXTERNAL_{tag}_{nonce}_END]"
```

The existing `_MARKER_PATTERNS` fake-spotlight pattern (`EXTERNAL_[A-Z0-9_]+_(?:START|END)`) already matches any kind — no change needed.

Back-port `kind` parameter to `imap-slim-mcp/injection_defense.py` too. Existing call sites pass no argument → default `"EMAIL"` preserves behavior.

### Sanitization choke point

Add `_sanitize_result(obj)` to each tool. Recursively walks the dict/list structure, calling `sanitize_external_text` on every string value — both keys and values. Returns the sanitized structure. The suspicious flag is discarded (no banner needed for tool responses — sanitization is silent).

```python
from injection_defense import sanitize_external_text

def _sanitize_result(obj):
    if isinstance(obj, str):
        safe, _ = sanitize_external_text(obj)
        return safe
    if isinstance(obj, dict):
        return {_sanitize_result(k): _sanitize_result(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_result(item) for item in obj]
    return obj
```

Keys are sanitized because `eval`, `bidi`, and `cdp` commands can return page-controlled object keys in their results.

**Sanitization is unconditional** — applied to all dispatch results. `sanitize_external_text` on clean strings is a no-op (NFKC of ASCII is identity, no markers found = same string returned). This avoids maintaining a per-command exclusion list and ensures no path is missed. Error messages, file paths, status info — all pass through unchanged because they contain no injection markers.

Apply at `_dispatch_safe_daemon` (Firefox, line 656) and `dispatch_safe` (Chrome, line 554), wrapping the return value of the inner `_dispatch` / `dispatch` call:

```python
# Firefox _dispatch_safe_daemon:
result = await asyncio.wait_for(_dispatch(conn, req), timeout=timeout)
return _sanitize_result(result)

# Chrome dispatch_safe:
result = await asyncio.wait_for(self.dispatch(req), timeout=timeout)
return _sanitize_result(result)
```

Error paths (exception handlers) also return dicts with string values — these get sanitized too, which is harmless and consistent.

### SKILL.md update

Add to both SKILL.md files:

```
Tool responses are sanitized: prompt-injection markers in page content are stripped before reaching the LLM.
```

### imap-slim-mcp back-port

Add `kind` parameter with validation to `wrap_untrusted` in `imap-slim-mcp/injection_defense.py`. Default `"EMAIL"`. No call-site changes needed.

Update imap-slim-mcp tests: add test for `kind` parameter and validation.

## Acceptance Criteria

- [x] AC1: `injection_defense.py` exists in `chrome-control/` and `firefox-control/`, identical to the post-change `imap-slim-mcp/injection_defense.py` except for the source-pointer comment at top. `wrap_untrusted` accepts `kind` parameter (default `"EMAIL"`) with `[A-Za-z0-9_]+` validation.
- [x] AC2: `_sanitize_result` function in both tools recursively sanitizes all string keys and values in result dicts/lists via `sanitize_external_text`. Non-string types (int, float, bool, None) pass through unchanged.
- [x] AC3: Firefox `_dispatch_safe_daemon` applies `_sanitize_result` to all results before returning to daemon socket.
- [x] AC4: Chrome `dispatch_safe` applies `_sanitize_result` to all results before returning to daemon socket.
- [x] AC5: `imap-slim-mcp/injection_defense.py` updated with `kind` parameter on `wrap_untrusted`. Existing call sites unchanged (default `"EMAIL"`).
- [x] AC6: imap-slim-mcp tests added: `wrap_untrusted("text", "WEBPAGE")` produces `EXTERNAL_WEBPAGE` in delimiter; invalid kind raises `ValueError`.
- [x] AC7: Both SKILL.md files mention injection sanitization.
- [x] AC8: `ruff check` + `ruff format --check` pass on all changed `.py` files.
- [x] AC9: Existing imap-slim-mcp tests still pass: `cd tests && uv run pytest imap-slim-mcp/`.

## Testing Strategy

- ruff check + ruff format on all changed files (pre-commit hook covers browser tools)
- Existing imap-slim-mcp test suite validates `sanitize_external_text` behavior — the copied module is identical
- Unit test for `_sanitize_result`: nested dict/list with `<|im_start|>` in values and keys → stripped; clean strings → unchanged; int/bool/None → unchanged
- Manual: `chromectl <id> eval "document.title"` on a page with injection markers in title → verify markers stripped
- Manual: `firefoxctl <ctx> get-text "body"` on page with `<|im_start|>` in body → verify stripped

## Out of Scope

- Shared module extraction (breaks single-file + library property)
- `wrap_untrusted` usage in browser tools (tool responses are structured JSON, not prompt text)
- Sanitizing user-provided inputs (expressions, selectors) — these come from the LLM, not from web pages
- Tests for browser-control `injection_defense.py` copies beyond `_sanitize_result` (identical module, tested via imap-slim-mcp suite)

## Tasks

- [x] 1. Add `kind` parameter with validation to `imap-slim-mcp/injection_defense.py`, add tests, run test suite
- [x] 2. Copy post-change `injection_defense.py` to both browser tools with source-pointer comment
- [x] 3. Add `_sanitize_result` to Firefox, wire into `_dispatch_safe_daemon`, add unit test
- [x] 4. Add `_sanitize_result` to Chrome, wire into `dispatch_safe`, add unit test
- [x] 5. Update both SKILL.md files
- [x] 6. Verify: ruff check + ruff format on all changed files, imap-slim-mcp tests pass

## Files Changed

- `imap-slim-mcp/injection_defense.py` — add `kind` parameter with validation
- `tests/imap-slim-mcp/test_injection_defense.py` — add `kind` + validation tests
- `chrome-control/injection_defense.py` — new file (copy)
- `firefox-control/injection_defense.py` — new file (copy)
- `chrome-control/chromectl.py` — import + `_sanitize_result` + wire in `dispatch_safe`
- `firefox-control/firefoxctl.py` — import + `_sanitize_result` + wire in `_dispatch_safe_daemon`
- `chrome-control/SKILL.md` — sanitization mention
- `firefox-control/SKILL.md` — sanitization mention

## Reflection

<!-- Written post-implementation by IMP -->
<!-- ### What went well -->
<!-- ### What changed from plan -->
<!-- ### Lessons learned -->
