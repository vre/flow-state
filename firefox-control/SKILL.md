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

**`navigate` may hand you a different context back.** Firefox sometimes answers a
navigation by replacing the browsing context rather than reusing it — the id you
asked for is destroyed and a new one appears at the target URL. `navigate` follows
the swap when it can identify the replacement:

```bash
uv run firefoxctl.py --json navigate "$ctx" https://example.com/feed.json
# {"navigation": "...", "url": "...", "context": "<same id>"}
# {"navigation": null,  "url": "...", "context": "<NEW id>", "context_swapped": true}
```

**Read `context` back from the result — do not reuse the id you passed in.**

It adopts a new context only when that context is **new, at the address you
requested, and in the window the original was in**, and refuses when two qualify.
A Firefox that does not report `clientWindow` gets no recovery at all — the discard
propagates, as it did before this existed.
The address comparison is exact — query and fragment included, and only an empty
path is treated as `/`. A target that **redirects** therefore raises: the
replacement is at the redirected address, which no longer matches. Navigate to the
final URL, or handle the error.

Navigation failures propagate unchanged.

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

### A container assignment replaces the context mid-navigation

`browsingContext.navigate` can return `Error: Browsing context got discarded` when
the navigation **succeeded** — the page is loaded under a new id.

The cause is a `userContext` (container) switch. An extension such as Multi-Account
Containers assigns a site to a container, and a context cannot change container in
place, so Firefox builds a new one and discards the old. Measured on
www.reddit.com 2026-09-22: the replacement carries the requested URL, the same
`clientWindow`, and the assigned `userContext`. It is **host-specific** — only sites
with an assignment rule swap — and **first-navigation only**: once a context is in
the container, it navigates normally.

Consequences:

- A profile with no container rules never sees this, so it will not reproduce on a
  clean test profile.
- Creating the tab directly in the assigned container (`browsingContext.create` with
  `userContext`) avoids the swap. The container's BiDi id is generated per session —
  read it from `browser.getUserContexts`, never hardcode it.
- **BiDi exposes no "replaced context X" relation**, so `navigate`'s recovery is a
  heuristic. What is left of it after the URL and window checks: the user would have
  to open that exact URL, in that window, between the snapshot `navigate` takes and
  the end of the wait. Accepted, not eliminated — "new" is new since that snapshot,
  not since Firefox acted on the navigation.

If you need certainty rather than a narrow risk: validate what you get back (the
document's origin, or a marker you set before navigating), or drive a window nothing
else can create contexts in.

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
