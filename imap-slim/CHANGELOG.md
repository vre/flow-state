# Changelog

## [2.0.1] - 2026-09-14

A cross-model review of 2.0.0 found these. The suite passed throughout; every one came from
running the code.

### Fixed

- **`replace` silently dropped an attached email.** `message/rfc822` has no decoded payload, so the
  part was skipped and the original draft then expunged. Attached messages are now carried over,
  and any part that cannot be copied aborts the replace before anything is written.
- **`debug_imap.py --debug` printed the password.** Tracing was enabled before `LOGIN`, which
  `imaplib` echoes in full. It starts after authentication.
- **An empty `to`, `cc` or `subject` could not clear a field.** Truthiness could not tell "not
  supplied" from "explicitly empty", so `cc: ""` kept the previous recipients.
- **`since:` and `before:` sent an unusable date.** `2024-01-01` went to the server verbatim; IMAP
  wants `1-Jan-2024` (RFC 3501 §9).
- **A non-ASCII search failed before reaching the server.** No charset was named, so the term was
  encoded as ASCII and raised locally. `UTF-8` is declared when the criteria need it.
- **A failed `flag` operation exited 0.** The CLI decided from the first characters of the rendered
  text; the dispatcher now marks a failed response and the exit code follows it.
- **Cached message lists ignored the request.** A list cached for `limit=10` answered `limit=50`,
  and previews were returned or withheld regardless of what was asked. Flags, which move without
  touching UIDVALIDITY/UIDNEXT/EXISTS, are now refetched after 30 s.
- **Renaming an account could split it across two names.** Each key was deleted right after being
  copied. All keys are copied and verified before any original is removed.
- `list` and `search` put subjects, senders and snippets inside the same `[EXTERNAL_EMAIL_…]`
  boundary `read` uses. Sanitizing strips markers but leaves ordinary prose, which arrived
  unmarked.
- `create` and `replace` report the new draft's id, which `SKILL.md` already told callers to use.
- `help draft` appeared in `SKILL.md` and the README; the topics are `create` and `replace`.

## [2.0.0] - 2026-09-07

Everything below is relative to 1.0.0. The intermediate versions this work passed through were
never published.

**Breaking:**

- `draft` and `edit` are replaced by `create` and `replace`. IMAP messages are immutable, so what
  was called editing always appended a new version and expunged the old. A replaced draft gets a
  new id.
- `format` is a required top-level parameter, not a payload key, with no default. Everything inside
  `payload` is a JSON string and never reaches the tool schema, so the contract was undiscoverable
  and the default silently produced HTML for callers who meant plain text.

### Fixed

- **Legacy keychain migration destroyed working credentials.** It copied every `imap-stream` key
  over `imap-slim` unconditionally and deleted the source, on every credential read. It now refuses
  when the current service holds accounts, never overwrites, and deletes a source key only after
  verifying its copy.
- **`replace` could permanently delete messages it was not replacing.** A bare `EXPUNGE` removes
  every `\Deleted` message in the mailbox. It now uses `uid_expunge` for exactly the superseded
  draft, is refused outside the Drafts folder, and expunges nothing at all without UIDPLUS.
- **`mcp>=1.0.0` made fresh installs dead on arrival.** mcp 2.x removed `mcp.server.fastmcp`; the
  dependency is pinned `<2`.
- A call made after an idle pause paid a full 30 s socket timeout before recovering. A connection
  believed dead is now discarded without sending anything: ~0.2 s.
- Line breaks were lost from the HTML part, so a signature block arrived as one running line.
- A line of only `=`, `~`, `*` or `_` was mangled in the plain part - `=====` became `=`.
- `edit` silently degraded formatting: bold became italic, strikethrough and highlight vanished.
- Both READMEs claimed "No destructive operations - No EXPUNGE" while the code had expunged for
  as long as it existed.

### Added

