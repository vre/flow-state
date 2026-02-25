# Changelog

## [0.6.0] - 2026-02-25

### Added
- Attachment indicator `[att:N]` in list and search results — shows attachment count from BODYSTRUCTURE without fetching message body
- New `bodystructure.py` module for IMAP BODYSTRUCTURE parsing
- Handles `Content-Disposition: attachment` and `inline` with filename (matches `read_message()` predicate)
- Type-specific disposition index: text/*[9], basic[8], message/rfc822[11]

## [0.5.1] - 2026-02-24

### Added
- `edit` action for surgical draft modifications (old/new text replacement without full body rewrite)
- Inline image separation in `read`: real attachments shown prominently, signature images compactly
- Format validation in `convert_body()`: rejects unknown formats with actionable error message

### Fixed
- Double IMAP fetch eliminated in `edit_draft` (prefetched draft passed to `modify_draft`)
- `edit_draft` prefetch uses `readonly=True` (was incorrectly opening writable)

### Changed
- `read` response shows `[index]` for each attachment/inline image (matches `attachment` action index)
- `MailAction.action` and help topics updated with `edit`

## [0.5.0] - 2026-02-22

### Added
- File attachment support for drafts (`attachments` field in draft payload)
- Forward attachment workflow: download → attach to new draft
- `_attach_files` helper with fail-fast validation (absolute path, is_file, 25 MB max)
- MIME type auto-detection via `mimetypes.guess_type()`, fallback to `application/octet-stream`
- Draft help text: Attachments section, Forward Attachment Workflow

### Fixed
- `modify_draft` now preserves existing attachments from original draft (was silently dropping them)
- `modify_draft` uses append-before-delete to prevent data loss
- Zero-byte attachments preserved correctly (`if payload is not None:` guard)
- OSError during file read wrapped as IMAPError with actionable message

### Changed
- `MailAction.action` description includes `attachment` and `cleanup`
- `MailAction.payload` description includes `format?` and `attachments?`
- Overview help topic lists all actions including `attachment` and `cleanup`
- `modify_draft` response includes both preserved and newly added attachments

## [0.4.1] - 2026-01-30

### Added
- Flag-based search: `flagged`, `unread`, `seen`, `answered`, `deleted` and variants (`is:flagged`, `flagged:yes`, `starred`)
- Flags displayed in search results (matching list action format)

## [0.4.0] - 2026-01-27

### Added
- Connection keepalive (5 min idle timeout) reduces connection overhead
- Folder list caching (persists until MCP shutdown)
- Message list caching with IMAP metadata validation (UIDVALIDITY, UIDNEXT, EXISTS)
- Cache automatically updated on flag operations
- Cache invalidated on draft create/modify operations

## [0.3.0] - 2026-01-27

### Added
- `flag` action to add/remove flags and labels on messages
- Batch flag operations on multiple messages
- Support for standard IMAP flags (Seen, Flagged, Answered, Deleted, Draft)
- Support for keywords/labels ($label1-5, custom)
- Unit tests for flag parsing functions

### Changed
- Flags displayed without backslash prefix (Seen instead of \Seen)
- Security description updated: "No destructive operations" instead of "Read-only"

## [0.2.0] - 2026-01-22

### Added
- Multi-account support with named accounts
- `accounts` action to list configured accounts
- `account` parameter for all actions
- `attachment` action to download attachments
- `cleanup` action to remove temp files
- Draft modification with `id` parameter
- Reply threading preservation (In-Reply-To, References)
- Markdown formatting in drafts (bold, italic, links, lists)
- HTML alternative in draft emails
- Context poisoning protection in read action
- URL autolinking in markdown email body conversion
- Environment variable option for IMAP configuration

### Changed
- Keychain storage uses `{account}:` prefix for all keys
- setup.py rewritten for multi-account management
- MCP installation uses plugin system

### Fixed
- Flags display (`\Draft` instead of `b'\\Draft'`)
- Bytes handling in IMAP responses
- HTML messages converted to readable text
- Markdown list preprocessing (avoid wrapping list items in paragraph tags)

## [0.1.0] - 2026-01-16

### Added
- Initial release
- Single `use_mail` tool with action dispatcher
- Actions: list, read, search, draft, folders, help
- Keychain credential storage
- Environment variable fallback
- SSL/TLS IMAP connection
