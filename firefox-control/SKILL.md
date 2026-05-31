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
  click SELECTOR          Click element
  check SELECTOR          Check checkbox
  uncheck SELECTOR        Uncheck checkbox
  type SELECTOR TEXT      Type text into input
  fill SELECTOR VALUE     Set input value (alias for type)
  select SELECTOR VALUE   Set select value
  get-text SELECTOR       Get innerText
  get-html SELECTOR       Get innerHTML
  get-value SELECTOR      Get input value
  get-attr SELECTOR ATTR  Get attribute
  get-texts SELECTOR      Get text of all matches
  exists SELECTOR         Check if element exists
  count SELECTOR          Count matches
  highlight SELECTOR      Outline elements in red
  submit SELECTOR         Submit form
  clear SELECTOR          Reset form
  scroll-to SELECTOR      Scroll element into view
  scroll-up [PIXELS]      Scroll up
  scroll-down [PIXELS]    Scroll down
  scroll-top              Scroll to top
  scroll-bottom           Scroll to bottom
  scroll-by X Y           Scroll by offset
  back                    Navigate back
  forward                 Navigate forward
  get-title               Get document title
  get-url                 Get current URL
  inject-css CSS          Inject CSS
  wait-for SEL [--timeout N]         Wait for element
  wait-hidden SEL [--timeout N]      Wait for element to hide
  wait-text SEL TEXT [--timeout N]   Wait for text
  wait-url PATTERN [--timeout N]     Wait for URL
```

For anything not covered: `firefoxctl.py CONTEXT eval "JS expression"`

Top-level await: `firefoxctl.py CONTEXT eval "await fetch('/api').then(r => r.json())"`

## Raw BiDi

```bash
firefoxctl.py bidi browser.getClientWindows
firefoxctl.py bidi browsingContext.getTree --params '{}'
```
