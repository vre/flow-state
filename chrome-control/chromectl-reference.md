# chromectl Command Reference

Complete reference for `chromectl.py` — the CLI for chrome-control.

## Command Overview

**Top-level commands:**
- `start` — Connect to running Chrome, listen on Unix socket
- `stop` — Stop daemon and any launched Chrome instances
- `list` — List open tabs (pages only)
- `open <url>` — Open a new tab
- `status` — Show daemon connection status
- `targets` — List all targets (pages, workers, iframes)
- `helpers` — List DOM helper commands
- `cdp <method>` — Raw CDP command (auto-connect only)

**Target commands** — `chromectl TARGET <command> [args]`:
- `eval <expr>` — Execute JavaScript in a tab
- `screenshot [-o file] [--full-page]` — Capture screenshot
- `console-tail [--for N]` — Stream console messages
- `worker-eval <expr>` — Execute JavaScript in a worker
- `navigate <url>` — Navigate tab to URL
- `reload` / `back` / `forward` — Navigation
- 30+ DOM helpers — see `chromectl helpers`

Target IDs come from `list` or `open` output. Prefix match OK (e.g. `ABC1` instead of full 32-char ID).

**Legacy mode:**
- `launch [--headless]` — Launch a separate Chrome instance with full CDP access

## Global Options

```bash
--host HOST    # CDP host (default: 127.0.0.1)
--port PORT    # CDP port (default: 9222)
```

Place global options BEFORE the command:
```bash
./chromectl.py --port 9223 list
```

## start — Connect to Chrome

```bash
./chromectl.py start
```

Connects to your running Chrome via `DevToolsActivePort` and starts a daemon on a Unix socket (`/tmp/chromectl-<uid>.sock`). Chrome shows a permission dialog on first connect — click Allow.

The daemon keeps one persistent WebSocket connection to Chrome and multiplexes page sessions using flat sessions (`Target.attachToTarget` with `flatten=true`). This avoids repeated permission dialogs.

Auto-shuts down after 5 minutes of inactivity or when Chrome closes.

**Prerequisites:**
- Chrome M144+ (January 2026+) with remote debugging enabled: `chrome://inspect/#remote-debugging` → toggle on
- Applies to all profiles once enabled

## stop — Stop daemon and Chrome

```bash
./chromectl.py stop
```

Sends quit to the daemon (if socket exists), then terminates any Chrome processes launched by chromectl in legacy mode (identified by chromectl profile directories).

## list — List Targets

```bash
./chromectl.py list
```

Returns JSON objects (one per line) for each target:
```json
{"id": "ABC123", "type": "page", "title": "Page Title", "url": "https://..."}
```

**Target types:** page, background_page, service_worker, iframe

## open — Open New Tab

```bash
./chromectl.py open <url>
```

Returns JSON with target ID:
```json
{"id": "ABC123", "url": "https://example.com"}
```

**Extract target ID:**
```bash
TARGET=$(./chromectl.py open https://example.com | jq -r .id)
```

**Supported URLs:**
- HTTP/HTTPS: `https://example.com`
- Data URLs: `data:text/html,<h1>Test</h1>`

## eval — Execute JavaScript

```bash
./chromectl.py TARGET eval <expression>
```

**Features:**
- Top-level `await` supported (REPL mode)
- Returns JSON-serialized values

**Common patterns:**

```bash
./chromectl.py $ID eval "document.title"
./chromectl.py $ID eval "document.readyState"
./chromectl.py $ID eval "({title: document.title, url: location.href})"
./chromectl.py $ID eval "await fetch('/api/data').then(r => r.json())"
```

Most common eval patterns have helper commands — see `./chromectl.py helpers`. Use eval for complex or custom JS.

**Advanced patterns:**

