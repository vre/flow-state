# Browser-Control Hardening: Architecture Review Fixes

## Intent

Architecture review of chrome-control and firefox-control found 10 issues (resilience gaps, bugs, incorrect error handling) and 2 feature gaps (Firefox lacks prefix-match and reconnect that Chrome has). Fixing these makes both tools production-grade and narrows the maturity gap.

## Goal

Both browser-control tools handle connection failures gracefully, detect errors correctly, and share equivalent UX features (prefix-match IDs, connect timeouts, liveness probes).

## Situational Context

- `firefox-control/firefoxctl.py` (1092 lines): WebDriver BiDi CLI, single `BiDiConnection` class, daemon with `nonlocal conn` closures. No reconnect — connection loss kills daemon. No prefix-match on context IDs.
- `chrome-control/chromectl.py` (1424 lines): CDP CLI, `Dispatcher` class with `FlatSession` multiplexing, reconnect, liveness probes. Has prefix-match via `_resolve_target()`. Per-session errors nuke all sessions instead of retrying one.
- Both share ~200 lines of identical helper JS generation (`_build_helper_js`, `_build_wait_js`) with no sync markers.
- Auto-start daemon and SCE fixes from current session already applied (uncommitted).

## Constraints

- Single-file scripts with `uv run` inline deps — no shared module extraction.
- Firefox BiDi: only 1 concurrent session. Zombie sessions unrecoverable without Firefox restart (`session.new` fails with "already started").
- Chrome M144+: each new WebSocket triggers permission dialog. Daemon must hold connection.

## Design

### Firefox reconnect (firefoxctl `cmd_start`, line 592)

**Concurrency**: add `_reconnect_lock = asyncio.Lock()` in `cmd_start()` scope. All reconnect attempts acquire this lock.

Add `_reconnect()` nested coroutine using `nonlocal conn`:
1. Acquire `_reconnect_lock`. If already held, wait — don't start parallel reconnects.
2. Close old conn via `conn.__aexit__` (try/except — may already be dead).
3. Create new `BiDiConnection(host, port)`, call `__aenter__()` (does `session.new` with 10s timeout via `asyncio.wait_for`).
4. If BiDiError "already started" → zombie session, can't recover → `_dead = True`, return False.
5. 5 attempts, 1s delay. Print status per attempt.
6. On success: update `nonlocal conn`, return True.

**Error classification in `_dispatch_safe_daemon`** (line 616): reconnect only on transport-level errors (`aiohttp.ClientError`, `ConnectionError`, `OSError`). NOT on `BiDiError` (protocol errors like bad context ID, invalid method). On transport error → call `_reconnect()` → if success, retry command once → if retry fails, return error. On `BiDiError` → return error directly without reconnect.

**Liveness probes in `idle_watchdog()`** (line 674): add `liveness_counter` (matching Chrome pattern at chromectl.py:982-1003). Every ~30s when idle >10s, call `asyncio.wait_for(conn.send("session.status", {}), timeout=5)`. On failure → `_reconnect()`, if that fails → `_dead = True`, shutdown.

**`BiDiConnection.send()` timeout removal** (line 148): remove `timeout=30.0` wrapper. Add `timeout` param to `__aenter__` for `session.new` call: `await asyncio.wait_for(self.send("session.new", ...), timeout=10)`. All other callers control timeout via `_dispatch_safe`/`_dispatch_safe_daemon`.

### Firefox prefix-match (firefoxctl `_dispatch`, line 514)

Add `_resolve_context(conn, partial)` coroutine:
- If input looks like a full UUID (contains `-` and len >= 36) → use as-is.
- Otherwise → `browsingContext.getTree({})`, collect top-level context IDs only (not iframe children — matches `cmd_list` scope).
- `startswith` match on context ID strings.
- 0 matches → `{"error": "No context matching '<partial>'"}`.
- \>1 matches → `{"error": "Ambiguous: '<partial>' matches N contexts"}`.

Apply at top of target-command section in `_dispatch()` where `context = req.get("context")`.

### Chrome per-session retry (chromectl `Dispatcher.dispatch`, line 579)

Wrap the target-command if/elif block (lines 603-623) in a try/except:
```python
try:
    result = await self._dispatch_target_cmd(cmd, req, target_id)
except (CDPError, ConnectionError) as e:
    self.sessions.pop(target_id, None)
    result = await self._dispatch_target_cmd(cmd, req, target_id)
```

Extract target commands into `_dispatch_target_cmd(cmd, req, target_id)` method. The retry re-attaches via `get_session()` (which creates new `FlatSession` when cache miss). This is safe because CDPError on a stale session fires before command execution — the session attachment itself fails.

If retry also raises → let it propagate to `dispatch_safe()` which handles full browser reconnect.

### Chrome console-tail handler cleanup (chromectl `_dispatch_console_tail`, line 718)

