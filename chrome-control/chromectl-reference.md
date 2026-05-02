# chromectl Command Reference

Complete reference for `chromectl.py` — the CLI for chrome-control.

## Command Overview

**Daemon mode (Chrome 144+):**
- `start` — Connect to running Chrome, listen on Unix socket
- `stop` — Stop daemon and any launched Chrome instances
- `send <cmd>` — Send command to running daemon

**Commands** (via `send` in daemon mode, or direct in legacy mode):
- `list` — List all open tabs/targets
- `open <url>` — Open a new tab
- `eval --id <id> -e <expr>` — Execute JavaScript in a tab
- `screenshot --id <id> [-o file]` — Capture screenshot
- `console-tail --id <id> [--for N]` — Stream console messages

**Legacy mode:**
- `launch [--headless]` — Launch a separate Chrome instance with full CDP access

## Global Options

```bash
--host HOST    # CDP host (default: 127.0.0.1)
--port PORT    # CDP port (default: 9222)
```

Place global options BEFORE the command:
```bash
./chromectl.py --port 9223 send list
```

## start — Connect to Chrome

```bash
./chromectl.py start
```

Connects to your running Chrome via `DevToolsActivePort` and starts a daemon on a Unix socket (`/tmp/chromectl-<uid>.sock`). Chrome shows a permission dialog on first connect — click Allow.

The daemon keeps one persistent WebSocket connection to Chrome and multiplexes page sessions using flat sessions (`Target.attachToTarget` with `flatten=true`). This avoids repeated permission dialogs.

Auto-shuts down after 5 minutes of inactivity or when Chrome closes.

**Prerequisites:**
- Chrome Chrome 144+ with remote debugging enabled: `chrome://inspect/#remote-debugging` → toggle on
- Applies to all profiles once enabled

## stop — Stop daemon and Chrome

```bash
./chromectl.py stop
```

Sends quit to the daemon (if socket exists), then terminates any Chrome processes launched by chromectl in legacy mode (identified by chromectl profile directories).

## send — Send command to daemon

```bash
./chromectl.py send <command> [options]
```

Routes a command through the daemon's Unix socket. All commands below can be used with `send`.

## list — List Targets

```bash
./chromectl.py send list
```

Returns JSON objects (one per line) for each target:
```json
{"id": "ABC123", "type": "page", "title": "Page Title", "url": "https://...", "attached": null}
```

**Target types:** page, background_page, service_worker, iframe

## open — Open New Tab

```bash
./chromectl.py send open <url>
```

Returns JSON with target ID:
```json
{"id": "ABC123", "url": "https://example.com"}
```

**Extract target ID:**
```bash
TARGET=$(./chromectl.py send open https://example.com | jq -r .id)
```

**Supported URLs:**
- HTTP/HTTPS: `https://example.com`
- Data URLs: `data:text/html,<h1>Test</h1>`

## eval — Execute JavaScript

```bash
./chromectl.py send eval --id <target-id> -e <expression>
```

**Features:**
- Automatically awaits promises
- Returns JSON-serialized values
- REPL mode enabled

**Common patterns:**

```bash
# Page inspection
send eval --id $ID -e "document.title"
send eval --id $ID -e "window.location.href"
send eval --id $ID -e "document.readyState"

# DOM queries
send eval --id $ID -e "document.querySelector('h1').innerText"
send eval --id $ID -e "document.querySelectorAll('a').length"

# Return structured data
send eval --id $ID -e "({title: document.title, url: location.href})"

# Async operations
send eval --id $ID -e "fetch('/api/data').then(r => r.json())"

# Page interaction
send eval --id $ID -e "document.querySelector('button#submit').click()"
send eval --id $ID -e "window.scrollTo(0, document.body.scrollHeight)"

# Navigate
send eval --id $ID -e "window.location.href = 'https://example.com'"

# Check for errors
send eval --id $ID -e "window.onerror"
send eval --id $ID -e "typeof myFunction"
```

**Advanced patterns:**

```bash
# Performance timing — page load breakdown (Navigation Timing L2)
send eval --id $ID -e "
(() => { const n = performance.getEntriesByType('navigation')[0];
  return { dns: n.domainLookupEnd - n.domainLookupStart,
    tcp: n.connectEnd - n.connectStart,
    ttfb: n.responseStart - n.requestStart,
    domReady: n.domContentLoadedEventEnd - n.startTime,
    load: n.loadEventEnd - n.startTime }; })()"

# React component state (works with React 18 createRoot and 19)
send eval --id $ID -e "
(() => { const el = document.querySelector('#root') || document.querySelector('#app');
  if (!el) return 'no root element';
  const key = Object.keys(el).find(k => k.startsWith('__reactFiber$') || k.startsWith('__reactContainer$'));
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
./chromectl.py send screenshot --id <target-id> [-o output.png] [--full-page]
```

