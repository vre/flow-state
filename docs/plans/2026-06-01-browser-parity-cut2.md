# Cut 2: Firefox new commands — open, status, console-tail, targets

Framing: `docs/plans/2026-06-01-frame-browser-control-parity.md`

## Intent

An LLM agent switching from Chrome to Firefox loses four capabilities: opening tabs, checking daemon status, monitoring console, and listing all targets. BiDi supports all of these — they're implementation gaps, not protocol limitations.

## Goal

Firefox supports `open`, `status`, `console-tail`, and `targets` commands via daemon socket and CLI, matching Chrome's capability set where BiDi allows.

## Situational Context

- `_dispatch()` (line 441): handles list, bidi, eval, screenshot, navigate, reload, helpers, waits
- `BiDiConnection` has `on_event()` (line 143) and `subscribe()` (line 146) — ready for console-tail
- `cmd_list()` (line 153): calls `browsingContext.getTree`, returns top-level contexts only
- Chrome equivalents: `_dispatch_open` (Target.createTarget), `_dispatch_status` (dict), `_dispatch_console_tail` (event streaming), `_dispatch_list` with cmd=="targets" (all types)
- `_KNOWN_COMMANDS` (line 838): set of all recognized commands for argv preprocessing
- `_dispatch_safe_daemon` (line 545): needs extended timeout for console-tail

## Constraints

- BiDi `browsingContext.create` requires `type: "tab"` or `type: "window"` — use `"tab"`
- Event handler cleanup: `on_event()` only appends. Need to remove handler after console-tail collection.
- BiDi log events use `log.entryAdded` (not `Log.entryAdded` like CDP)
- `targets` should use BiDi terminology for types, not CDP terminology

## Design

### `open <url>`

```python
async def cmd_open(conn, url):
    result = await conn.send("browsingContext.create", {"type": "tab"})
    context = result.get("context", "")
    if url and url != "about:blank":
        await conn.send("browsingContext.navigate", {"context": context, "url": url, "wait": "complete"})
    return {"context": context, "url": url}
```

Dispatch: before context-required block (doesn't need existing context).
Socket: `{"cmd": "open", "url": "..."}` → `{"context": "new-id", "url": "..."}`

### `status`

Dispatch: before context-required block.
Returns daemon state dict. In daemon context, connection is always alive (or reconnect failed and daemon shut down).

```python
if cmd == "status":
    return {"connected": True, "port": port, "session_id": conn._session_id, "pid": os.getpid()}
```

Problem: `_dispatch()` takes `conn` but not `port`. Port is available in `cmd_start` scope. Two options:
1. Pass port through req dict from daemon
2. Extract from `conn.ws_url`

Option 2 is simpler — parse from `ws://host:port/session`.

### `console-tail`

Needs context. Uses BiDi event subscription.

```python
if cmd == "console-tail":
    duration = float(req.get("for", 10))
    messages = []
    start_ts = time.time()
    async def handler(data):
        params = data.get("params", {})
        tdelta = f"+{time.time() - start_ts:0.3f}s"
        entry = params.get("entry", params)
        messages.append({"t": tdelta, "level": entry.get("level", ""), "text": entry.get("text", "")})
    conn.on_event("log.entryAdded", handler)
    await conn.subscribe(["log.entryAdded"])
    await asyncio.sleep(duration)
    handlers = conn._event_handlers.get("log.entryAdded", [])
    if handler in handlers:
        handlers.remove(handler)
    return {"messages": messages}
```

Extended timeout in `_dispatch_safe_daemon`: add `console-tail` check.

### `targets`

Flatten `browsingContext.getTree` including children. No context required.

```python
if cmd == "targets":
    result = await conn.send("browsingContext.getTree", {})
    flat = []
    def flatten(ctx, depth=0):
        flat.append({"context": ctx.get("context", ""), "url": ctx.get("url", ""), "type": "tab" if depth == 0 else "iframe"})
        for child in ctx.get("children", []):
            flatten(child, depth + 1)
    for ctx in result.get("contexts", []):
        flatten(ctx)
    return {"targets": flat}
```

### Output formatting in `_route_request`

Add cases for new response shapes:
- `"targets"` key → format like list
- `"context"` + `"url"` (open response) → print context ID
- `"messages"` key → print each message line
- `"connected"` key (status) → print key: value lines

## Acceptance Criteria

- [ ] AC1: `firefoxctl open https://example.com` opens a new tab and returns context ID
- [ ] AC2: `firefoxctl status` returns connection info (connected, port, session_id, pid)
- [ ] AC3: `firefoxctl CONTEXT console-tail --for 5` captures log events for 5 seconds
- [ ] AC4: `firefoxctl targets` lists all browsing contexts including iframes
- [ ] AC5: All four commands work via socket protocol (`echo '{"cmd":"open","url":"..."}' | nc -U sock`)

## Testing Strategy

- Integration test: add sections for open, status, targets, console-tail to `tests/firefox-control/test_integration.sh`
- Manual: start daemon, test each command, verify output

## Out of Scope

- `--json` flag (cut 3)
- Chrome changes (cuts 3-4)
- Doc updates (cut 4)

## Tasks

- [ ] 1. Add `cmd_open()` function
- [ ] 2. Add `open`, `status`, `targets` to `_dispatch()` (before context check)
- [ ] 3. Add `console-tail` to `_dispatch()` (after context check)
- [ ] 4. Add `console-tail` timeout to `_dispatch_safe_daemon()`
- [ ] 5. Add parser subcommands + CLI handlers for all four
- [ ] 6. Update `_KNOWN_COMMANDS`
- [ ] 7. Add output formatting cases to `_route_request()`
- [ ] 8. Update integration test with new command tests
- [ ] 9. Commit

## Files Changed

- `firefox-control/firefoxctl.py` — dispatch, parser, CLI handlers, _route_request, _KNOWN_COMMANDS
- `tests/firefox-control/test_integration.sh` — new test sections
