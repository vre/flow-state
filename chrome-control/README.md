# Chrome Debug Skill for Claude Code

A **Claude Code skill** and **standalone CLI tool** for controlling Chrome via the Chrome DevTools Protocol (CDP). Enables automated web app debugging, console monitoring, and screenshot capture.

Built as a single-file Python script using **uv inline dependencies** — no `requirements.txt`, no manual venv, no setup required.

**Use it as:**
- 🤖 **Claude Code Skill** - Claude automatically debugs your web apps
- 🛠️ **Standalone Tool** - Command-line Chrome automation via `chromectl.py`

## Features

- **Zero-setup**: Just run the script, uv handles all dependencies automatically
- **Browser automation**: Open tabs, evaluate JavaScript, capture screenshots
- **Console monitoring**: Stream live console messages from any tab
- **Full-page screenshots**: Capture entire pages, not just the viewport
- **Headless support**: Run Chrome in the background without a visible window

## Install as Claude Code Skill

**Want Claude to help debug your web apps automatically?** Install this as a skill for [Claude Code](https://claude.com/claude-code).

### Quick Install

```bash
cd ~/.claude/skills
git clone https://github.com/pengelbrecht/chrome-debug-skill.git chrome-debug
```

Then **restart Claude Code**.

### What does the skill do?

Once installed, Claude will automatically use this skill when you ask for help with:
- "Debug why this page isn't loading correctly"
- "Take a screenshot of https://example.com"
- "Check the console for errors on my webapp"
- "Monitor console output while I test my app"

The skill enables **collaborative debugging** where Claude can:
- Launch Chrome in visible mode (so you can interact with the page)
- Monitor console errors in real-time
- Capture screenshots to identify visual issues
- Execute JavaScript to inspect page state
- All while you navigate and test your application

See [SKILL.md](SKILL.md) for complete skill documentation and workflows.

---

## Standalone Installation (Without Claude Code)

Clone the repository and use the script directly:

```bash
git clone https://github.com/pengelbrecht/chrome-debug-skill.git
cd chrome-debug-skill
chmod +x scripts/chromectl.py
```

That's it! On first run, `uv` will automatically install the required dependency (`aiohttp`).

## Quick Start

1. **Launch Chrome with remote debugging:**
   ```bash
   scripts/chromectl.py start --headless
   ```

2. **List all open tabs:**
   ```bash
   scripts/chromectl.py list
   ```

3. **Open a new tab:**
   ```bash
   scripts/chromectl.py open https://example.com
   # Output: {"id":"ABC123...","url":"https://example.com"}
   ```

4. **Run JavaScript:**
   ```bash
   scripts/chromectl.py eval --id ABC123 -e "document.title"
   # Output: "Example Domain"
   ```

5. **Stop Chrome when done (important!):**
   ```bash
   scripts/chromectl.py stop
   ```

   **⚠️ Always run `stop` when finished** to clean up Chrome processes and allow normal Chrome to launch from Finder.

## Commands

### `start` - Launch Chrome with debugging enabled

```bash
scripts/chromectl.py start [--headless] [--port PORT] [--chrome-app NAME] [--user-data-dir PATH]
```

**Options:**
- `--headless` - Run Chrome in headless mode (no visible window)
- `--port` - Remote debugging port (default: 9222)
- `--chrome-app` - macOS app name (default: "Google Chrome")
- `--user-data-dir` - Custom profile directory (default: ~/chromectl-profile)

**Important:** Each debugging instance uses a separate profile directory, allowing you to run multiple instances simultaneously without closing your regular Chrome browser.

**Examples:**
```bash
# Headless mode (recommended for automation)
scripts/chromectl.py start --headless

# Visible Chrome window
scripts/chromectl.py start

# Use Chrome Canary
scripts/chromectl.py start --chrome-app "Google Chrome Canary"
```

---

### `stop` - Stop all chromectl-managed Chrome instances

```bash
scripts/chromectl.py stop
```

Finds and stops all Chrome instances launched by chromectl (identifies them by the chromectl profile directories).

**Why use this:**
- Cleans up background Chrome processes
- Frees up debugging ports (9222, etc.)
- Allows you to launch regular Chrome from macOS Finder
- Prevents interference with your normal Chrome usage

**Output:**
```
Stopping Chrome instance (PID: 5595)
Stopping Chrome instance (PID: 5602)
...
Stopped 8 Chrome instance(s)
```

**Important:** Always run `stop` when you're done debugging. Headless Chrome instances run invisibly in the background and can prevent normal Chrome from launching properly.

---

### `list` - List all open tabs/targets

```bash
scripts/chromectl.py list
```

Shows all available targets (tabs, extensions, service workers) with their IDs, URLs, and titles.

**Output format:** One JSON object per line
```json
{"id": "ABC123...", "type": "page", "title": "Example", "url": "https://example.com", "attached": null}
```

---

### `open` - Open a new tab

```bash
scripts/chromectl.py open <url>
```

Opens a new tab at the specified URL and returns its target ID.

**Examples:**
```bash
# Open a website
scripts/chromectl.py open https://github.com

# Open a data URL with inline HTML/JS
scripts/chromectl.py open "data:text/html,<h1>Hello</h1>"
```

**Tip:** Save the target ID for use with other commands:
```bash
TARGET=$(scripts/chromectl.py open https://example.com | jq -r .id)
scripts/chromectl.py eval --id $TARGET -e "document.title"
```

---

### `eval` - Evaluate JavaScript

```bash
scripts/chromectl.py eval --id <target-id> -e <expression>
```

Executes JavaScript in the specified tab and returns the result.

**Features:**
- Automatically awaits promises (`awaitPromise: true`)
- Returns JSON-serialized values
- REPL mode enabled for cleaner output

**Examples:**
```bash
# Get page title
scripts/chromectl.py eval --id ABC123 -e "document.title"

# Get current URL
scripts/chromectl.py eval --id ABC123 -e "window.location.href"

# Return an object
scripts/chromectl.py eval --id ABC123 -e "({title: document.title, url: location.href})"

# Async operations work automatically
scripts/chromectl.py eval --id ABC123 -e "fetch('https://api.github.com').then(r => r.json())"

# DOM manipulation
scripts/chromectl.py eval --id ABC123 -e "document.querySelector('h1').innerText"
```

---

### `screenshot` - Capture a PNG screenshot

```bash
scripts/chromectl.py screenshot --id <target-id> [-o output.png] [--full-page]
```

**Options:**
- `-o, --output` - Output file path (default: `screenshot_<id>.png`)
- `--full-page` - Capture entire page by resizing viewport to content height

**Examples:**
```bash
# Viewport screenshot (visible area only)
scripts/chromectl.py screenshot --id ABC123 -o page.png

# Full-page screenshot (entire scrollable content)
scripts/chromectl.py screenshot --id ABC123 -o fullpage.png --full-page
```

**Output:** Prints the filename when complete
```
page.png
```

---

### `console-tail` - Stream console messages

```bash
scripts/chromectl.py console-tail --id <target-id> [--for SECONDS]
```

Streams console output from the specified tab in real-time.

**Options:**
- `--for` - Duration in seconds to stream (default: 10)

**Important:** Only captures messages logged **after** the command starts. Historical console messages are not shown.

**Output format:** One JSON object per line
```json
{"t": "+2.011s", "console": "log", "args": ["Test message"]}
{"t": "+2.015s", "console": "warning", "args": ["Warning text"]}
{"t": "+2.020s", "console": "error", "args": ["Error message"]}
```

**Usage pattern:**
```bash
# Start tailing in the background
scripts/chromectl.py console-tail --id ABC123 --for 30 &

# Then interact with the page
scripts/chromectl.py eval --id ABC123 -e "console.log('Hello from eval')"
```

**Example:** Monitor a page with active logging
```bash
# Open a page that logs continuously
scripts/chromectl.py open "data:text/html,<script>setInterval(() => console.log('tick', Date.now()), 1000)</script>"

# Start monitoring (captures new messages for 10 seconds)
scripts/chromectl.py console-tail --id <target-id> --for 10
```

---

## How It Works

- **Shebang magic**: `#!/usr/bin/env -S uv run` tells your shell to execute via `uv run`
- **Inline dependencies**: The `# /// script` block (PEP 723) embeds dependency info directly in the file
- **Auto-caching**: On first run, uv resolves and caches `aiohttp` (~17ms after initial install)
- **Chrome DevTools Protocol**: Communicates with Chrome over HTTP and WebSocket on port 9222

## Tips & Tricks

### Run multiple debugging instances
You can run multiple Chrome instances simultaneously without closing your regular browser:
```bash
# Instance 1 on port 9222
scripts/chromectl.py start --headless

# Instance 2 on port 9223 (doesn't interfere with your regular Chrome)
scripts/chromectl.py start --headless --port 9223 --user-data-dir ~/chromectl-test

# Use the second instance
scripts/chromectl.py --port 9223 list
```

### Closing Chrome cleanly
```bash
# Use the built-in stop command (recommended)
scripts/chromectl.py stop

# Or manually close all Chrome instances
killall "Google Chrome"

# Or find and kill specific debugging instance by PID
ps aux | grep chromectl-profile
kill <PID>
```

### Chain commands with jq
```bash
# Open, capture ID, and screenshot in one go
TARGET=$(scripts/chromectl.py open https://github.com | jq -r .id)
scripts/chromectl.py screenshot --id $TARGET -o github.png
```

### Monitor console while running tests
```bash
# Terminal 1: Start console monitoring
scripts/chromectl.py console-tail --id ABC123 --for 60

# Terminal 2: Run your automation
scripts/chromectl.py eval --id ABC123 -e "runTests()"
```

### Debug connection issues
```bash
# Check if Chrome is listening on the debug port
lsof -i :9222

# Test HTTP endpoint directly
curl http://localhost:9222/json | jq .
```

## Troubleshooting

**"Cannot connect to host 127.0.0.1:9222"**
- No Chrome instance with remote debugging is running on that port
- Start one with: `./chromectl.py start --headless`
- If port is taken, use a different port: `./chromectl.py start --headless --port 9223`

**"Target not found"**
- The tab was closed or the ID is incorrect
- Run `./chromectl.py list` to get current target IDs

**Port already in use**
- Another Chrome instance is using port 9222
- Use `--port 9223` to specify a different port

## Requirements

- **macOS** (uses `open -a` to launch Chrome; Linux/Windows need different launch commands)
- **uv** ([Install here](https://github.com/astral-sh/uv))
- **Google Chrome** installed in `/Applications/`

## License

MIT
