# 0003 — Action names describe what IMAP does

Status: accepted (v2.0.0). Breaking.

## Context

IMAP messages are immutable. An "edit" action can only fetch, substitute, append a new version and
expunge the old — a replace — and every replace mints a fresh `Message-ID` and sequence number. The
name promised in-place mutation with a stable identity; neither is available.

## Decision

- `create` — an `APPEND`.
- `replace` — an `APPEND` plus an expunge of the draft it supersedes; reports the new id.
- No `edit`.

Two actions rather than one branching on whether a payload carries an id, so the destructive one is
named: an `id` in a `create` is an error, a missing `id` in a `replace` is an error.

## Consequences

- **An id is stale after a `replace`.** Callers must use the id the response reports.
- Changing a draft means sending the whole body again. Nothing stores the markdown source, so the
  caller keeps it — stated in `SKILL.md`.