Same pattern as Firefox AC5: wrap `asyncio.sleep(duration)` in try/finally, clear handler in finally block:
```python
session.set_event_handler(console_handler)
try:
    await asyncio.sleep(duration)
finally:
    session.set_event_handler(None)
```

### Connect timeout — all `open_unix_connection` call sites

Wrap every `asyncio.open_unix_connection()` in `asyncio.wait_for(..., timeout=5)`.

**firefoxctl.py call sites:**
- `_send_to_daemon` (line 733) — main client path
- `cmd_start` stale socket probe (line 598)
- `cmd_stop` (line 719)
- `_auto_start_daemon` readiness probe (line 762) — already has 2s timeout on readline, add 5s on connect

**chromectl.py call sites:**
- `_daemon_request` (line 1096) — main client path
- `cmd_start` stale socket probe (line 928)
- `cmd_stop` (line 877)
- `_auto_start_daemon` readiness probe (line 1131) — already has 2s timeout on readline, add 5s on connect

## Acceptance Criteria

- [x] AC1: Firefox daemon reconnects on transport errors (`aiohttp.ClientError`, `ConnectionError`, `OSError`) during command dispatch. Logs reconnect attempt. Retries command once on success. Does NOT reconnect on `BiDiError` (protocol errors).
- [x] AC2: Firefox daemon detects zombie BiDi session ("already started" in BiDiError) during reconnect, logs "zombie BiDi session — restart Firefox", sets `_dead`, daemon exits.
- [x] AC3: Firefox liveness probes every ~30s when idle >10s. On probe failure → reconnect attempt → shutdown if reconnect fails.
- [x] AC4: Firefox `cmd_list()` returns `{"context": "...", "url": "..."}` — no broken title field.
- [x] AC5: Firefox AND Chrome `console-tail` handler cleaned up via try/finally even if sleep interrupted.
- [x] AC6: Firefox prefix-match on context IDs: top-level contexts only, `startswith` match, error on 0 or >1 matches.
- [x] AC7: `BiDiConnection.send()` has no hardcoded timeout. `__aenter__` wraps `session.new` in 10s timeout. Dispatch callers control their own timeouts.
- [x] AC8: Chrome `cmd_stop` grep requires `--user-data-dir=` AND `chromectl` in process line.
- [x] AC9: Chrome `_daemon_request` JSON-output path parses `json.loads()`, checks `"error" in result` dict key.
- [x] AC10: All `open_unix_connection()` calls in both tools wrapped in `asyncio.wait_for(..., timeout=5)`.
- [x] AC11: Chrome target commands retry once on `CDPError`/`ConnectionError`: evict session, re-attach, retry. Does not retry non-target commands.
- [x] AC12: Both tools have `# Keep in sync with {other}/` comment above `_build_helper_js`, `_build_wait_js`, `_HELPER_COMMANDS`, `_WAIT_COMMANDS`.
- [x] AC13: Firefox reconnect uses `asyncio.Lock` — no parallel reconnect attempts from concurrent client handlers.

## Testing Strategy

- `ruff check` + `ruff format --check` on both .py files (pre-commit hook)
- Manual reconnect: `firefoxctl list`, kill Firefox, `firefoxctl list` → expect "reconnect attempt 1/5" log, then either reconnect success or "zombie BiDi session" shutdown
- Manual prefix-match: `firefoxctl list` → note first 4 chars of context ID → `firefoxctl <4chars> eval "document.title"` → expect result
- Manual prefix ambiguity: `firefoxctl <1char> eval "1"` with multiple tabs → expect "Ambiguous" error
- Manual cmd_stop: run `chromectl stop` with no launched instances → expect "Nothing to stop", no process kills
- Manual connect timeout: kill daemon process (`kill -9`), leave socket file → `firefoxctl list` → expect timeout error within ~5s, then auto-start

## Out of Scope

- Shared module for duplicated helper JS (breaks single-file property)
- Chrome `_dispatch_eval` serializationOptions (CDP `returnByValue` already handles this)
- Firefox multiplexing (BiDi doesn't need it — native context addressing)
- Automated unit tests for failure paths (no test framework for WebSocket mocking in these single-file tools)

## Tasks

- [x] 1. Firefox reconnect + liveness probes + send() timeout removal + reconnect lock (AC1-3, AC7, AC13)
- [x] 2. Firefox fixes: cmd_list title, console-tail handler leak, prefix-match context IDs (AC4-6)
- [x] 3. Chrome fixes: cmd_stop grep, `_daemon_request` error detection, per-session retry, console-tail handler leak (AC5, AC8-9, AC11)
- [x] 4. Both: connect timeout on all open_unix_connection sites + sync comments on helpers (AC10, AC12)
- [x] 5. Verify: ruff check + ruff format on both files

## Files Changed

- `firefox-control/firefoxctl.py` — tasks 1, 2, 4
- `chrome-control/chromectl.py` — tasks 3, 4

## Reflection

<!-- Written post-implementation by IMP -->
<!-- ### What went well -->
<!-- ### What changed from plan -->
<!-- ### Lessons learned -->
