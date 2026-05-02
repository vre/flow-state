# chrome-control — CLI and Skill to Control Chrome over DevTools Protocol

Control Chrome programmatically via CDP (Chrome DevTools Protocol) — the same protocol that powers Chrome's built-in DevTools (F12). Inspect pages, run JavaScript, take screenshots, and monitor console output across all your tabs, cookies, and logged-in sessions.

Built for two audiences:
- **Claude Code skill** — Claude debugs web apps through your real browser session
- **Standalone CLI** — command-line Chrome automation via `chromectl.py`

## Why this exists

Chrome 136–146 progressively locked down remote debugging on the default profile to prevent cookie theft. The traditional approach — launching Chrome with `--remote-debugging-port` and a separate `--user-data-dir` — still works but requires a separate profile (no cookies, no logins, no extensions).

Chrome 144 (November 2025) introduced an alternative: enable remote debugging from inside a running browser via `chrome://inspect/#remote-debugging`. This enables CDP access to **your existing session** — all profiles, all cookies, all logged-in sites. The tradeoff: each new WebSocket connection triggers a permission dialog.

chrome-control handles both modes:
- **Auto-connect** (Chrome 144+): connects to your running Chrome via `DevToolsActivePort`, keeps one persistent connection to avoid repeated permission prompts
- **Legacy** (`launch`): starts a separate Chrome instance with full CDP access and a separate profile

## Quick start

### 1. Enable remote debugging in Chrome

Open `chrome://inspect/#remote-debugging` and toggle the switch on. This applies to all profiles. Chrome starts listening on a local port and writes a `DevToolsActivePort` file.

### 2. Start chromectl

```bash
./chromectl.py start
```

