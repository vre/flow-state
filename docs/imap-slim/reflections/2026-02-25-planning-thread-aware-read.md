# 2026-02-25 Planning Reflections: Thread-Aware Read

Plan: `docs/imap-stream-mcp/plans/2026-02-25-thread-aware-read.md`

## How planning went

Problem emerged from manual acceptance testing of v0.5.1 — reading the VikingPLoP hotel thread (19 messages) consumed ~10k tokens where only ~500 were the newest message. HC flagged it immediately: "miksi jälkimmäinen haku oli yli 10ktoc?" The plan went from observation to written plan in one session.

**Design decisions.** HC drove three key calls:
- Binary choice (truncated vs full) instead of paginating individual quoted messages — original messages exist as separate IMAP messages in the same folder, quoted text is a redundant copy
- Language-independent attribution detection — line ending `:` followed by `>` lines catches "On ... wrote:", "Am ... schrieb:", etc. without maintaining a pattern list
- No forwarded message special handling — forwarded markers vary by client and language ("Forwarded message", "Lähetetty viesti", "Weitergeleitet"), unreliable detection adds complexity without results

HC also raised interleaved quoting as a risk: "joskus jotkut ihmiset harrastavat jotain outoa tapaa kirjoittaa kommenttejaan quoteketjuun sisään." This became the key safety mechanism — if quoted/unquoted blocks alternate multiple times, no truncation.

**Self-review** found 7 items. HC corrected each precisely: `len/4` is fine for token estimation, attribution `:` + `>` is sufficient (no language patterns needed), forwarded = no special handling, and default behavior can change (no existing workflows to break).

**Codex review** found 7 issues (3 high). Most impactful: truncation notice must be outside `<untrusted_email_content>` wrapper (security boundary), and HTML-only emails need `html2text` fallback (verified that html2text preserves `>` markers from blockquotes).

## HC's part

- Identified the problem from real usage (10k tokens for one email read)
- Drove the binary truncation decision with the key insight: quoted messages are redundant copies, originals are separate IMAP messages
- Proposed language-independent attribution detection pattern
- Raised interleaved quoting as a risk case
- Simplified forwarded message handling: "varies by language, don't bother"
- Corrected each self-review item with precise reasoning

## My part

- Quantified the problem (19-message thread, ~10k tokens, ~9k waste)
- Designed the detection algorithm (4 signal types, bottom-up scanning, interleaved safety)
- Structured the payload extension grammar (`^\d+(?::full)?$`)
- Placed truncation notice correctly relative to security wrapper
- Self-reviewed and incorporated both HC corrections and Codex findings
- Verified html2text `>` marker preservation via Codex research

## What I learned about planning

1. **Domain knowledge beats engineering instinct.** I would have designed pagination or per-message parsing. HC's "quoted messages are redundant copies of messages already in the folder" collapsed the entire problem to a binary choice. This is IMAP domain knowledge — the protocol stores individual messages, threading is reconstructed.

2. **Language-independent patterns beat pattern lists.** Instead of maintaining regex for "wrote:", "schrieb:", "kirjoitti:", etc., the structural pattern (line ending `:` + next line starts `>`) works across all languages. Structural detection > content detection.

3. **Security boundaries inform placement.** The `<untrusted_email_content>` wrapper isn't just formatting — it's a security boundary. Truncation metadata (message count, char count, `:full` hint) is trusted system output, not untrusted email content. Codex caught this: the notice must be outside the wrapper. Understanding *why* the wrapper exists determines *where* new content goes.
