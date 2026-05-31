# firefoxctl — Implementation Plan

Date: 2026-05-31
Status: active

## Context

Firefox removed CDP entirely. WebDriver BiDi is the only automation protocol.
Firefox speaks BiDi natively at `ws://127.0.0.1:PORT/session` — no geckodriver
needed. However, Firefox sets `navigator.webdriver=true` on any
`--remote-debugging-port` session (Bug 1719505, Firefox 101+), making it
detectable by anti-bot systems. This tool is a test/research tool that proves
BiDi works and documents Firefox's self-imposed limitations for agent use.

## Phase 1 — BiDi connection + list [x]

- Single-file `firefoxctl.py` with `uv` inline deps (aiohttp)
- BiDi WebSocket connection to `ws://127.0.0.1:PORT/session`
- `session.new` / `session.end` lifecycle
- `list` command via `browsingContext.getTree`
- Futures-by-ID command/response matching
- Event subscription plumbing (for later use)
- Requires Firefox running with `--remote-debugging-port`

## Phase 2 — Core commands [x]

- `eval` — `script.evaluate`
- `screenshot` — `browsingContext.captureScreenshot`
- `navigate` — `browsingContext.navigate`
- `get-text` / `get-html` / `exists` / `count` — DOM helpers via `script.callFunction`
- `click` / `fill` — interaction via `script.callFunction`

## Phase 3 — Daemon mode [x]

- Persistent WebSocket, Unix socket interface
- `start` / `stop` / `send` commands
- JSON line protocol (same as chromectl)
- Auto-reconnect on WebSocket drop

## Phase 4 — Packaging [x]

- SKILL.md for Claude Code
- README.md with "painted into a corner" disclaimer
- Marketplace entry in flow-state
- Unit tests (mocked BiDi, no Firefox needed)
- Integration test script (real Firefox)
