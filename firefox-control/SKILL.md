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

## Prerequisites

User must launch Firefox with: `firefox --remote-debugging-port 9223`

The daemon starts automatically on first command. No explicit `start` needed.

The daemon holds the BiDi WebSocket open so each CLI call is instant — no connection overhead. Each command is a one-shot call; the caller does not hold any connection. The daemon idles out after 5 min of no commands. Unix socket: /tmp/firefoxctl-{uid}.sock.

Tool responses are sanitized: prompt-injection markers in page content are stripped before reaching the LLM.

## Commands

```bash
firefoxctl.py list
firefoxctl.py open https://example.com
firefoxctl.py status
firefoxctl.py targets
firefoxctl.py stop
```

Use `--json` for machine-parseable JSON output (default is human-readable).

## Target commands

All target commands: `firefoxctl.py CONTEXT COMMAND [ARGS]`

Context ID from list output (full UUID required — no prefix match).

```bash
firefoxctl.py CONTEXT eval "document.title"
firefoxctl.py CONTEXT screenshot -o page.png
firefoxctl.py CONTEXT console-tail --for 30
firefoxctl.py CONTEXT navigate https://example.com
```

## DOM helpers

Shorthands for common eval patterns. Selectors are CSS.

```
  click/check/uncheck/highlight SELECTOR
  submit/clear FORM
  type/fill SELECTOR TEXT
  select SELECTOR VALUE
  get-text/get-html/get-value/exists/count/get-texts SELECTOR
  get-attr SELECTOR ATTR
  scroll-to/wait-for/wait-hidden SELECTOR
  wait-text SELECTOR TEXT
  navigate URL
  wait-url PATTERN
  scroll-up/scroll-down [PIXELS]
  scroll-by X Y
  inject-css CSS
  reload/back/forward/get-title/get-url/scroll-top/scroll-bottom
```

Wait commands: --timeout N (default 10s)

For anything not covered: `firefoxctl.py CONTEXT eval "JS expression"`

Top-level await: `firefoxctl.py CONTEXT eval "await fetch('/api').then(r => r.json())"`

## Raw BiDi

```bash
firefoxctl.py bidi browser.getClientWindows
firefoxctl.py bidi browsingContext.getTree --params '{}'
```