**Options:**
- `-o, --output` — Output file path (default: screenshot_<id>.png)
- `--full-page` — Capture entire scrollable page (not just viewport)

**Examples:**
```bash
./chromectl.py send screenshot --id $ID -o page.png
./chromectl.py send screenshot --id $ID -o full.png --full-page
```

## console-tail — Stream Console

```bash
./chromectl.py send console-tail --id <target-id> [--for SECONDS]
```

**Options:**
- `--for` — Duration in seconds to stream (default: 10)

**IMPORTANT:** Only captures messages logged AFTER the command starts. No historical messages.

**Output format:**
```json
{"t": "+2.011s", "console": "log", "args": ["Message text"]}
{"t": "+2.015s", "console": "warning", "args": ["Warning text"]}
{"t": "+2.020s", "console": "error", "args": ["Error message"]}
{"t": "+5.123s", "log": {"level": "error", "source": "javascript", "text": "Error details"}}
```

**Usage pattern for debugging:**
```bash
# Start monitoring in background
./chromectl.py send console-tail --id $ID --for 30 &

# Trigger actions
./chromectl.py send eval --id $ID -e "myFunction()"

# Wait for console-tail to complete
wait
```

## Workflows

### Daemon Mode (typical)

```bash
# 1. Start daemon (connects to running Chrome)
./chromectl.py start

# 2. Find or open target
./chromectl.py send list
TARGET=$(./chromectl.py send open https://myapp.com | jq -r .id)

# 3. Monitor + inspect
./chromectl.py send console-tail --id $TARGET --for 60 &
./chromectl.py send screenshot --id $TARGET -o initial.png
./chromectl.py send eval --id $TARGET -e "document.readyState"

# 4. Stop
./chromectl.py stop
```

### Multiple Targets

```bash
ID1=$(./chromectl.py send open https://page1.com | jq -r .id)
ID2=$(./chromectl.py send open https://page2.com | jq -r .id)

./chromectl.py send screenshot --id $ID1 -o page1.png
./chromectl.py send screenshot --id $ID2 -o page2.png
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

In legacy mode, commands are used directly (no `send`):

```bash
./chromectl.py launch --headless
TARGET=$(./chromectl.py open https://example.com | jq -r .id)
./chromectl.py eval --id $TARGET -e "document.title"
./chromectl.py screenshot --id $TARGET -o page.png
./chromectl.py stop
```

## Troubleshooting

**Daemon won't connect:**
1. Check Chrome remote debugging is enabled: `chrome://inspect/#remote-debugging`
2. Check `DevToolsActivePort` exists: `ls ~/Library/Application\ Support/Google/Chrome/DevToolsActivePort`
3. If Chrome was restarted, the permission dialog appears again — click Allow

**"Target not found":**
- Tab was closed or ID is incorrect
- Run `./chromectl.py send list` to get current IDs

**Daemon died unexpectedly:**
- Chrome closed or went to sleep — restart with `./chromectl.py start`
- Check if socket exists: `ls /tmp/chromectl-$(id -u).sock`

**Legacy mode — port already in use:**
- Another Chrome instance using the port
- Use different port: `./chromectl.py launch --port 9223`

## Socket Protocol

The daemon accepts JSON commands over its Unix socket, one per line:

```bash
echo '{"cmd":"list"}' | nc -U /tmp/chromectl-$(id -u).sock
echo '{"cmd":"eval","id":"TARGET_ID","expr":"document.title"}' | nc -U /tmp/chromectl-$(id -u).sock
echo '{"cmd":"screenshot","id":"TARGET_ID","output":"shot.png"}' | nc -U /tmp/chromectl-$(id -u).sock
echo '{"cmd":"quit"}' | nc -U /tmp/chromectl-$(id -u).sock
```

## Technical Details

- **Protocol:** Chrome DevTools Protocol (CDP) over WebSocket
- **Connection:** Single browser-level WebSocket, flat session multiplexing per page
- **Port:** 9222 (default), configurable
- **Socket:** `/tmp/chromectl-<uid>.sock` (daemon mode)
- **Dependencies:** aiohttp (auto-installed by uv)
- **Platform:** macOS or Linux (Unix socket requires POSIX)
