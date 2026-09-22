# Cut 1: the client quotes

Frame: `2026-09-22-frame-html-reply.md`. This cut delivers replies whose quote the client
produces. The verbatim HTML fragment is cut 2; everything else is here.

## What ships

`create` takes `quote: "INBOX:1253"` as a top-level parameter and assembles the reply itself:

- **Recipient** from the original's `Reply-To`, else `From`, unless the caller supplied `to`.
- **Subject** `Re: <original>`, unless it already starts with `Re:`, unless the caller supplied one.
- **Threading**: `In-Reply-To` = the original's Message-ID, `References` = the original's
  `References` plus its Message-ID.
- **Plain part**: the caller's text, blank line, attribution, then the original prefixed `> `.
- **HTML part** (markdown format only): the caller's text rendered, then
  `div.moz-cite-prefix`, then `blockquote type="cite" cite="mid:…"` holding the original's
  text, HTML-escaped with `<br>` line breaks.

## The quote is not re-interpreted

The quoted original is never passed through the markdown renderer. Asterisks in someone else's
mail are asterisks, not emphasis, and `#` at the start of their line is not a heading. In the
plain part it is prefixed and otherwise untouched - **no rewrapping**, because rewrapping is an
alteration and the frame says we do not alter the quote. In the HTML part it is escaped text.

That is also why this cut builds the whole skeleton rather than a markdown `>` block: cut 2
replaces the escaped text inside the blockquote with the original's verbatim fragment and
changes nothing else.

## Attribution

`On 19.8.2026 15.18, Display Name wrote:` - Thunderbird's line, pinned as a constant rather than
produced by a locale-dependent formatter (frame decision 3). Day, month and hour without leading
zeros; minutes zero-padded; dots throughout. Falls back to the address when there is no display
name, and omits the line entirely when the original has no parsable date.

## Shape

- `quoting.py` (new): `attribution_line`, `quote_plain`, `quote_html_text`, `reply_headers`,
  `assemble_reply`. Pure functions over an original already fetched - no IMAP, no rendering.
- `imap_client.fetch_quotable(folder, uid, account)`: the original's message-id, references,
  subject, from/reply-to, date and body text. Uses the existing read path; the full body, not the
  truncated one, because a truncated quote is a misquote.
- `actions.py`: the `create` branch resolves `quote`, then calls `create_draft` with the
  assembled body and the threading headers.
- `create_draft` learns `references`, which it previously derived from `in_reply_to`.
- `imapctl.py`: `create --quote INBOX:1253`.

## Out of this cut

- The verbatim HTML fragment and `multipart/related` (cut 2).
- Interleaving (cut 3).
- `quote` on `replace`: a draft already holds its quote, so re-quoting would duplicate it.

## Checks

- Attribution renders identically regardless of the process locale.
- A plain original is quoted byte-for-byte apart from the `> ` prefix, blank lines included.
- Markdown in the quoted original stays literal in both parts.
- `Re:` is not doubled; `References` chains rather than replaces.
- `Reply-To` wins over `From`; an explicit `to` wins over both.
- A missing or unreadable quote target fails before anything is appended.
