# Firefox Control

Control Firefox via [WebDriver BiDi](https://www.w3.org/TR/webdriver-bidi/) from the command line. Python CLI, no geckodriver, direct WebSocket to Firefox's native BiDi implementation.

**Test tool** — Firefox sets `navigator.webdriver=true` on any remote debugging session. Every anti-bot system detects this. For production agent workflows, use Chrome CDP tooling instead.

## What You Can Do

Once connected to Firefox:

- **List tabs** — all open browsing contexts
- **Open new tabs** with a URL
- **Run JavaScript** in any tab (DOM inspection, function calls, page state)
- **Take screenshots** — viewport PNG capture
- **Monitor console** output (errors, warnings, logs) for a duration
- **DOM helpers** — click, type, get-text, exists, count, scroll, wait, and more
- **Raw BiDi** — send any WebDriver BiDi command directly

JavaScript evaluation covers anything the DOM helpers don't:

```bash
# Extract structured data
./firefoxctl.py CONTEXT eval "({title: document.title, url: location.href})"

# Await async operations (top-level await supported)
./firefoxctl.py CONTEXT eval "await fetch('/api').then(r => r.json())"
```

## What You Can't Do

Firefox made three decisions that kill it for agent browser automation:

1. **`navigator.webdriver = true`** — Firefox sets this flag on any remote debugging session ([Bug 1719505](https://bugzilla.mozilla.org/show_bug.cgi?id=1719505), Firefox 101+). Every anti-bot system checks this. Chrome CDP does not set it.

2. **No extension-based automation** — Chrome has `chrome.debugger`, which lets extensions get full CDP access without opening a debug port. Firefox has no equivalent API — no `browser.debugger`, nothing.

3. **Launch-time only** — `--remote-debugging-port` must be set when Firefox starts. Chrome M144+ lets you enable debugging at runtime via `chrome://inspect/#remote-debugging`. Firefox has no runtime toggle.

The BiDi protocol itself is solid — W3C standard, clean WebSocket API, native Firefox implementation with no intermediary. Mozilla just surrounded it with restrictions that make it useless for the "automate your real browser" use case that agents need.

## Install

### Claude Code

```bash
claude plugin marketplace add vre/flow-state
claude plugin install firefox-control@flow-state
```

### Other Coding Agents

Tell your LLM to install the skill from `https://github.com/vre/flow-state/firefox-control`

### Standalone CLI

```bash
cd flow-state/firefox-control
chmod +x firefoxctl.py
./firefoxctl.py --help
```

Requires [uv](https://github.com/astral-sh/uv) — the script's shebang handles dependencies automatically.

## Usage

### 1. Launch Firefox with remote debugging

```bash
firefox --remote-debugging-port 9223
```

### 2. Use it

The daemon starts automatically on first command. No explicit `start` needed.

```bash
# If port differs from default (9222):
./firefoxctl.py --port 9223 list
```

The daemon holds the BiDi WebSocket open so each CLI call is instant — no connection overhead per command. Each CLI invocation sends one request to the daemon via Unix socket and exits; the caller holds no persistent state. The daemon shuts down after 5 minutes of inactivity. Socket: `/tmp/firefoxctl-<uid>.sock`. You can also start it explicitly with `./firefoxctl.py start`.

### 3. Commands

```bash
# List open tabs
./firefoxctl.py list

# Open a new tab
./firefoxctl.py open https://example.com

# Check daemon status
./firefoxctl.py status

# Run JavaScript (use context ID from list output)
./firefoxctl.py CONTEXT eval "document.title"

# Take a screenshot
./firefoxctl.py CONTEXT screenshot -o page.png

# Monitor console output
./firefoxctl.py CONTEXT console-tail --for 30

# DOM helpers
./firefoxctl.py CONTEXT click "button.submit"
./firefoxctl.py CONTEXT get-text h1
./firefoxctl.py CONTEXT type "input[name=q]" "search term"

# JSON output for scripting
./firefoxctl.py --json list

# Or use netcat directly
echo '{"cmd":"list"}' | nc -U /tmp/firefoxctl-$(id -u).sock
```

### 4. Stop

```bash
./firefoxctl.py stop
```

### Raw BiDi

```bash
./firefoxctl.py bidi browser.getClientWindows
./firefoxctl.py bidi session.status
```

## How It Works

```
Firefox (--remote-debugging-port 9223)
  └── BiDi WebSocket: ws://127.0.0.1:9223/session
        ↕
firefoxctl daemon (Unix socket: /tmp/firefoxctl-{uid}.sock)
        ↕
firefoxctl CLI / LLM agent / echo '{"cmd":"list"}' | nc -U <socket>
```

- **Protocol**: WebDriver BiDi (W3C standard) over WebSocket
- **Connection**: direct to Firefox, no geckodriver, no Selenium, no Puppeteer
- **Daemon**: persistent BiDi session, stable context IDs, idle timeout (5 min), clean shutdown (session.end)
- **CLI**: human-readable by default, `--json` for machine-parseable output

## Commands

### Global

| Command | Description |
|---------|-------------|
| `start` | Connect to Firefox BiDi, listen on Unix socket |
| `stop` | Stop daemon |
| `list` | List open tabs |
| `open <url>` | Open a new tab |
| `status` | Show daemon connection status |
| `targets` | List all targets (tabs, iframes) |
| `helpers` | List all DOM helper commands |
| `bidi <method> [--params JSON]` | Send raw BiDi command |

### Target

All target commands: `firefoxctl.py CONTEXT COMMAND [ARGS]`

Context ID from `list` output (full UUID required — no prefix match).

| Command | Description |
|---------|-------------|
| `CONTEXT eval <expr>` | Run JavaScript in a context |
| `CONTEXT screenshot [-o file]` | Capture viewport PNG screenshot |
| `CONTEXT console-tail [--for N]` | Stream console messages |
| `CONTEXT navigate <url>` | Navigate to URL |
| `CONTEXT reload` | Reload page |
| `CONTEXT click <sel>` | Click element |
| `CONTEXT type <sel> <text>` | Type text into input |
| `CONTEXT get-text <sel>` | Get text content |
| `CONTEXT exists <sel>` | Check if element exists |
| `CONTEXT wait-for <sel> [--timeout N]` | Wait for element to appear |
| `CONTEXT scroll-to <sel>` | Scroll element into view |

30+ DOM helpers available — run `firefoxctl.py helpers` for the full list.

### Flags

| Flag | Description |
|------|-------------|
| `--json` | Output raw JSON instead of human-readable format |
| `--port N` | Firefox remote debugging port (default: 9222) |

### Socket Protocol

firefoxctl accepts JSON commands over its Unix socket, one per line. Socket always returns JSON regardless of `--json` flag.

```bash
echo '{"cmd":"list"}' | nc -U /tmp/firefoxctl-$(id -u).sock
echo '{"cmd":"open","url":"https://example.com"}' | nc -U /tmp/firefoxctl-$(id -u).sock
echo '{"cmd":"status"}' | nc -U /tmp/firefoxctl-$(id -u).sock
echo '{"cmd":"targets"}' | nc -U /tmp/firefoxctl-$(id -u).sock
echo '{"cmd":"eval","context":"CONTEXT_ID","expr":"document.title"}' | nc -U /tmp/firefoxctl-$(id -u).sock
echo '{"cmd":"console-tail","context":"CONTEXT_ID","for":10}' | nc -U /tmp/firefoxctl-$(id -u).sock
echo '{"cmd":"screenshot","context":"CONTEXT_ID","output":"page.png"}' | nc -U /tmp/firefoxctl-$(id -u).sock
echo '{"cmd":"quit"}' | nc -U /tmp/firefoxctl-$(id -u).sock
```

### Python Library

For scripts that need firefoxctl access programmatically:

```python
from firefoxctl_daemon import daemon_context, send_command, ensure_daemon_running

async with daemon_context(port=9223) as socket_path:
    result = await send_command({"cmd": "list"}, socket_path)
    for ctx in result["contexts"]:
        print(ctx["url"])

# Or for mid-run recovery (starts daemon if needed, idempotent):
socket_path = await ensure_daemon_running(port=9223)
```

## Requirements

- **Python 3.11+**
- **[uv](https://github.com/astral-sh/uv)** (the script's shebang uses `uv run`)
- **Mozilla Firefox** (any recent version with BiDi support)
- **macOS or Linux** (Unix socket requires POSIX)

## Why This Exists

Chrome M144+ (January 2026) introduced restrictions on remote debugging — permission dialogs on each new WebSocket connection, blocked direct page URLs, blocked HTTP discovery. We investigated Firefox as an alternative and found that Firefox had removed CDP entirely (Firefox 141+), replacing it with WebDriver BiDi.

firefoxctl validates that raw BiDi works without Selenium, geckodriver, or any intermediary. The BiDi WebSocket protocol is clean and the implementation was straightforward. But Mozilla's policy decisions — `navigator.webdriver=true`, no extension-based automation API, no runtime debug toggle — make Firefox unusable for production agent automation (see [What You Can't Do](#what-you-cant-do)).

The tool proves BiDi works. For production agent workflows, use Chrome CDP tooling instead.

## Release Highlights

- **v0.1.0** — WebDriver BiDi CLI for Firefox (test tool)
  - Direct BiDi WebSocket, daemon mode, DOM helpers
  - Proves that BiDi works and was quite easy actually to set up

## License

MIT, See [LICENSE](LICENSE) for more information.
