# Changelog

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
