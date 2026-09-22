# TODO

## Future Ideas

- [x] Cache - Folder listing/message caching (v0.4.0)
- [ ] Search operators - Complex criteria (AND/OR)
- [x] Flag-based search - is:flagged, unread, seen, answered (v0.4.1)
- [x] Flag management - Mark as read/important (v0.3.0)
- [ ] Safe Moving messages from folder to another
- [x] Marking messages for deletion (v0.3.0, via \Deleted flag)
- [x] Marking messages as spam/not spam (v0.3.0, via $Junk keyword)
- [x] Support for Labels (v0.3.0, via keywords)
- [x] Attachment upload to drafts (v0.5.0)
- [x] Attachment indicator (`[att:N]`) in list/search (v0.6.0) — `docs/imap-slim/plans/2026-02-24-attachment-indicator.md`
- [x] Snippet preview (`preview: true/false`) in list/search (v0.7.0) — `docs/imap-slim/plans/2026-02-24-list-search-snippet.md`
- [x] Thread-aware read: truncate quoted replies to reduce token count (v0.6.1) — `docs/imap-slim/plans/2026-02-25-thread-aware-read.md`
- [x] Depth-aware quote truncation: `:N` modifiers for progressive disclosure of reply chains (v0.7.1) — `docs/imap-slim/plans/2026-03-09-depth-aware-quote-truncation.md`
- [ ] Preserve `multipart/related` MIME structure in `replace` (inline images lose `cid:` linkage).
      Since 2.0.1 such a draft is refused rather than written without it
- [x] Draft body format made explicit and required (v2.0.0) - `format` is a top-level parameter
- [x] Fenced code blocks and pipe tables (v2.0.0)
- [x] Connection recovery: discard rather than interrogate a dead socket (v2.0.0)
- [x] Skill-backed CLI alongside the MCP (v2.0.0)
- [x] Action names match IMAP: create / replace, no edit (v2.0.0)
- [ ] Inline spans crossing a newline: `**bold\ncontinued**` stays literal in the plain part while
      the HTML renders it. Known divergence, no decision to fix
- [x] Attachments and cleanup exercised against a real server (2026-09-07)
- [x] Multi-account switching verified across three accounts (2026-09-07)
- [x] Read operations retry once on a fresh connection (v2.0.0)
- [x] `setup.py`: remove and set-default in the menu, editable fields, default marked (v2.0.0)
- [ ] Retry has never been proven against a connection that dies mid-command on a real server
- [ ] `replace` rebuilds the To header from the envelope; a malformed address becomes
      `user@MISSING_DOMAIN`. Judged not worth fixing - the sending client composes the real header