(Requires [uv](https://github.com/astral-sh/uv) — the script's shebang handles dependencies automatically.)

Chrome will show a permission dialog — click Allow. chromectl keeps this connection alive on a Unix socket (`/tmp/chromectl-<uid>.sock`). It shuts down automatically after 5 minutes of inactivity or when Chrome closes.

### 3. Use it

```bash
# List all open tabs
./chromectl.py send list

# Run JavaScript in a tab (use target ID from list output)
./chromectl.py send eval --id <target-id> -e "document.title"

# Take a screenshot
./chromectl.py send screenshot --id <target-id> -o page.png

# Or use netcat directly
echo '{"cmd":"list"}' | nc -U /tmp/chromectl-$(id -u).sock
```

### 4. Stop

```bash
./chromectl.py stop
```

## What you can do

Once connected to your running Chrome:

- **List tabs** across all windows and profiles
- **Run JavaScript** in any tab (inspect DOM, call functions, read page state)
- **Take screenshots** (viewport or full-page)
- **Monitor console** output (errors, warnings, logs) for a duration
- **Open new tabs** with a URL

JavaScript evaluation is the universal tool — anything you can do in the DevTools console, you can do via `eval`:

```bash
# Click a button
./chromectl.py send eval --id $ID -e "document.querySelector('button#submit').click()"

# Navigate
./chromectl.py send eval --id $ID -e "window.location.href = 'https://example.com'"

# Extract structured data
./chromectl.py send eval --id $ID -e "({title: document.title, url: location.href})"

# Await async operations
./chromectl.py send eval --id $ID -e "fetch('/api/data').then(r => r.json())"
```

(`$ID` is a target ID from `./chromectl.py send list` output.)

## What you can't do (Chrome 144+ limitations)

- **No HTTP discovery API** — `/json`, `/json/version` return 404. chromectl uses `Target.getTargets()` over WebSocket instead.
- **No direct page WebSocket** — `ws://.../devtools/page/<id>` returns 403. All page interaction goes through flat sessions multiplexed over the browser WebSocket.
- **Permission dialog on reconnect** — if the connection drops (Chrome restart, sleep/wake), reconnecting requires a new manual approval in Chrome.
- **Worker attachment unstable** — attaching to service worker targets can crash the WebSocket connection. This is a known Chrome bug, not intentional.

Legacy mode (`launch`) has none of these limitations — it uses a separate profile with full CDP access.

## How it works

```
                  ┌─────────────────────────────┐
                  │  Chrome (user's session)     │
                  │  chrome://inspect enabled    │
                  └──────────┬──────────────────┘
                             │ WebSocket (one persistent connection)
                  ┌──────────┴──────────────────┐
                  │  chromectl daemon            │
                  │  Unix socket + auto-reconnect│
                  │  idle shutdown after 5 min   │
                  └──────────┬──────────────────┘
                             │ JSON line protocol
              ┌──────────────┼──────────────────┐
              │              │                   │
          nc -U sock    chromectl send      Python script
                                          (chromectl_daemon.py)
```

**Flat sessions**: Chrome 144+ blocks direct page WebSocket URLs. chromectl maintains a single browser-level WebSocket and multiplexes page sessions using `Target.attachToTarget` with `flatten=true`. Each page gets a `sessionId`; CDP commands and events are routed by this ID over the shared connection.

## Install

### Claude Code (marketplace)

```bash
/plugin install chrome-control@vre
```

### Clone manually

```bash
git clone https://github.com/vre/chrome-control.git
cd chrome-control
chmod +x chromectl.py
```

For Claude Code skill use, clone into `~/.claude/skills/` and restart Claude Code.

## Commands

| Command | Description |
|---------|-------------|
| `start` | Connect to running Chrome, listen on Unix socket |
| `stop` | Stop daemon and any launched Chrome instances |
| `send <cmd>` | Send a command to the running daemon |
| `send list` | List open tabs/targets |
| `send open <url>` | Open a new tab |
| `send eval --id <id> -e <expr>` | Run JavaScript in a tab |
| `send screenshot --id <id> [-o file]` | Capture PNG screenshot |
| `send console-tail --id <id> [--for N]` | Stream console messages |
| `launch [--headless]` | Launch a separate Chrome instance (legacy) |

### Socket protocol

chromectl accepts JSON commands over its Unix socket, one per line:

```bash
echo '{"cmd":"list"}' | nc -U /tmp/chromectl-$(id -u).sock
echo '{"cmd":"eval","id":"TARGET_ID","expr":"document.title"}' | nc -U /tmp/chromectl-$(id -u).sock
echo '{"cmd":"screenshot","id":"TARGET_ID","output":"shot.png"}' | nc -U /tmp/chromectl-$(id -u).sock
echo '{"cmd":"quit"}' | nc -U /tmp/chromectl-$(id -u).sock
```

### chromectl_daemon.py — Python library

For scripts that need chromectl access programmatically:

```python
from chromectl_daemon import daemon_context, send_command

async with daemon_context() as socket_path:
    result = await send_command({"cmd": "list"}, socket_path)
    for tab in result["targets"]:
        print(tab["title"])
```

## Legacy mode

If you need full CDP access (HTTP discovery, direct page WebSocket, worker attachment) or don't want to touch your default Chrome, launch a separate instance:

```bash
./chromectl.py launch --headless
TARGET=$(./chromectl.py open https://example.com | jq -r .id)
./chromectl.py eval --id $TARGET -e "document.title"
./chromectl.py screenshot --id $TARGET -o page.png
./chromectl.py stop
```

## Requirements

- **Python 3.11+**
- **[uv](https://github.com/astral-sh/uv)** (the script's shebang uses `uv run`)
- **Google Chrome** (Chrome 144+ for auto-connect, any version for legacy mode)
- **macOS or Linux** (Unix socket requires POSIX)

## Fork history

Forked from [pengelbrecht/chrome-debug-skill](https://github.com/pengelbrecht/chrome-debug-skill). Additions: Chrome 144+ auto-connect, daemon mode, flat session multiplexing, reconnect handling, liveness probes.

## License

MIT
