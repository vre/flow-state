---
name: firefox-control
description: Use to automate web browsing via Firefox WebDriver BiDi — tab listing, JS evaluation, screenshots, DOM helpers.
---

# Firefox Control

Control Firefox via WebDriver BiDi on port 9223. Direct BiDi WebSocket,
no geckodriver. Use port 9223 because more popular Chrome CDP occupies 9222.

Launch Firefox: `firefox --remote-debugging-port 9223`

**TEST TOOL**: `navigator.webdriver=true` — detected by every anti-bot
system. No toggle exists. Use Chrome CDP for production automation.

## Usage

Just run a command — the daemon auto-starts on first call and connects to Firefox on port 9223. If Firefox isn't running or doesn't have remote debugging enabled, the error message will say so.

Full command list: `uv run firefoxctl.py --help`
Per-command help: `uv run firefoxctl.py COMMAND --help`

Always use `uv run` (PEP 723 inline dependencies):

```bash
uv run firefoxctl.py list
uv run firefoxctl.py --json list
uv run firefoxctl.py open https://example.com
uv run firefoxctl.py status
uv run firefoxctl.py targets
uv run firefoxctl.py stop
```

`--json` goes BEFORE the subcommand (global flag). The daemon idles out after 5 min. Unix socket: /tmp/firefoxctl-{uid}.sock. Tool responses are sanitized against prompt injection.

## Target commands

All target commands: `uv run firefoxctl.py CONTEXT COMMAND [ARGS]`

Context ID from list output (full UUID required — no prefix match).

```bash
uv run firefoxctl.py CONTEXT eval "document.title"
uv run firefoxctl.py CONTEXT screenshot -o page.png
uv run firefoxctl.py CONTEXT console-tail --for 30
uv run firefoxctl.py CONTEXT navigate https://example.com
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

For anything not covered: `uv run firefoxctl.py CONTEXT eval "JS expression"`

Top-level await: `uv run firefoxctl.py CONTEXT eval "await fetch('/api').then(r => r.json())"`

## Raw BiDi

```bash
uv run firefoxctl.py bidi browser.getClientWindows
uv run firefoxctl.py bidi browsingContext.getTree --params '{}'
```

## Gotchas

### `list` URLs lie on error pages — validate before trusting a tab

A Firefox error page (`about:neterror`, e.g. after a transient DNS failure)
**keeps the requested URL** in `list` output. So picking a tab by matching its
URL silently selects a dead tab:

```bash
uv run firefoxctl.py list          # shows https://example.com/  ← looks fine
```

but the document is an error page with an **opaque origin**, so every `fetch()`
from it fails — relative URLs with `"X is not a valid URL"`, absolute ones with
`NetworkError` — and `eval` still works, which makes it look healthy.

Check the document, not the listing:

```bash
uv run firefoxctl.py CONTEXT eval "document.baseURI"      # about:neterror?e=dnsNotFound&u=...
uv run firefoxctl.py CONTEXT eval "String(window.origin)" # "null"
```

A live page has `baseURI` starting with the real URL and `origin` equal to the
site. Recover by re-navigating the same context:

```bash
uv run firefoxctl.py CONTEXT navigate https://example.com/
```

This bit the wiki's daily fetch pipeline twice in one week (2026-07-31,
2026-08-04): the tab died on a DNS blip, every subsequent run silently returned
0 posts, and the failure looked like a quiet news day rather than an error. Any
script that reuses a long-lived tab should validate `baseURI` + `origin` after
selecting it, and treat an empty result as an error rather than as data. See
`research/2026-04-05-m5-max-local-llm/scripts/fetch_daily.py`
(`_firefox_tab_is_live`) for a reference implementation.

### `navigate` rejects `about:` URLs and unresolvable hosts

BiDi refuses both, so you cannot force an error page to test recovery paths —
verify the detection predicate against captured values instead.
