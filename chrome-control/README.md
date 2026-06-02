# Chrome Control

Control Chrome programmatically via CDP (Chrome DevTools Protocol). That is the same protocol that powers Chrome's built-in DevTools (F12). Inspect pages, run JavaScript, take screenshots, and monitor console output across all your tabs, cookies, and logged-in sessions.

Built for two audiences:
- **Skill**: Use your LLM to debug web apps through your real browser session with Claude or other skillful LLM
- **Standalone CLI**: Use for command-line script automation via `chromectl.py`

## What You Can Do

Once connected to your running Chrome:

- **List tabs** across all windows and profiles
- **Open new tabs** with a URL
- **Run JavaScript** in any tab (inspect DOM, call functions, read page state)
- **Take screenshots** (viewport or full-page)
- **Monitor console** output (errors, warnings, logs) for a duration
- **DOM helpers** — click, type, get-text, get-html, exists, count, scroll, wait, and more
- **Raw CDP** — send any Chrome DevTools Protocol command directly

JavaScript evaluation is the universal tool — anything you can do in the DevTools console, you can do via `eval`:

```bash
# Extract structured data
./chromectl.py $ID eval "({title: document.title, url: location.href})"

# Await async operations (top-level await supported)
./chromectl.py $ID eval "await fetch('/api/data').then(r => r.json())"
```

(`$ID` is a target ID from `./chromectl.py list` output. Prefix match OK — e.g. `88FA` instead of full ID.)

## What You Can't Do

Chrome M144+ limitations:

- **No HTTP discovery API** — `/json`, `/json/version` return 404. chromectl uses `Target.getTargets()` over WebSocket instead.
- **No direct page WebSocket** — `ws://.../devtools/page/<id>` returns 403. All page interaction goes through flat sessions multiplexed over the browser WebSocket.
- **Permission dialog on reconnect** — if the connection drops (Chrome restart, sleep/wake), reconnecting requires a new manual approval in Chrome.
- **Worker attachment unstable** — attaching to service worker targets can crash the WebSocket connection. This is a known Chrome bug, not intentional.

Legacy mode (`launch`) has none of these limitations — it uses a separate profile with full CDP access.

## Install

### Claude Code

```bash
claude plugin marketplace add vre/flow-state
claude plugin install chrome-control@flow-state
```

### Other Coding Agents

Tell your LLM to install the skill from `https://github.com/vre/flow-state/chrome-control`

### Standalone CLI

```bash
cd flow-state/chrome-control
chmod +x chromectl.py
./chromectl.py start
```

