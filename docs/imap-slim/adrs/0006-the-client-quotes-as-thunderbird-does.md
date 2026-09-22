# 0006 — The client quotes, as Thunderbird does, and never alters the quote

Status: accepted (v2.1.0)

## Context

A reply has to carry the message it answers. Left to the model, the quote is reproduced from context
— something that *resembles* the original, over a body `read` truncates by default. For an HTML
message the model cannot produce the sender's markup at all. Mail clients solved this long ago, but
the markup they use is convention, not standard: no RFC defines the attribution line or the quote
wrapper.

## Decision

- **The client quotes.** `create` with `quote: "FOLDER:UID"` fetches the original and builds the
  quote, attribution, `Re:` subject, recipient and `In-Reply-To`/`References`. The model supplies
  only the new text.
- **Thunderbird is the specification**, measured off the wire from real replies rather than
  described from memory: `div.moz-cite-prefix` attribution, `blockquote type="cite" cite="mid:…"`,
  the original's body fragment verbatim, inline images carried in a `multipart/related` around the
  HTML alternative under fresh Content-IDs, attachments not carried. The measurement is recorded in
  `docs/imap-slim/plans/2026-09-22-frame-html-reply.md`.
- **The quoted original is never altered.** Not rendered as markdown, not rewrapped, not sanitised,
  remote images left in place. An altered quote is a misquote.
- **Interleaving is plain text only**, and the quote that comes back is checked: every `>` line must
  appear verbatim in the original, in order. Dropping lines is allowed; changing or reordering them
  refuses the draft. Nobody splices into someone else's HTML, this client included.
- The attribution date format is a constant (`19.8.2026 15.18`), not a locale call: the process
  inherits whatever locale the MCP or CLI started with.

## Consequences

- Third-party markup is re-sent over the user's identity unsanitised, and remote images in a quote
  report back to the original sender when the recipient opens the reply. Both are true of every mail
  client; stripping either would alter the quote, which is the larger harm. The one consumer that is
  not a mail client — `read` — sanitises and wraps untrusted content on the way in.
- The new text always sits above the quote, so an unbalanced tag in the fragment can only break the
  quote's own rendering.
- A quote with inline images makes a large draft. It is reported above 500 kB and never truncated.
- The order check in interleaving scans forward, so a line that repeats in the original could reject
  a legitimate reply. Not seen yet; recorded in `imap-slim/TODO.md`.
- Anything that changes how a reply is assembled should be checked against a real Thunderbird reply,
  not against this document.
