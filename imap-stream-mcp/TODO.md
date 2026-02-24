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
- [ ] Attachment indicator (`[att:N]`) in list/search — `docs/imap-stream-mcp/plans/2026-02-24-attachment-indicator.md`
- [ ] Snippet (~100 chars preview) in list/search — `docs/imap-stream-mcp/plans/2026-02-24-list-search-snippet.md` (depends on attachment indicator)
- [ ] Thread-aware read: truncate quoted replies to reduce token count (8-msg Outlook thread = ~10k tokens)
- [ ] Preserve `multipart/related` MIME structure in modify_draft (inline images lose `cid:` linkage)
