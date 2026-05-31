# Firefox Control

> **Test Tool — Mozilla Painted Themselves Into a Corner**

Control Firefox via [WebDriver BiDi](https://www.w3.org/TR/webdriver-bidi/) from
the command line. Single-file Python CLI, no geckodriver, direct WebSocket to
Firefox's native BiDi implementation.

This tool exists to prove BiDi works and to demonstrate what Firefox got wrong
for agent automation. **Not recommended for production agent workflows** — use
Chrome CDP tooling instead.

## Why This Is a Test Tool

Firefox made three decisions that kill it for agent browser automation:

1. **`navigator.webdriver = true`** — Firefox sets this flag on any remote
   debugging session ([Bug 1719505](https://bugzilla.mozilla.org/show_bug.cgi?id=1719505),
   Firefox 101+). Every anti-bot system checks this. Chrome CDP does not set it.

2. **No extension-based automation** — Chrome has `chrome.debugger`, which lets
   extensions (like Claude in Chrome) get full CDP access without opening a debug
   port. Firefox has no equivalent API. No `browser.debugger`, nothing.

3. **Launch-time only** — `--remote-debugging-port` must be set when Firefox
   starts. Chrome M144+ lets you enable debugging at runtime via
   `chrome://inspect/#remote-debugging`. Firefox has no runtime toggle.

The BiDi protocol itself is solid — W3C standard, clean WebSocket API, native
Firefox implementation with no intermediary. Mozilla just surrounded it with
restrictions that make it useless for the "automate your real browser" use case
that agents need.

## Installation

### Via Claude Code marketplace

```bash
/plugin marketplace add vre/flow-state
/plugin install firefox-control@flow-state
```

### Standalone

```bash
# Requires uv (https://docs.astral.sh/uv/)
chmod +x firefoxctl.py
./firefoxctl.py --help
```

## Usage

### 1. Launch Firefox with remote debugging

```bash
firefox --remote-debugging-port 9223
```

### 2. Start the daemon

```bash
firefoxctl.py --port 9223 start
```

### 3. Use it

```bash
firefoxctl.py list
firefoxctl.py CONTEXT eval "document.title"
firefoxctl.py CONTEXT screenshot -o page.png
firefoxctl.py CONTEXT navigate https://example.com
firefoxctl.py CONTEXT get-text h1
firefoxctl.py CONTEXT click "button.submit"
firefoxctl.py CONTEXT fill "input[name=q]" "search term"
firefoxctl.py stop
```

### Direct mode (no daemon)

Every command without a running daemon creates a fresh BiDi session. Context IDs
change between invocations. Use daemon mode for stable context IDs.

```bash
firefoxctl.py --port 9223 list
```

### Raw BiDi

```bash
firefoxctl.py bidi browser.getClientWindows
firefoxctl.py bidi session.status
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
- **Daemon**: persistent BiDi session, stable context IDs, idle timeout (5 min)
- **CLI**: JSON line protocol, pipe-friendly

## Copyright

Copyright (c) 2026 Ville Reijonen. All rights reserved.

Licensed under the MIT License. See [LICENSE](LICENSE) for details.
