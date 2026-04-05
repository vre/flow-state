---
name: chrome-debug
description: This skill should be used when debugging web applications, diagnosing page errors, inspecting console output, or capturing screenshots of pages. It provides Chrome DevTools Protocol (CDP) automation via the chromectl.py script for collaborative or automated browser debugging.
---

# Chrome Debug

## Overview

This skill enables web application debugging through automated Chrome browser control using the Chrome DevTools Protocol (CDP). It works with **Chrome M144+** where traditional `--remote-debugging-port` on the default profile is blocked.

Two operating modes:
- **Daemon mode** (preferred): connects to user's running Chrome via `--auto-connect`, accesses all logged-in sessions
- **Traditional mode**: launches a separate Chrome instance with its own profile

## When to Use This Skill

Invoke this skill when:
- Debugging web application issues or investigating page errors
- Inspecting browser console for errors, warnings, or log messages
- Capturing screenshots of pages to identify visual problems
- Monitoring page behavior in real-time during development
- Automating page inspection or testing workflows
- Diagnosing JavaScript errors or unexpected page behavior

Do NOT use this skill for:
- General web browsing or information gathering (use WebFetch instead)
- Editing HTML/CSS files directly (this is for runtime inspection only)
- Testing that requires sophisticated user interaction (use proper testing frameworks)

## Choosing a Mode

### Daemon mode (default choice)

Use when the user already has Chrome open with the target site. Connects to the user's existing browser session — all tabs, cookies, and logins are accessible.

**Setup**: user must have enabled remote debugging via `chrome://inspect/#remote-debugging` (applies to all profiles).

```bash
# Start daemon — connects to running Chrome
scripts/chromectl.py daemon

# Commands go through the daemon
scripts/chromectl.py send list
scripts/chromectl.py send eval --id $ID -e "document.title"
scripts/chromectl.py send screenshot --id $ID -o page.png
```

The daemon keeps one WebSocket connection alive to avoid repeated Chrome permission dialogs. Shuts down automatically after 5 min idle or when Chrome closes.

### Traditional mode

Use when you need a clean browser instance, or when the user hasn't enabled remote debugging.

```bash
scripts/chromectl.py start [--headless]    # Launch separate Chrome
scripts/chromectl.py list                   # Direct commands (no daemon)
scripts/chromectl.py stop                   # Kill when done
```

`--headless` for automation, without for collaborative debugging where the user interacts with the visible window.

## Daemon Mode Limitations (M144+)

- **No HTTP discovery** — `/json` endpoints return 404. Use `list` through daemon instead.
- **No direct page WebSocket** — all page access goes through flat sessions multiplexed over the browser WebSocket.
- **Permission dialog on reconnect** — if the daemon's connection drops (Chrome restart, sleep/wake), the user must click Allow again.
- **Worker attachment unstable** — attaching to service worker targets can crash the connection.

Traditional mode has none of these limitations.

## Debugging Workflows

### Workflow 1: Inspect user's running page (daemon)

The most common scenario: user has a site open and wants to debug it.

```bash
# 1. Start daemon (user clicks Allow in Chrome)
scripts/chromectl.py daemon

# 2. Find the target tab
scripts/chromectl.py send list

# 3. Inspect page state
scripts/chromectl.py send eval --id $ID -e "document.title"
scripts/chromectl.py send eval --id $ID -e "({
  readyState: document.readyState,
  errors: document.querySelectorAll('.error').length,
  url: location.href
})"

# 4. Screenshot
scripts/chromectl.py send screenshot --id $ID -o state.png

# 5. Stop when done
scripts/chromectl.py stop
```

### Workflow 2: Collaborative debugging (traditional)

Use when developer wants a visible Chrome window to work together.

```bash
# 1. Start Chrome with visible window
scripts/chromectl.py start

# 2. Open the problematic page
TARGET=$(scripts/chromectl.py open https://myapp.com/problem-page | jq -r .id)

# 3. Monitor console while developer interacts
scripts/chromectl.py console-tail --id $TARGET --for 60 &

# 4. Inspect page state
scripts/chromectl.py screenshot --id $TARGET -o initial.png
scripts/chromectl.py eval --id $TARGET -e "document.readyState"

# 5. Clean up
scripts/chromectl.py stop
```

### Workflow 3: Automated screenshot capture (traditional)

```bash
scripts/chromectl.py start --headless
TARGET=$(scripts/chromectl.py open https://example.com | jq -r .id)
sleep 2
scripts/chromectl.py screenshot --id $TARGET -o page.png --full-page
scripts/chromectl.py stop
```

## JavaScript Evaluation

The `eval` command inspects and debugs page state:

```bash
# Page inspection
eval --id $ID -e "document.readyState"
eval --id $ID -e "({title: document.title, url: location.href})"
eval --id $ID -e "document.querySelector('#error-message')?.innerText"

# Debug functions
eval --id $ID -e "typeof myFunction"
eval --id $ID -e "window.myApp.config"

# Page interaction (for debugging)
eval --id $ID -e "document.querySelector('button#submit').click()"
eval --id $ID -e "window.scrollTo(0, document.body.scrollHeight)"
```

Promises are awaited automatically.

## Important Reminders

### Console-Tail Only Captures New Messages

Historical console messages are not shown. Start monitoring FIRST, then trigger actions:

```bash
scripts/chromectl.py console-tail --id $TARGET --for 30 &
scripts/chromectl.py eval --id $TARGET -e "myFunction()"
```

### Target IDs

All per-page commands need a target ID:

```bash
# From daemon
scripts/chromectl.py send list

# From open command
TARGET=$(scripts/chromectl.py open https://example.com | jq -r .id)
```

## Resources

### scripts/chromectl.py

The main CLI tool. Single-file Python script, dependencies managed by uv inline metadata.

### scripts/chromectl_daemon.py

Python library for daemon lifecycle management. Provides `daemon_context` (async context manager) and `send_command` for scripts that need programmatic daemon access.

### references/chromectl-reference.md

Complete command reference with all options, examples, and troubleshooting.

## Quick Reference

```bash
# Daemon mode (preferred)
scripts/chromectl.py daemon
scripts/chromectl.py send list
scripts/chromectl.py send eval --id $ID -e "expression"
scripts/chromectl.py send screenshot --id $ID -o file.png
scripts/chromectl.py stop

# Traditional mode
scripts/chromectl.py start [--headless]
TARGET=$(scripts/chromectl.py open URL | jq -r .id)
scripts/chromectl.py eval --id $TARGET -e "expression"
scripts/chromectl.py screenshot --id $TARGET -o file.png
scripts/chromectl.py stop
```
