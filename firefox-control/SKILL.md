---
name: firefox-control
description: Use when you need to automate Firefox via WebDriver BiDi — tab listing, JS evaluation, screenshots, DOM helpers. TEST TOOL — Firefox sets navigator.webdriver=true.
---

# Firefox Control

Control Firefox via WebDriver BiDi. Connects to Firefox launched with
`--remote-debugging-port`. No geckodriver needed — direct BiDi WebSocket.

**TEST TOOL**: Firefox sets `navigator.webdriver=true` on any remote debugging
session. Every anti-bot system detects this. Mozilla has no extension-based
automation API and no runtime toggle. For production agent workflows, use
Chrome CDP tooling instead.

## Start daemon

```bash
firefoxctl.py --port 9223 start
```

Creates: Unix socket at /tmp/firefoxctl-{uid}.sock. Idles out after 5 min.

User must launch Firefox with: `firefox --remote-debugging-port 9223`

## Commands

```bash
firefoxctl.py list
firefoxctl.py stop
```

## Target commands

All target commands: `firefoxctl.py CONTEXT COMMAND [ARGS]`

Context ID from list output (full UUID required — no prefix match).

```bash
firefoxctl.py CONTEXT eval "document.title"
firefoxctl.py CONTEXT screenshot -o page.png
firefoxctl.py CONTEXT navigate https://example.com
```

## DOM helpers

```
  get-text SELECTOR       Get text content
  get-html SELECTOR       Get outerHTML
  exists SELECTOR         Check if element exists
  count SELECTOR          Count matching elements
  click SELECTOR          Click element
  fill SELECTOR VALUE     Set input value
```

For anything not covered: `firefoxctl.py CONTEXT eval "JS expression"`

Top-level await: `firefoxctl.py CONTEXT eval "await fetch('/api').then(r => r.json())"`

## Raw BiDi

```bash
firefoxctl.py bidi browser.getClientWindows
firefoxctl.py bidi browsingContext.getTree --params '{}'
```