```bash
# Performance timing — page load breakdown (Navigation Timing L2)
./chromectl.py $ID eval "
(() => { const n = performance.getEntriesByType('navigation')[0];
  return { dns: n.domainLookupEnd - n.domainLookupStart,
    tcp: n.connectEnd - n.connectStart,
    ttfb: n.responseStart - n.requestStart,
    domReady: n.domContentLoadedEventEnd - n.startTime,
    load: n.loadEventEnd - n.startTime }; })()"

# React component state (works with React 18 createRoot and 19)
./chromectl.py $ID eval "
(() => { const el = document.querySelector('#root') || document.querySelector('#app');
  if (!el) return 'no root element';
  const key = Object.keys(el).find(k => k.startsWith('__reactFiber\$') || k.startsWith('__reactContainer\$'));
  if (!key) return 'no React fiber found';
  const fiber = el[key];
  const states = [];
  let node = fiber;
  while (node) { if (node.memoizedState) states.push({type: node.type?.name, state: node.memoizedState});
    node = node.child; }
  return states.slice(0, 5); })()"
```

## screenshot — Capture Screenshot

```bash
./chromectl.py TARGET screenshot [-o output.png] [--full-page]
```

**Options:**
- `-o, --output` — Output file path (default: screenshot_<id>.png)
- `--full-page` — Capture entire scrollable page (not just viewport)

**Examples:**
```bash
./chromectl.py $ID screenshot -o page.png
./chromectl.py $ID screenshot -o full.png --full-page
```

## console-tail — Stream Console

```bash
./chromectl.py TARGET console-tail [--for SECONDS]
```

**Options:**
- `--for` — Duration in seconds to stream (default: 10)

**IMPORTANT:** Only captures messages logged AFTER the command starts. No historical messages.

**Output format:**
```json
{"t": "+2.011s", "console": "log", "args": ["Message text"]}
{"t": "+2.015s", "console": "warning", "args": ["Warning text"]}
{"t": "+2.020s", "console": "error", "args": ["Error message"]}
{"t": "+5.123s", "level": "error", "source": "javascript", "text": "Error details"}
```

**Usage pattern for debugging:**
```bash
# Start monitoring in background
./chromectl.py $ID console-tail --for 30 &

# Trigger actions
./chromectl.py $ID eval "myFunction()"

# Wait for console-tail to complete
wait
```

## targets — List All Targets

```bash
./chromectl.py targets
```

Like `list`, but returns all target types (pages, service workers, iframes) without filtering.

## status — Daemon Status

```bash
./chromectl.py status
```

Returns daemon connection info:
```json
{"connected": true, "mode": "auto-connect", "port": 9222, "sessions": 2, "pid": 12345}
```

**Fields:**
- `mode` — `auto-connect` (Chrome M144+ via DevToolsActivePort) or `http` (legacy)
- `sessions` — number of active flat sessions (attached targets)

## cdp — Raw CDP Command

```bash
./chromectl.py cdp <method>
```

Send a raw Chrome DevTools Protocol method at the browser level. Auto-connect mode only.

```bash
./chromectl.py cdp Browser.getVersion
```

Via socket protocol (with params):
```bash
echo '{"cmd":"cdp","method":"Target.getTargets"}' | nc -U /tmp/chromectl-$(id -u).sock
```

## worker-eval — Evaluate JS in a Worker

```bash
./chromectl.py TARGET worker-eval <expression>
```

Like `eval`, but attaches to service worker or background targets. Use `targets` (not `list`) to find worker target IDs.

**Note:** Worker attachment can be unstable on some Chrome versions — the WebSocket connection may drop. This is a known Chrome bug.

## DOM Helpers

Shorthands for common eval patterns. CSS selectors for element targeting.

```
chromectl.py TARGET click/check/uncheck/highlight SELECTOR
chromectl.py TARGET submit/clear FORM
chromectl.py TARGET type SELECTOR TEXT
chromectl.py TARGET select SELECTOR VALUE
chromectl.py TARGET get-text/get-html/get-value/exists/count/get-texts SELECTOR
chromectl.py TARGET get-attr SELECTOR ATTR
chromectl.py TARGET scroll-to/wait-for/wait-hidden SELECTOR
chromectl.py TARGET wait-text SELECTOR TEXT
chromectl.py TARGET navigate URL
chromectl.py TARGET wait-url PATTERN
chromectl.py TARGET scroll-up/scroll-down [PIXELS]
chromectl.py TARGET scroll-by X Y
chromectl.py TARGET inject-css CSS
chromectl.py TARGET reload/back/forward/get-title/get-url/scroll-top/scroll-bottom
```

