# Frame: replying to HTML mail

Status: framing. Nothing implemented.

## Problem

Three ways of writing mail. Two work:

- **New mail in markdown** — `create` renders HTML plus a plain alternative. Solved.
- **Plain-text mail and plain replies** — `plain` is sent exactly as written. Solved.
- **Replying to an HTML message** — not solved, and not currently possible to do correctly.

A reply to an HTML message has to carry the original's HTML inside a `<blockquote>`, because
that is what the sender recognises as their own mail. Today the model would have to reproduce
that fragment from its own context, which means it is producing something that *resembles* the
original rather than quoting it. Two failures follow: the quote is not faithful, and `read`
truncates quoted chains by default, so the model often has not seen the text it is quoting.

The model must not be in the quoting path at all. The client has the original; the client quotes.

## Ground truth

Measured 2026-09-22 against real Thunderbird-composed replies in two Sent folders (11 messages,
two providers). Not recalled, not inferred - read from the wire. This section is the
specification: where we differ from it, we should have a reason.

### Structure

```
multipart/mixed                        only when files are attached to the reply
└ multipart/alternative
  ├ text/plain
  └ multipart/related                  only when the quote references inline images
    ├ text/html
    └ image/png  inline  <part1.XXXX.YYYY@senderdomain>  image.png
```

`multipart/related` sits inside `multipart/alternative`, wrapping the HTML part alone
([RFC 2387](https://www.rfc-editor.org/rfc/rfc2387)). With no inline images the structure is a
plain `multipart/alternative`.

### HTML part

```html
<body>
  <p>new text</p>
  <div class="moz-cite-prefix">On 19.8.2026 15.18, Display Name wrote:<br></div>
  <blockquote type="cite" cite="mid:ORIGINAL-MESSAGE-ID@host">
      the original body content, verbatim
  </blockquote>
</body>
```

- Attribution is a `div` immediately before the blockquote, not part of it.
- `cite="mid:…"` carries the original Message-ID.
- The fragment is **verbatim**: foreign classes survive (`gmail_quote`, `gmail_attr`,
  Outlook's `elementToProof`, and its `x_`/`x_x_` prefixes on classes inherited from earlier
  clients), and so do `<style>` blocks - verified specifically: every `<style>` in the sample sat
  *after* the `<blockquote>`, never in `<head>`. Quoted styles stay scoped inside the quote.

### Plain part

```
new text
                                            blank line
On 19.8.2026 15.18, Display Name wrote:     attribution, no "> " prefix
> original, wrapped at ~70 columns
```

No `format=flowed` in any sample, so [RFC 3676](https://www.rfc-editor.org/rfc/rfc3676) rewrap
does not apply to what we generate.

### Inline images vs attachments

- `image/*` with `Content-Disposition: inline`, referenced by `cid:` → copied into the new
  `multipart/related` with **rewritten Content-IDs** (`partN.XXXX.YYYY@senderdomain`), and the
  `cid:` references inside the quoted fragment rewritten to match. Filenames preserved.
- Attachments on the original → **not carried**. The quote gets an empty
  `<fieldset class="moz-mime-attachment-header">` where they were.

This answers the `multipart/related` item that has been open in `TODO.md` since 2026-02.

## Scope

In:

- `create` learns to quote a message the client fetches itself.
- Plain and markdown replies: `> ` quoting, attribution line, threading headers.
- HTML replies: verbatim fragment in a blockquote, inline images carried with rewritten cids.
- Interleaved replying for plain only, as a two-step where the client produces the quote block
  and the model splices into it.

Out:

- Interleaving inside HTML. Splicing into someone else's markup is not something this client
  will do, and no mail client does it either.
- Carrying the original's attachments into the reply. Thunderbird drops them; so do we.
- Signatures. There is no signature feature and this does not add one.

## Approach

`create` takes the message to quote, by folder and uid, and assembles everything:

1. Fetch the original. Take its `text/plain` when present, else `html2text` of its HTML, for the
   plain half. Take its body fragment for the HTML half.
2. Build the plain part: new text, blank line, attribution, `> `-prefixed original.
3. Build the HTML part when the reply is HTML: rendered markdown, attribution div, blockquote.
4. Copy inline image parts the fragment references; rewrite their Content-IDs and the `cid:`
   references to match; wrap HTML + images in `multipart/related`.
5. Set `In-Reply-To` to the original's Message-ID and `References` to the original's `References`
   plus its Message-ID. Prefix `Re:` if not already present. Default the recipient from
   `Reply-To`, else `From`.

The model supplies the new text and nothing else.

### Cuts

1. **Plain and markdown quoting.** No new dependency, no MIME work beyond what exists. Delivers
   correct replies to plain mail and correct plain replies to anything.
2. **HTML quoting.** Fragment extraction, blockquote assembly, `multipart/related`, cid
   rewriting. The substantial one.
3. **Interleaving for plain**, with a validator that refuses a body whose `> ` lines are not
   verbatim in the original. Only if it is actually wanted.

## Risks

- **Verbatim third-party markup is re-sent over the user's identity**, unsanitised, as
  Thunderbird does. Accepted deliberately (decision 4): altering the quote is the larger harm.
- **Remote images in the quote** fire from the recipient's machine and report back to whoever
  sent the original. Accepted (decision 5) for the same reason.
- **Size.** A long HTML thread with inline images makes a large draft, and it is appended over
  IMAP on every `replace`. Warned above 500 kB (decision 6), never truncated.
- **Broken cid references** - a fragment referencing a part that is not there, or two parts
  colliding after rewriting.
- **The plain projection of an HTML-only original** is `html2text` output: lossy, and it is what
  the recipient's plain-text reader sees.

## Decisions (HC, 2026-09-22)

The rule HC set: **follow Thunderbird, and do not alter the quoted original.** Everything below
follows from that.

1. **`quote` is a top-level parameter**, next to `format`. No Thunderbird analogue exists for
   this one - it is an API question - and the `format` precedent decides it: payload keys never
   reach the tool schema, which is how the format contract stayed invisible once already.
2. **`format` governs the new text only**, which is also what Thunderbird does: composing in
   plain text sends a plain-only reply with a text quote even when the original was HTML;
   composing in HTML sends both parts.
3. **Attribution copies Thunderbird's line**, `On 19.8.2026 15.18, Display Name wrote:` - day
   and month without leading zeros, dots throughout, time as `H.mm`. The format is **pinned as a
   constant, not produced by a locale-dependent formatter**: Thunderbird renders in the user's
   locale, but this process inherits whatever locale the MCP or CLI was launched with, so a
   locale call would make the same mailbox produce `19.8.2026` or `8/19/2026` depending on how
   the tool started.
4. **No sanitising.** The fragment is copied as it arrived. `<script>` and event handlers are
   inert in mail clients, which is what Thunderbird relies on, and the one consumer that is not
   a mail client - our own `read` - already sanitises and wraps untrusted content on the way in.
   Well-formedness is a separate matter: an unbalanced tag in the fragment can only break the
   rendering of the quote below it, because the new text is always above it.
5. **Remote images stay.** Stripping them would alter the quote, which is the thing we have
   decided not to do. They report back to whoever sent the original when the recipient opens the
   reply; that is true of every mail client.
6. **Warn above 500 kB**, measured on the assembled message, and write nothing differently -
   the draft is still correct, only large. Inline images dominate that number. A server refusing
   an oversized APPEND is reported as what it is; no truncation, because a truncated quote is a
   misquote.

## Open unknowns

- Nested `multipart/related` inside a quoted original.
- Originals whose `cid:` references point at parts that do not exist.
- Whether any provider rejects the assembled structure on APPEND.
