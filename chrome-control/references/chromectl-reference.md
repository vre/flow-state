# chromectl Command Reference

Complete reference for the chromectl.py script used in Chrome debugging workflows.

## Command Overview

- `start` - Launch Chrome with remote debugging
- `stop` - Stop all chromectl-managed Chrome instances
- `list` - List all open tabs/targets
- `open <url>` - Open a new tab and get its target ID
- `eval --id <id> -e <expr>` - Execute JavaScript in a tab
- `screenshot --id <id> [-o file]` - Capture screenshot
- `console-tail --id <id> [--for N]` - Stream console messages

## Global Options

```bash
--host HOST    # CDP host (default: 127.0.0.1)
--port PORT    # CDP port (default: 9222)
```

Place global options BEFORE the command:
```bash
./chromectl.py --port 9223 list
```

## start - Launch Chrome

```bash
./chromectl.py start [OPTIONS]
```

**Options:**
- `--headless` - Run in headless mode (no visible window)
- `--port PORT` - Remote debugging port (default: 9222)
- `--chrome-app NAME` - macOS app name (default: "Google Chrome")
- `--user-data-dir PATH` - Custom profile directory (default: ~/chromectl-profile)

**Headful vs Headless:**
- **Without --headless**: Visible Chrome window for collaborative debugging (developer + Claude)
- **With --headless**: Background process for automation/screenshots

**Examples:**
```bash
# Visible window (collaborative debugging)
./chromectl.py start

# Headless (automation)
./chromectl.py start --headless

# Multiple instances
./chromectl.py start --port 9223 --user-data-dir ~/chromectl-test2
```

## stop - Stop Chrome Instances

```bash
./chromectl.py stop
```

Finds and terminates all Chrome processes launched by chromectl (identified by chromectl profile directories).

**CRITICAL:** Always run `stop` when debugging session ends to:
- Free up debugging ports
- Allow normal Chrome to launch from Finder
- Clean up background processes

## list - List Targets

```bash
./chromectl.py list
```

Returns JSON objects (one per line) for each target:
```json
{"id": "ABC123", "type": "page", "title": "Page Title", "url": "https://...", "attached": null}
```

**Target types:** page, background_page, service_worker, iframe

## open - Open New Tab

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

## eval - Execute JavaScript

```bash
./chromectl.py eval --id <target-id> -e <expression>
```

**Features:**
- Automatically awaits promises
- Returns JSON-serialized values
- REPL mode enabled

**Common patterns:**

```bash
# Page inspection
eval --id $ID -e "document.title"
eval --id $ID -e "window.location.href"
eval --id $ID -e "document.readyState"

# DOM queries
eval --id $ID -e "document.querySelector('h1').innerText"
eval --id $ID -e "document.querySelectorAll('a').length"

# Return objects
eval --id $ID -e "({title: document.title, url: location.href})"

# Async operations
eval --id $ID -e "fetch('/api/data').then(r => r.json())"

# Page interaction (for debugging)
eval --id $ID -e "document.querySelector('button#submit').click()"
eval --id $ID -e "window.scrollTo(0, document.body.scrollHeight)"

# Check for JavaScript errors
eval --id $ID -e "window.onerror"
eval --id $ID -e "typeof myFunction"
```

## screenshot - Capture Screenshot

```bash
./chromectl.py screenshot --id <target-id> [-o output.png] [--full-page]
```

**Options:**
- `-o, --output` - Output file path (default: screenshot_<id>.png)
- `--full-page` - Capture entire scrollable page (not just viewport)

**Examples:**
```bash
# Viewport only
./chromectl.py screenshot --id $ID -o page.png

# Full page
./chromectl.py screenshot --id $ID -o full.png --full-page
```

Returns the output filename when complete.

## console-tail - Stream Console

```bash
./chromectl.py console-tail --id <target-id> [--for SECONDS]
```

**Options:**
- `--for` - Duration in seconds to stream (default: 10)

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
./chromectl.py console-tail --id $ID --for 30 &

# Interact with page or trigger actions
./chromectl.py eval --id $ID -e "myFunction()"

# Wait for console-tail to complete
wait
```

## Workflows

### Basic Debugging Session

```bash
# 1. Start Chrome (headful for collab, headless for automation)
./chromectl.py start

# 2. Open the page to debug
TARGET=$(./chromectl.py open https://myapp.com | jq -r .id)

# 3. Start console monitoring
./chromectl.py console-tail --id $TARGET --for 60 &

# 4. Take screenshot
./chromectl.py screenshot --id $TARGET -o initial.png

# 5. Inspect page state
./chromectl.py eval --id $TARGET -e "document.readyState"

# 6. Clean up
./chromectl.py stop
```

### Multiple Targets

```bash
# Open multiple pages
ID1=$(./chromectl.py open https://page1.com | jq -r .id)
ID2=$(./chromectl.py open https://page2.com | jq -r .id)

# Work with each
./chromectl.py screenshot --id $ID1 -o page1.png
./chromectl.py screenshot --id $ID2 -o page2.png
```

## Troubleshooting

**"Cannot connect to host 127.0.0.1:9222"**
- No Chrome instance running with remote debugging
- Solution: `./chromectl.py start --headless`
- If port taken: `./chromectl.py start --port 9223`

**"Target not found"**
- Tab was closed or ID is incorrect
- Solution: Run `./chromectl.py list` to get current IDs

**Port already in use**
- Another Chrome instance using the port
- Solution: Use different port with `--port 9223`

**Verify connection:**
```bash
lsof -i :9222                        # Check if port is listening
curl http://localhost:9222/json      # Test CDP endpoint
```

## Technical Details

- **Protocol:** Chrome DevTools Protocol (CDP) over WebSocket
- **Port:** 9222 (default), configurable
- **Dependencies:** aiohttp (auto-installed by uv)
- **Profile:** Uses isolated profile directory (~/chromectl-profile)
- **Platform:** macOS (direct Chrome binary execution)
