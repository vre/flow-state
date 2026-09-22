# Cycle Reflection (code): open survives the swap

## What this was

A gap in the cycle that shipped hours earlier. `cmd_navigate` learned to survive a
container swap; `cmd_open` kept a raw `conn.send("browsingContext.navigate", ...)` and
learned nothing.

## How it was found

Not by review. Three cross-model rounds read the diff and passed it. The gap was visible
only in a **live run of a real consumer**: `fetch_daily.py`'s log showed

```
… open reported firefoxctl failed: {"error": "… Browsing context got discarded"};
  looking for the replacement context
✓ context was replaced; continuing in d9077bfe-5d8…
```

A consumer re-implementing the fix that had just been shipped to it is a defect report.

## Why review could not have caught it

Every round was framed as "review `git diff main..HEAD`". The defect was in a function
the diff did not touch. A reviewer asked to check a change cannot be expected to ask
*what else has this shape* — that question belongs to whoever sets the scope.

The generalisable check is cheap and was run afterwards: `grep` for the raw operation the
fix wraps, and confirm every remaining call site is the wrapper itself.

## Verification

Unit tests use fakes, so it was also A/B'd live with the daemon stopped (the daemon holds
the connection and executes *its* copy of the code — a first attempt at this A/B compared
two invocations that were both being served by the old daemon, and read as "the fix does
nothing"):

| | `open https://www.reddit.com/` |
|---|---|
| before | `error: Browsing context got discarded` |
| after | `context_swapped: true`, and `document.title` on the returned context reads `Reddit - The heart of the internet` |
