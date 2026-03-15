# chromectl — Chrome DevTools Protocol CLI

A single-file Python CLI for controlling Chrome via the Chrome DevTools Protocol (CDP). Works with **Chrome M144+** where traditional `--remote-debugging-port` on the default profile is blocked.

Built for two audiences:
- **Claude Code skill** — Claude automatically debugs web apps through your real browser session
- **Standalone CLI** — command-line Chrome automation via `chromectl.py`

## Why this exists

Chrome 136–146 progressively locked down remote debugging on the default profile to prevent cookie theft. The traditional approach — launching Chrome with `--remote-debugging-port` and a separate `--user-data-dir` — still works but requires a separate profile (no cookies, no logins, no extensions).

Chrome M144 introduced an alternative: enable remote debugging from inside a running browser via `chrome://inspect/#remote-debugging`. This enables CDP access to **your existing session** — all profiles, all cookies, all logged-in sites. The tradeoff: each new WebSocket connection triggers a permission dialog.

chromectl handles both modes:
- **Auto-connect** (M144+): connects to your running Chrome via `DevToolsActivePort`, daemon keeps one connection alive to avoid repeated permission prompts
- **Traditional**: launches a separate Chrome instance with `--remote-debugging-port` (full CDP, separate profile)

## Quick start: auto-connect to your Chrome

### 1. Enable remote debugging in Chrome

Open `chrome://inspect/#remote-debugging` and toggle the switch on. This applies to all profiles. Chrome starts listening on a local port and writes a `DevToolsActivePort` file.

### 2. Start the daemon

```bash
scripts/chromectl.py --auto-connect daemon
```

Chrome will show a permission dialog — click Allow. The daemon keeps this connection alive on a Unix socket (`/tmp/chromectl-<uid>.sock`). It shuts down automatically after 5 minutes of inactivity or when Chrome closes.

### 3. Use it

```bash
# List all open tabs
scripts/chromectl.py send list

# Run JavaScript in a tab
scripts/chromectl.py send eval --id <target-id> -e "document.title"

# Take a screenshot
scripts/chromectl.py send screenshot --id <target-id> -o page.png

# Or use netcat directly
echo '{"cmd":"list"}' | nc -U /tmp/chromectl-501.sock
```

### 4. Stop

```bash
scripts/chromectl.py stop
```

## Quick start: traditional mode (separate profile)

If you need full CDP access (HTTP discovery, direct page WebSocket, worker attachment) or don't want to touch your default Chrome:

```bash
# Launch Chrome with a separate profile
scripts/chromectl.py start --headless

# Use commands directly (no daemon needed)
TARGET=$(scripts/chromectl.py open https://example.com | jq -r .id)
scripts/chromectl.py eval --id $TARGET -e "document.title"
scripts/chromectl.py screenshot --id $TARGET -o page.png

scripts/chromectl.py stop
```

## Install as Claude Code skill

```bash
cd ~/.claude/skills
git clone https://github.com/<you>/chromectl.git chrome-debug
```

Restart Claude Code. The skill activates when you ask Claude to debug web apps, take screenshots, or inspect console output.

## What you can do through the daemon

Once connected to your running Chrome:

- **List tabs** across all windows and profiles
- **Run JavaScript** in any tab (inspect DOM, call functions, read page state)
- **Take screenshots** (viewport or full-page)
- **Monitor console** output (errors, warnings, logs) for a duration
- **Open new tabs** with a URL
- **Raw CDP commands** for anything not covered above

## What you can't do (M144+ limitations)

- **No HTTP discovery API** — `/json`, `/json/version` return 404. The daemon uses `Target.getTargets()` over WebSocket instead.
- **No direct page WebSocket** — `ws://.../devtools/page/<id>` returns 403. All page interaction goes through flat sessions multiplexed over the browser WebSocket.
- **Permission dialog on reconnect** — if the daemon's connection drops (Chrome restart, sleep/wake), reconnecting requires a new manual approval in Chrome.
- **Worker attachment unstable** — attaching to service worker targets can crash the WebSocket connection. This is a [known Chrome bug](https://github.com/nicedoc/chrome-devtools-mcp/issues/1173), not intentional.

Traditional mode (`start`/`stop`) has none of these limitations — it uses a separate profile with full CDP access.

## Commands

| Command | Mode | Description |
|---------|------|-------------|
| `--auto-connect daemon` | auto | Start daemon, connect to running Chrome |
| `send <cmd> [opts]` | auto | Send one command to running daemon |
| `start [--headless]` | trad | Launch Chrome with separate profile |
| `stop` | both | Stop daemon (if running) and chromectl Chrome instances |
| `list` | both | List open tabs/targets |
| `open <url>` | both | Open a new tab |
| `eval --id <id> -e <expr>` | both | Run JavaScript in a tab |
| `screenshot --id <id> [-o file]` | both | Capture PNG screenshot |
| `console-tail --id <id> [--for N]` | both | Stream console messages |

### Daemon socket protocol

The daemon accepts JSON commands over its Unix socket, one per line:

```bash
echo '{"cmd":"list"}' | nc -U /tmp/chromectl-501.sock
echo '{"cmd":"eval","id":"TARGET_ID","expr":"document.title"}' | nc -U /tmp/chromectl-501.sock
echo '{"cmd":"screenshot","id":"TARGET_ID","output":"shot.png"}' | nc -U /tmp/chromectl-501.sock
echo '{"cmd":"quit"}' | nc -U /tmp/chromectl-501.sock
```

### chromectl_daemon.py — Python library

For scripts that need daemon access programmatically:

```python
from chromectl_daemon import daemon_context, send_command

# Context manager: starts daemon if needed, stops on exit
async with daemon_context() as socket_path:
    result = await send_command({"cmd": "list"}, socket_path)
    for tab in result["targets"]:
        print(tab["title"])
```

## How it works

```
                  ┌─────────────────────────────┐
                  │  Chrome (user's session)     │
                  │  chrome://inspect enabled    │
                  └──────────┬──────────────────┘
                             │ WebSocket (one persistent connection)
                  ┌──────────┴──────────────────┐
                  │  chromectl daemon            │
                  │  PID file + Unix socket      │
                  │  auto-reconnect on WS drop   │
                  │  idle shutdown after 5 min   │
                  └──────────┬──────────────────┘
                             │ JSON line protocol
              ┌──────────────┼──────────────────┐
              │              │                   │
          nc -U sock    chromectl send      Python script
                                          (chromectl_daemon.py)
```

**Flat sessions**: Chrome M144+ blocks direct page WebSocket URLs. The daemon maintains a single browser-level WebSocket and multiplexes page sessions using `Target.attachToTarget` with `flatten=true`. Each page gets a `sessionId`; CDP commands and events are routed by this ID over the shared connection.

## Requirements

- **Python 3.11+**
- **[uv](https://github.com/astral-sh/uv)** (the script's shebang uses `uv run`)
- **Google Chrome** (M144+ for auto-connect, any version for traditional mode)
- **macOS** for `start`/`stop` commands (auto-connect mode works on any platform)

## Fork history

Forked from [pengelbrecht/chrome-debug-skill](https://github.com/pengelbrecht/chrome-debug-skill). Additions: M144+ auto-connect, daemon mode, flat session multiplexing, reconnect handling, liveness probes.

## License

MIT
