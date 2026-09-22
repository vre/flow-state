# 0005 — Exactly one expunge, scoped to one message, only in Drafts

Status: accepted (v2.0.0)

## Context

A bare `EXPUNGE` removes **every** message carrying `\Deleted` in the selected mailbox, not the one
just marked (RFC 3501). `replace` used one, on a caller-supplied folder, checking only that the
*target message* carried `\Draft`. That permanently destroyed messages the user had merely marked.

## Decision

- `uid_expunge` (RFC 4315) removes exactly the superseded draft.
- Without UIDPLUS, **nothing** is expunged: the old draft is left marked and the response says so.
  Expunging everything is not a fallback for expunging one thing.
- `replace` is refused outside the Drafts folder, before anything is written.
- No `expunge` action is exposed. `flag ... +Deleted` marks and stops there.

## Consequences

- On a server without UIDPLUS, superseded drafts accumulate marked-deleted until the user's mail
  client clears them. Visible and recoverable, unlike silent loss.
- This is the only deletion the client performs. **Any future action that deletes needs its own
  decision recorded here**, and a `\Draft` check on the target is not sufficient on its own — the
  folder must be constrained too.