- **`imap-slim-cli`**, the same actions as a skill-backed CLI. An enabled MCP server loads ~814
  tokens into every session; the skill costs ~41 until a command runs. Both dispatch through one
  `run_action`, so they cannot drift.
- Fenced code blocks and pipe tables, with fence content sent exactly as written in both parts.
- Read operations retry once on a fresh connection. Writes never replay.
- `setup.py` manages accounts interactively: remove, set default, and edit any field without
  retyping, including renaming an account.
- Decisions with tradeoffs are recorded in `docs/imap-slim/adrs/`.

## [1.0.0] - 2026-05-30

### Fixed
- Multi-account support: `account` parameter now wired through `use_mail()` to all 9 imap_client calls
- Draft From header uses correct account credentials instead of always defaulting

### Added
- `account` field on `MailAction` for multi-account selection

### Security
- New `injection_defense.py` module: NFKC normalization, invisible/BIDI strip, expanded marker coverage (chat-template tokens, Llama markers, system markers, role XML), randomized nonce wrapper
- Defense applied to all untrusted text reaching LLM: subject, from, body, snippet, attachment filename + content_type, folder names, account names
- Wrapper switched from fixed `<untrusted_email_content>` XML tags to per-call randomized `[EXTERNAL_EMAIL_<8hex>_START]` / `[EXTERNAL_EMAIL_<8hex>_END]` delimiters (defeats pre-computable boundary attacks)
- Banner aggregation in list/search/folders/accounts: shown once at top when any row triggers
- `use_mail` docstring (FastMCP tool description) explicitly tells the LLM that content inside the markers is untrusted

### Removed
- `_contains_injection_patterns`, `_sanitize_for_delimiters`, `_wrap_email`, `UNTRUSTED_WARNING` (replaced by new module)

## [0.7.1] - 2026-03-09

### Added
- Depth-aware quote truncation: `read=67:1` returns depth 0+1 (inline replies), `read=67:2` for deeper, `read=67:full` for everything
- `_find_all_boundaries()` detects all separator patterns in a message and returns sorted boundary indices
- Truncation notices guide to next depth level (`:N+1`) and `:full`
- Boundary precedence rules: Outlook wins over localized, minimum 3-line gap between boundaries

### Changed
- `split_quoted_tail()` accepts `depth` parameter, cuts at Nth boundary instead of always first
- `read_message()` accepts `depth` parameter, passed through to `split_quoted_tail()`
- Interleaved reply bypass removed — was returning full body (44k+), now returns depth 0 by default with deeper levels via `:N`

## [0.7.0] - 2026-03-03

### Added
- Body snippet preview in list/search results — first ~100 chars of message body shown as blockquote line
- Mandatory `preview` parameter for list/search: `preview: true` fetches snippets, `preview: false` skips (0 extra IMAP roundtrips)
- Two-step FETCH: BODYSTRUCTURE parsing identifies text/plain (or HTML fallback), then `BODY.PEEK[section]<0.600>` fetches partial body
- Decoding pipeline: transfer encoding (7BIT/BASE64/QUOTED-PRINTABLE) → charset → HTML strip → whitespace collapse → word-boundary truncation
- `get_body_peek()` consolidated in `bodystructure.py` with prefix-match key lookup (handles server response variants)
- Prompt injection check on snippets via existing `_contains_injection_patterns()`

## [0.6.1] - 2026-02-25

### Added
- Thread-aware `read`: quoted reply tails truncated by default, reducing token usage >80% on long threads
- 5 quote-boundary detection signals: Outlook `____From:` separator, localized Outlook headers (Finnish/German/etc.), attribution+`>` lines, classic `>` tail, bare `>` lines
- Interleaved reply safety: alternating quoted/unquoted blocks preserved as primary content
- `:full` modifier for `read` payload (`"123:full"`) to retrieve complete message with quoted tail
- Truncation notice outside `<untrusted_email_content>` wrapper with char count, message estimate, and `:full` hint
- HTML-only email support: `html2text` output used for quote detection when no plain text part exists

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
