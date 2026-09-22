# Changelog

## [0.2.0] - 2026-09-22

### Fixed

- **`navigate` and `open` survive Firefox replacing the browsing context.** A navigation that
  crosses into a container cannot reuse its context - `userContext` is not changeable in place - so
  Firefox builds a new one, discards the old, and reports `browsingContext.navigate: unknown error
  - Error: Browsing context got discarded` on a load that **succeeded**. Both commands now follow
  the replacement and return it with `context_swapped: true`. Adoption is narrow by construction:
  the context must be new, at the **exact** requested address, and in the window the original was
  in. A redirecting target, two candidates, or a Firefox that does not report `clientWindow` all
  let the original error propagate instead - the behaviour from before this existed. Mechanism,
  rejected alternatives and the residual risk:
  `docs/firefox-control/adrs/0001-identify-the-swapped-context-by-address-and-window.md`.

  `open` was missed by the first cut and fixed the same day. Its navigation is always a context's
  first, which is precisely the one a container assignment replaces, so it was the command most
  exposed rather than least. The invariant that keeps this from recurring: **everything that
  navigates goes through `cmd_navigate`**.

- **`send()` releases its reply slot when the caller is cancelled**, including cancellation during
  the socket write. `asyncio.wait_for` would otherwise strand an entry in `_pending` for the life
  of the connection.

### Changed

- **`list` reports `clientWindow`** for each context, which the swap recovery matches on.
- **`navigate` always returns `context`**, and adds `context_swapped` on a swap. **Read `context`
  back from the result** rather than reusing the id passed in - and for `open`, rather than
  assuming it is the tab that was created.

### Notes

- To avoid the swap rather than recover from it, create the tab directly in the assigned container
  (`browsingContext.create` with `userContext`). The container's BiDi id is generated per session
  and appears nowhere on disk, so read it from `browser.getUserContexts` rather than hardcoding it.