Wait commands accept `--timeout N` (default 10s).

**Examples:**
```bash
./chromectl.py $ID click "button.submit"
./chromectl.py $ID type "input[name=q]" "search query"
./chromectl.py $ID get-text ".result-count"
./chromectl.py $ID wait-for ".loaded" --timeout 30
./chromectl.py $ID scroll-down 500
./chromectl.py $ID navigate "https://example.com"
```

## Workflows

### Daemon Mode (typical)

```bash
# 1. Start daemon (connects to running Chrome)
./chromectl.py start

# 2. Find or open target
./chromectl.py list
TARGET=$(./chromectl.py open https://myapp.com | jq -r .id)

# 3. Monitor + inspect
./chromectl.py $TARGET console-tail --for 60 &
./chromectl.py $TARGET screenshot -o initial.png
./chromectl.py $TARGET get-text ".status"

# 4. Stop
./chromectl.py stop
```

### Multiple Targets

```bash
ID1=$(./chromectl.py open https://page1.com | jq -r .id)
ID2=$(./chromectl.py open https://page2.com | jq -r .id)

./chromectl.py $ID1 screenshot -o page1.png
./chromectl.py $ID2 screenshot -o page2.png
```

## Legacy Mode

Launch a separate Chrome instance with full CDP access (HTTP discovery, direct page WebSocket, worker attachment). Uses an isolated profile — no access to existing cookies or sessions.

```bash
./chromectl.py launch [--headless]
```

**Options:**
- `--headless` — Run in headless mode
- `--port PORT` — Remote debugging port (default: 9222)
- `--chrome-app NAME` — macOS app name (default: "Google Chrome")
- `--user-data-dir PATH` — Custom profile directory (default: ~/chromectl-profile)

```bash
./chromectl.py launch --headless
TARGET=$(./chromectl.py open https://example.com | jq -r .id)
./chromectl.py $TARGET eval "document.title"
./chromectl.py $TARGET screenshot -o page.png
./chromectl.py stop
```

## Troubleshooting

**Daemon won't connect:**
1. Check Chrome remote debugging is enabled: `chrome://inspect/#remote-debugging`
2. Check `DevToolsActivePort` exists: `ls ~/Library/Application\ Support/Google/Chrome/DevToolsActivePort`
3. If Chrome was restarted, the permission dialog appears again — click Allow

**"Target not found":**
- Tab was closed or ID is incorrect
- Run `./chromectl.py list` to get current IDs

**Daemon died unexpectedly:**
- Chrome closed or went to sleep — restart with `./chromectl.py start`
- Check if socket exists: `ls /tmp/chromectl-$(id -u).sock`

**Legacy mode — port already in use:**
- Another Chrome instance using the port
- Use different port: `./chromectl.py launch --port 9223`

## Socket Protocol

The daemon accepts one JSON command per connection (request-response, then close):

```bash
echo '{"cmd":"list"}' | nc -U /tmp/chromectl-$(id -u).sock
echo '{"cmd":"eval","id":"TARGET_ID","expr":"document.title"}' | nc -U /tmp/chromectl-$(id -u).sock
echo '{"cmd":"screenshot","id":"TARGET_ID","output":"shot.png"}' | nc -U /tmp/chromectl-$(id -u).sock
echo '{"cmd":"cdp","method":"Browser.getVersion"}' | nc -U /tmp/chromectl-$(id -u).sock
echo '{"cmd":"quit"}' | nc -U /tmp/chromectl-$(id -u).sock
```

## Technical Details

- **Protocol:** Chrome DevTools Protocol (CDP) over WebSocket
- **Connection:** Single browser-level WebSocket, flat session multiplexing per page
- **Port:** 9222 (default), configurable
- **Socket:** `/tmp/chromectl-<uid>.sock` (daemon mode)
- **Dependencies:** aiohttp (auto-installed by uv)
- **Platform:** macOS or Linux (Unix socket requires POSIX)
