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
chromectl.py send list
chromectl.py send open https://example.com
chromectl.py send eval --id <id> -e "document.title"
chromectl.py send screenshot --id <id> -o page.png [--full-page]
chromectl.py send console-tail --id <id> --for 30
chromectl.py stop
```

Eval is universal — anything from DevTools console works:

```bash
chromectl.py send eval --id <id> -e "document.querySelector('btn').click()"
chromectl.py send eval --id <id> -e "({title: document.title, url: location.href})"
chromectl.py send eval --id <id> -e "fetch('/api').then(r => r.json())"
```

## Legacy mode

For clean browser without existing sessions: `chromectl.py launch [--headless]`, then use commands without `send`.

## Resources

- `chromectl-reference.md` — all options, socket protocol, troubleshooting
