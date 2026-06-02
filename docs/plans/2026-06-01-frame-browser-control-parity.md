# Browser-Control Parity — Framing Document

Date: 2026-06-01
Status: active
Plugins: firefox-control, chrome-control

## Problem

Three rounds of skeptical symmetry review found structural gaps between firefox-control and chrome-control. Firefox daemon lacks resilience (no reconnect, no liveness), is missing commands that BiDi supports (`open`, `status`, `console-tail`, `targets`), and has a direct-connection fallback that bypasses the daemon. CLI output differs: Chrome prints raw JSON, Firefox prints human-readable — neither tool gives the user control.

## HC Requirements (verbatim)

1. Add reconnect/resilience to Firefox daemon
2. `--json` flag for both tools — JSON when requested, human-readable otherwise
3. Fix feature gaps where applicable
4. Firefox should require daemon (no direct-connection fallback)

## Key Constraints

- **Protocol-specific terminology preserved**: BiDi uses `contexts`/`context`/`result`, CDP uses `targets`/`id`/`value`. Do not shoehorn.
- **No full Dispatcher class for Firefox**: BiDi has no session multiplexing. `nonlocal conn` with reconnect helper is sufficient.
- **No co-authors in commits** (flow-state convention)
- **Tests in `tests/<plugin>/`**, not in plugin dirs

## Cut Sequence

1. **Firefox daemon resilience + daemon-first** — restructure `cmd_start()` for reconnect, liveness probe, `_dead` flag. Remove direct-connection fallback from `_route_request()`.
2. **Firefox new commands** — `open`, `status`, `console-tail`, `targets`. Parser, dispatch, CLI handlers.
3. **`--json` flag for both tools** — Firefox: add flag, bypass formatting. Chrome: add flag, add human-readable formatting as default.
4. **Docs + tests** — README, SKILL.md updates for both. Test updates for daemon-first and `--json`.

## Decisions

- BiDi reconnect = create new `BiDiConnection` + `session.new` (handled by `__aenter__`). Old session state (event subscriptions) is lost — acceptable, Chrome behaves identically.
- Liveness probe: `session.status` every ~30s when idle, matching Chrome's `list_targets()` pattern.
- `console-tail`: uses existing `BiDiConnection.on_event()` + `subscribe()`. Handler removal via direct list pop (private attr access) — add `off_event()` method if cleaner.
- `targets` flattens `browsingContext.getTree` children as `type: "iframe"`, top-level as `type: "tab"`.
- Chrome's CLI output change (raw JSON → human-readable default) is a breaking change for scripts parsing CLI output. Socket protocol is unaffected. Tests updated to use `--json` or socket.
