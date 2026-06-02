# Cut 1: Firefox daemon resilience + daemon-first

Framing: `docs/plans/2026-06-01-frame-browser-control-parity.md`

## Intent

Firefox daemon dies silently on WebSocket drop. An LLM agent loses the tool mid-session with no recovery path. Chrome daemon survives this — Firefox should too.

## Goal

Firefox daemon reconnects automatically on BiDi connection loss (5 attempts, 1s delay), runs liveness probes, and shuts down cleanly on unrecoverable failure. CLI requires daemon (no direct-connection fallback).

## Situational Context

- `cmd_start()` (line 510): `async with BiDiConnection(...)` — connection is scoped, not replaceable
- `_dispatch_safe()` (line 495): catches errors but no reconnect
- `idle_watchdog()` (line 560): checks idle timeout only, no liveness probe
- `_route_request()` (line 620): falls back to direct BiDi connection if no daemon socket
- BiDi requires `session.new` on each connection (unlike CDP's sessionless browser connection)
- `BiDiConnection.__aenter__()` handles `session.new` — creating a new instance and entering it IS the reconnect path
- Chrome reference: `Dispatcher._reconnect()` (chromectl.py:491), `dispatch_safe()` (550), liveness (980-988)

## Constraints

- No Dispatcher class — Firefox has no session multiplexing, `nonlocal conn` is sufficient
- BiDi `session.new` creates fresh session — event subscriptions from old session are lost (acceptable, Chrome same)
- Module-level `_dispatch_safe()` stays as public API — not imported by anything after this cut (daemon lib uses socket, direct fallback removed) but kept for potential direct-import use

## Design

### Current → Target

**`cmd_start()`**: Replace outer `async with` with manual lifecycle. Add nested `_reconnect()` using `nonlocal conn`. Add local `_dispatch_safe_daemon()` that wraps `_dispatch` with reconnect-on-failure + retry-once.

**`idle_watchdog()`**: Add `_dead` flag check. Add liveness probe: counter increments each 5s cycle, every 6th cycle (~30s) when idle >10s, call `conn.send("session.status", {})` with 5s timeout.

**`_route_request()`**: Remove `else` branch (direct connection). Match Chrome pattern: error + exit if no socket.

**Module-level `_dispatch_safe()`**: Keep unchanged — used by `firefoxctl_daemon.py` and potentially other callers. The daemon uses its own enhanced local version.

### Reconnect flow

```
dispatch_safe_daemon(req) → _dispatch(conn, req)
  ↓ on TimeoutError/BiDiError/ClientError/ConnectionError/OSError
  ↓ _reconnect() → close old conn, create new BiDiConnection, __aenter__()
  ↓   5 attempts, 1s delay
  ↓   success → retry _dispatch(conn, req) once
  ↓   failure → _dead = True, return error
```

## Acceptance Criteria

- [ ] AC1: Daemon reconnects on BiDi connection drop and resumes serving commands
  - Given: daemon running, BiDi connection drops
  - When: next command arrives
  - Then: daemon reconnects (up to 5 attempts), retries command, returns result
- [ ] AC2: Daemon shuts down on unrecoverable failure
  - Given: daemon running, BiDi connection drops, all 5 reconnect attempts fail
  - When: next watchdog cycle
  - Then: daemon prints message, removes socket, exits
- [ ] AC3: Liveness probe detects dead connection
  - Given: daemon idle >10s
  - When: ~30s liveness probe fires
  - Then: if connection dead, daemon shuts down cleanly
- [ ] AC4: CLI requires daemon (no direct fallback)
  - Given: no daemon socket exists
  - When: `firefoxctl list`
  - Then: prints error to stderr, exits with code 1
- [ ] AC5: Daemon cleanup on normal shutdown closes BiDi connection
  - Given: daemon running
  - When: `firefoxctl stop` or idle timeout
  - Then: BiDi connection closed (`session.end`), socket removed

## Testing Strategy

- Unit tests: mock BiDiConnection, verify reconnect logic, _dead flag, liveness probe behavior
- Integration test: `tests/firefox-control/test_integration.sh` — remove direct-mode test, verify daemon-mode still works
- Manual: start daemon → kill Firefox → send command → verify reconnect message → restart Firefox → verify recovery

## Out of Scope

- New commands (cut 2)
- `--json` flag (cut 3)
- Doc updates (cut 4)
- Chrome changes (cuts 3-4)

## Tasks

- [ ] 1. Restructure `cmd_start()`: manual conn lifecycle, `nonlocal conn`
- [ ] 2. Add `_reconnect()` nested coroutine (5 attempts, 1s delay)
- [ ] 3. Add `_dispatch_safe_daemon()` with reconnect-on-failure + retry
- [ ] 4. Add `_dead` flag to `idle_watchdog()`
- [ ] 5. Add liveness probe to `idle_watchdog()`
- [ ] 6. Add conn cleanup in `finally` block
- [ ] 7. Remove direct-connection fallback from `_route_request()`
- [ ] 8. Update `tests/firefox-control/test_integration.sh` — remove direct-mode tests, fix daemon-mode list parsing (currently tries json.loads on human-formatted output — parse human format or wait for --json in cut 3)
- [ ] 9. Commit

## Files Changed

- `firefox-control/firefoxctl.py` — lines 495-648 (dispatch_safe, cmd_start, _route_request)
- `tests/firefox-control/test_integration.sh` — remove lines 32-41 (direct mode section)
