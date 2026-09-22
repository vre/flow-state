# 0001 — Identify a swapped browsing context by address and window

Status: accepted (2026-09-22)

## Context

`browsingContext.navigate` can return

```
browsingContext.navigate: unknown error — Error: Browsing context got discarded
```

while the navigation **succeeded** — the page is loaded under a new context id.
A consumer treated it as fatal, fell back to "reuse any tab on that site", grabbed a
tab a human was reading, and died when they navigated away: three days of silent
failure in a scheduled job.

The cause was measured 2026-09-22, not inferred. It is a `userContext` (container)
switch: Multi-Account Containers assigns the site to a container, and a context
cannot change container in place, so Firefox builds a new one. Three trials on the
affected profile:

```
created:     userContext=default      clientWindow=W
navigate ->  discarded
replacement: userContext=<container>  clientWindow=W   url=<exact target>
```

`clientWindow` is preserved. The replacement carries the byte-identical requested URL
— the swap re-issues the same request, so it is not a redirect. It is host-specific
(only sites with an assignment rule) and first-navigation only.

BiDi exposes **no "replaced context X" relation**, so nothing in the protocol proves
which context replaced which.

## Decision

Snapshot the contexts immediately before navigating, recording the navigated
context's `clientWindow`. On a discard, adopt a context that is **new since that
snapshot, at the exact requested address, and in that window** — and refuse when two
qualify or when the window is unknown.

Rejected: **a dedicated owned window** (create a window nothing else opens tabs in,
making any new context there provably ours). It is the only real ownership proof, and
`clientWindow` surviving the swap makes it cheap to build. Not taken because with the
weaker tiers removed the remaining race requires a human to open the exact target —
JSON API endpoints, in this consumer's case — in that window inside the wait.

Rejected: **an "only new context on the target's origin" tier** for redirects. The
measured mechanism does not produce a redirect, and an ordinary new tab on the site
satisfied it.

## Consequences

- A target that **redirects** raises. Navigate to the final URL, or handle the error.
- A Firefox that does not report `clientWindow` gets no recovery: the discard
  propagates. Two absent ids are not a window match.
- An unresponsive `getTree` disables recovery rather than hanging or failing the
  navigation.
- The residual risk is pinned by
  `test_known_residual_risk_a_user_tab_at_the_exact_target_in_our_window`.
  **If it must be closed, build the owned window — do not loosen the match.**
- Creating the tab directly in the assigned container avoids the swap entirely. The
  container's BiDi id is generated per session; read it from
  `browser.getUserContexts`, never hardcode it.

## Scope: every command that navigates, not just `navigate`

Amended 2026-09-22, same day. The first implementation changed `cmd_navigate` only, and
`cmd_open` kept navigating with a raw `conn.send`. That left the **most** exposed command
unfixed: `open` creates a tab, so its navigation is always a context's first — precisely
the one a container assignment replaces. `firefoxctl open https://www.reddit.com/` still
raised.

It was caught by watching a consumer work around it in its own code during a live run,
minutes after the fix shipped — not by review, which read the diff that was there rather
than the commands that were not in it.

`cmd_open` now delegates to `cmd_navigate`. `grep` for `browsingContext.navigate` shows
one remaining raw send, inside `cmd_navigate` itself. **Anything that navigates goes
through `cmd_navigate`** — that invariant is what makes this decision hold.
