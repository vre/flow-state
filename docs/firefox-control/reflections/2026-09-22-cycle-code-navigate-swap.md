# Cycle Reflection (code): navigate context swap

## What the cycle actually was

Not a feature. A three-day outage in a scheduled job, debugged to a mechanism, then
fixed in the shared tool.

## What went wrong before this cycle

Nine hypothesis tests over several days all checked **whether the original context
survived**. None checked **whether a replacement had appeared**. The navigation was
succeeding the whole time. The instrument was wrong, not the engine — the same
failure shape as wiki `CLAUDE.md` §"Open the source", trigger 2.

The fix only became designable once the mechanism was measured instead of guessed.
`userContext` changing from `default` to a fixed container id was the tell; before
that the design was a probability argument about URLs.

## What the measurement bought

Three design simplifications, each replacing an argument with a fact:

- the `origin` tier could be **deleted** — it existed for a redirect the mechanism
  does not produce
- `accept_redirect` went with it, along with its CLI gap and its docs
- `clientWindow` became available as an exact check, for one extra field

Measured code is smaller than defensive code.

## Review

Three cross-model rounds, six findings, five of them real defects the tests did not
catch: a `_pending` leak when cancellation lands in the socket write, an unbounded
pre-navigation `getTree`, `rstrip("/")` collapsing distinct paths, a dropped
fragment, and `None == None` passing as a window match.

The last is the one worth keeping: a compatibility fallback that looked harmless was
protecting a hypothetical browser at the cost of the safety property the docs claimed.
Failing closed costs nothing real (Firefox 155.0.1 reports the field) and makes the
documentation true.

## Verification

Unit tests use fakes, so every behaviour was also checked live against the real
browser: the swapping target recovers, a non-swapping target takes the normal path,
and both real target shapes still match after matching was tightened.