Requires [uv](https://github.com/astral-sh/uv) — the script's shebang handles dependencies automatically.

## Usage

### 1. Enable remote debugging in Chrome

Open `chrome://inspect/#remote-debugging` and toggle the switch on. This applies to all profiles simultaneously. Chrome starts listening on a local port and writes a `DevToolsActivePort` file.

### 2. Start chromectl

```bash
./chromectl.py start
```

Chrome will show a permission dialog, click Allow. chromectl keeps this connection alive on a Unix socket (`/tmp/chromectl-<uid>.sock`). It shuts down automatically after 5 minutes of inactivity or when Chrome closes.

### 3. Use it

```bash
# List all open tabs
./chromectl.py list

# Open a new tab
./chromectl.py open https://example.com

# Check daemon status
./chromectl.py status

# Run JavaScript in a tab (use target ID from list output)
./chromectl.py TARGET eval "document.title"

# Take a screenshot
./chromectl.py TARGET screenshot -o page.png

# Monitor console output
./chromectl.py TARGET console-tail --for 30

# DOM helpers
./chromectl.py TARGET click "button.submit"
./chromectl.py TARGET get-text h1
./chromectl.py TARGET type "input[name=q]" "search term"

# JSON output for scripting
./chromectl.py --json list

# Or use netcat directly
echo '{"cmd":"list"}' | nc -U /tmp/chromectl-$(id -u).sock
```

### 4. Stop

```bash
./chromectl.py stop
```

### Raw CDP

```bash
./chromectl.py cdp Browser.getVersion
./chromectl.py cdp Target.getTargets
```

## How It Works

```
                  ┌──────────────────────────────┐
                  │  Chrome (user's session)     │
                  │  chrome://inspect enabled    │
                  └──────────┬───────────────────┘
                             │ WebSocket (one persistent connection)
                  ┌──────────┴───────────────────┐
                  │  chromectl daemon            │
                  │  Unix socket + auto-reconnect│
                  │  idle shutdown after 5 min   │
                  └──────────┬───────────────────┘
                             │ JSON line protocol
              ┌──────────────┼───────────────────┐
              │              │                   │
          nc -U sock    chromectl CLI      Python script
                                          (chromectl_daemon.py)
```

**Flat sessions**: Chrome M144+ blocks direct page WebSocket URLs. chromectl maintains a single browser-level WebSocket and multiplexes page sessions using `Target.attachToTarget` with `flatten=true`. Each page gets a `sessionId`; CDP commands and events are routed by this ID over the shared connection.

## Commands

### Global

| Command | Description |
|---------|-------------|
| `start` | Connect to running Chrome, listen on Unix socket |
| `stop` | Stop daemon and any launched Chrome instances |
| `list` | List open tabs |
| `open <url>` | Open a new tab |
| `status` | Show daemon connection status |
| `targets` | List all targets (pages, workers, iframes) |
| `helpers` | List all DOM helper commands |
| `cdp <method> [--params JSON]` | Send raw CDP command (browser-level) |
| `launch [--headless]` | Launch a separate Chrome instance (legacy) |

### Target

All target commands: `chromectl.py TARGET COMMAND [ARGS]`

Target ID from `list`/`open` output. Prefix match OK (e.g. `88FA` instead of full 32-char ID).

| Command | Description |
|---------|-------------|
| `TARGET eval <expr>` | Run JavaScript in a tab |
| `TARGET screenshot [-o file] [--full-page]` | Capture PNG screenshot |
| `TARGET console-tail [--for N]` | Stream console messages |
| `TARGET navigate <url>` | Navigate to URL |
| `TARGET reload` | Reload page |
| `TARGET click <sel>` | Click element |
| `TARGET type <sel> <text>` | Type text into input |
| `TARGET get-text <sel>` | Get text content |
| `TARGET exists <sel>` | Check if element exists |
| `TARGET wait-for <sel> [--timeout N]` | Wait for element to appear |
| `TARGET scroll-to <sel>` | Scroll element into view |

30+ DOM helpers available — run `chromectl.py helpers` for the full list.

### Flags

| Flag | Description |
|------|-------------|
| `--json` | Output raw JSON instead of human-readable format |

### Socket Protocol

chromectl accepts JSON commands over its Unix socket, one per line. Socket always returns JSON regardless of `--json` flag.

```bash
echo '{"cmd":"list"}' | nc -U /tmp/chromectl-$(id -u).sock
echo '{"cmd":"open","url":"https://example.com"}' | nc -U /tmp/chromectl-$(id -u).sock
echo '{"cmd":"status"}' | nc -U /tmp/chromectl-$(id -u).sock
echo '{"cmd":"targets"}' | nc -U /tmp/chromectl-$(id -u).sock
echo '{"cmd":"eval","id":"TARGET_ID","expr":"document.title"}' | nc -U /tmp/chromectl-$(id -u).sock
echo '{"cmd":"console-tail","id":"TARGET_ID","for":10}' | nc -U /tmp/chromectl-$(id -u).sock
echo '{"cmd":"screenshot","id":"TARGET_ID","output":"shot.png"}' | nc -U /tmp/chromectl-$(id -u).sock
echo '{"cmd":"quit"}' | nc -U /tmp/chromectl-$(id -u).sock
```

### Python Library

For scripts that need chromectl access programmatically:

```python
from chromectl_daemon import daemon_context, send_command, ensure_daemon_running

async with daemon_context() as socket_path:
    result = await send_command({"cmd": "list"}, socket_path)
    for target in result["targets"]:
        print(target["title"])

# Or for mid-run recovery (starts daemon if needed, idempotent):
socket_path = await ensure_daemon_running()
```

## Legacy Mode

If you need full CDP access (HTTP discovery, direct page WebSocket, worker attachment) or don't want to touch your default Chrome, launch a separate instance:

```bash
./chromectl.py launch --headless
TARGET=$(./chromectl.py --json open https://example.com | jq -r .id)
./chromectl.py $TARGET eval "document.title"
./chromectl.py $TARGET screenshot -o page.png
./chromectl.py stop
```

## Requirements

- **Python 3.11+**
- **[uv](https://github.com/astral-sh/uv)** (the script's shebang uses `uv run`)
- **Google Chrome** (Chrome M144+ for auto-connect, any version for legacy mode)
- **macOS or Linux** (Unix socket requires POSIX)

## Why This Exists

Chrome M136 (April 2025) through M146 progressively locked down remote debugging on the default profile to prevent cookie theft. The traditional approach of launching Chrome with `--remote-debugging-port` and a separate `--user-data-dir` still works but requires a separate profile (no cookies, no logins, no extensions).

Chrome M144 (January 2026) introduced an alternative: enable remote debugging from inside a running browser via `chrome://inspect/#remote-debugging`. This enables CDP access to **your existing session** with all profiles, all cookies, all logged-in sites. The tradeoff is that each new WebSocket connection triggers a permission dialog.

chrome-control handles both modes:

- **Auto-connect** (Chrome M144+): connects to your running Chrome via `DevToolsActivePort`, keeps one persistent connection to avoid repeated permission prompts
- **Legacy** (`launch`): starts a separate Chrome instance with full CDP access and a separate profile

## Release Highlights

- **v1.0.0** — Chrome DevTools Protocol CLI and skill
  - Auto-connect to your running Chrome (M144+), no separate profile needed
  - Daemon mode with persistent WebSocket and Unix socket interface
  - 30+ DOM helper commands: click, type, get-text, exists, wait-for, scroll, and more
  - Forked base from [pengelbrecht/chrome-debug-skill](https://github.com/pengelbrecht/chrome-debug-skill)

## Fork History

Forked from [pengelbrecht/chrome-debug-skill](https://github.com/pengelbrecht/chrome-debug-skill). Additions: Chrome M144+ auto-connect, daemon mode, flat session multiplexing, reconnect handling, liveness probes, 30+ DOM helpers.

## License

MIT, See [LICENSE](LICENSE) for more information.
