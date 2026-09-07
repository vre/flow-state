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
- [ ] Preserve `multipart/related` MIME structure in `replace` (inline images lose `cid:` linkage)
- [x] Draft body format made explicit and required (v1.1.0) - `format` is a top-level parameter
- [x] Fenced code blocks and pipe tables (v1.1.0)
- [x] Connection recovery: discard rather than interrogate a dead socket (v1.1.0)
- [x] Skill-backed CLI alongside the MCP (v1.1.0)
- [x] Action names match IMAP: create / replace, no edit (v2.0.0)
- [ ] Inline spans crossing a newline: `**bold\ncontinued**` stays literal in the plain part while
      the HTML renders it. Known divergence, no decision to fix
- [ ] Attachments are the one path never exercised against a real server
