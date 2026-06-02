# Cut 3: --json flag for both tools

Framing: `docs/plans/2026-06-01-frame-browser-control-parity.md`

## Intent

LLM agents need parseable JSON. Humans need readable output. Neither tool lets the user choose.

## Goal

Both `firefoxctl` and `chromectl` accept `--json` flag. Default output is human-readable. `--json` outputs raw single-line JSON from the daemon.

## Situational Context

**Firefox** (`firefoxctl.py`): `_route_request()` already formats output per response type (format_tabs, "Saved X bytes", pretty-print). Adding `--json` = bypass formatting, print raw JSON.

**Chrome** (`chromectl.py`): `_daemon_request()` (line 1042) always prints raw JSON from daemon socket. Adding `--json` = keep current behavior as `--json`, add formatting for default. Chrome uses a different routing pattern: `_daemon_request` reads raw bytes from socket, `_route_request` calls `_daemon_request`. Need to parse JSON in `_daemon_request` when not `--json` to format it.

**Socket protocol**: Unchanged. Socket always returns JSON. `--json` only affects CLI output.

## Constraints

- Chrome CLI behavioral change: scripts parsing CLI output break without `--json`. Socket protocol unaffected.
- Chrome test impact: `tests/chrome-control/test_integration.sh` lines 280-284 parse JSON from CLI. Need `--json` flag on those calls.
- Firefox test: already parses human format (fixed in cut 1). No impact.

## Design

### Firefox

Parser: add `--json` to top-level args.

`_route_request()`: check `getattr(args, "json_output", False)`. If true, print `json.dumps(result, ensure_ascii=False)` and return. Otherwise existing formatting.

### Chrome

Parser: add `--json` to top-level args.

`_daemon_request()`: currently prints raw bytes. Change to:
1. Decode and parse JSON
2. If `--json`: print raw single-line JSON (current behavior)
3. If not `--json`: call `_format_output(result)`

`_format_output(result)`:
- `"error"` → stderr + exit 2
- `"targets"` → `ID  URL  TITLE` per line
- `"file"` → `Saved to {file}`
- `"messages"` → `+time  level  text` per line
- `"value"` → pretty-print if dict/list, bare value otherwise
- `"connected"` → key: value lines (status)
- `"status"` → print status string
- fallback → pretty JSON

`_route_request()`: pass `json_output` through to `_daemon_request`.

## Acceptance Criteria

- [ ] AC1: `firefoxctl list` outputs human-readable tab list (one line per tab)
- [ ] AC2: `firefoxctl --json list` outputs single-line JSON `{"contexts": [...]}`
- [ ] AC3: `chromectl list` outputs human-readable target list (one line per target)
- [ ] AC4: `chromectl --json list` outputs single-line JSON `{"targets": [...]}`
- [ ] AC5: `chromectl --json TARGET eval "1+1"` outputs `{"value": 2}`
- [ ] AC6: Chrome integration tests pass with `--json` flag added to CLI test lines

## Testing Strategy

- Chrome integration test: add `--json` to CLI test commands (lines 280-284)
- Manual: run both tools with and without `--json`, compare output

## Out of Scope

- Doc updates (cut 4)

## Tasks

- [ ] 1. Firefox: add `--json` parser flag
- [ ] 2. Firefox: add `--json` bypass in `_route_request()`
- [ ] 3. Chrome: add `--json` parser flag
- [ ] 4. Chrome: add `_format_output()` function
- [ ] 5. Chrome: modify `_daemon_request()` and `_route_request()` for json_output
- [ ] 6. Chrome integration test: add `--json` to CLI test commands
- [ ] 7. Commit

## Files Changed

- `firefox-control/firefoxctl.py` — parser, `_route_request`
- `chrome-control/chromectl.py` — parser, `_daemon_request`, `_route_request`, new `_format_output`
- `tests/chrome-control/test_integration.sh` — CLI test lines
