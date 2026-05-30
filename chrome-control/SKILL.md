---
name: chrome-control
description: Use when debugging web applications, diagnosing page errors, inspecting console output, or capturing screenshots via Chrome DevTools Protocol (CDP).
---

# Chrome Control

Control Chrome via CDP. Connects to user's running Chrome — all tabs, cookies, logins accessible.

## Start daemon

```bash
chromectl.py start
```

Creates: Unix socket at /tmp/chromectl-{uid}.sock

User clicks Allow once. Daemon idles out after 5 min or on `stop`.

If connection fails → tell user to enable `chrome://inspect/#remote-debugging`, or offer legacy mode (`launch`).

## Commands

```bash
chromectl.py list
chromectl.py open https://example.com
chromectl.py status
chromectl.py stop
```

## Target commands

All target commands: `chromectl.py TARGET COMMAND [ARGS]`

Target ID from list/open output. Prefix match OK (e.g. `88FA` instead of full 32-char ID).

```bash
chromectl.py ABC123 eval "document.title"
chromectl.py ABC123 screenshot -o page.png [--full-page]
chromectl.py ABC123 console-tail [--for 30]
```

## DOM helpers

Shorthands for common eval patterns. Selectors are CSS.

```
  click/check/uncheck/highlight SELECTOR
  submit/clear FORM
  type SELECTOR TEXT
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

For anything not covered: `chromectl.py ABC123 eval "JS expression"`

Top-level await: `chromectl.py ABC123 eval "await fetch('/api').then(r => r.json())"`

## Legacy mode

For clean browser without existing sessions: `chromectl.py launch [--headless]`

## Resources

- `chromectl-reference.md` — all options, socket protocol, troubleshooting
