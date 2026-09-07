# Changelog

## [2.1.0] - 2026-09-07

### Added
- **Read operations retry once on a fresh connection.** A connection can die between the liveness
  probe and the command; that race cannot be probed away, only retried through. `read`, `search`
  and `attachment` now recover from it instead of surfacing an error.
- `AccountSession.run_op(operation, retry=...)`. A context manager cannot do this - an exception
  thrown back at its `yield` can be suppressed or transformed, but the caller's `with` body cannot
  be run again - so an operation that wants a retry passes its body as a callable.

### Notes
- **Retry is opt-in and off by default.** `create`, `replace` and `flag` never replay: an appended
  message would be duplicated and an expunge cannot be undone. A test asserts they do not use the
  retrying runner.

## [2.0.1] - 2026-09-07

### Fixed
- **`replace` could permanently delete messages it was not replacing.** It ended with a bare
  `EXPUNGE`, which RFC 3501 defines as removing *every* message carrying `\Deleted` in the selected
  mailbox - not the one just marked. Demonstrated on a live account: two drafts that had only been
  marked, and which the README described as recoverable, were destroyed by a later replace.
  It now uses `uid_expunge` (RFC 4315) to remove only the draft it superseded
- **Without UIDPLUS, nothing is expunged at all.** There is no scoped form to fall back to, so the
  superseded draft is left marked `\Deleted` for the user's mail client to clear, and the response
  says so. Expunging everything is not an acceptable fallback for expunging one thing
- **`replace` is confined to the Drafts folder.** The folder came from the caller and only the
  target message was checked for the `\Draft` flag, so an expunge could be pointed at any folder
  holding the user's own `\Deleted` messages. A non-Drafts folder is now refused before anything
  is written

## [2.0.0] - 2026-09-07

**Breaking: the action names now describe what IMAP actually does.** There is no edit — messages
are immutable — so what was called editing was always a replace.

### Changed
- `draft` without an id is now **`create`** (an `APPEND`)
- `draft` with an id is now **`replace`** (an `APPEND`, then an expunge of the draft it supersedes)
- `replace` reports "Draft Replaced" and, as before, gives the draft a **new id** — the old one is
  stale the moment a replace succeeds

### Removed
- **`edit`.** It fetched a draft, substituted text, and performed the same replace, which made its
  name a promise the protocol cannot keep: in-place mutation with a stable identity. It was already
  refused for any draft with an HTML body, and for a plain draft it did nothing the caller could not
  do by sending the body again

### Notes
- The expunge inside `replace` is the only deletion this client performs, and it is not exposed as
  an action. `flag ... +Deleted` marks a message and nothing more; your mail client does the
  deleting. `cleanup` removes downloaded attachment temp files locally and never touches the server

## [1.1.1] - 2026-09-07

### Fixed
- **Legacy keychain migration could destroy working credentials.** `_migrate_legacy` copied every
  key from the old `imap-stream` service into `imap-slim` unconditionally and then deleted the
  source, so a stale legacy entry replaced live credentials with itself and the originals were
  gone. It runs from `_keyring_get`, so any credential read could trigger it. It now refuses to
  run at all when the current service already holds accounts, never overwrites an existing key,
  and deletes a source key only after verifying its copy landed intact
- **The test suite reached the real login keychain.** An autouse fixture now replaces
  `imap_client.keyring` with an in-memory store for every test. A suite that can read live
  credentials could also trigger the migration above, which is how running tests became capable
  of destroying them

## [1.1.0] - 2026-09-07

The draft body contract is now explicit and visible, connection recovery is roughly 150x faster,
and the same mail actions are available as a skill-backed CLI that costs a session nothing until
it runs a command.

**Breaking:** `format` is required on every draft and is a top-level parameter, not a payload key.

### Added
- Fenced code blocks and pipe tables in markdown mode. Enabling the two extensions was the small
  part; they exposed four defects that existed all along and were invisible only because the
  extensions were off:
  - `preprocess_markdown` had no fence state and injected blank lines *inside* fenced content
  - `markdown_to_plain` ran its five substitutions over fenced code, so the plain alternative
    rewrote the author's `**literal**`, `~~literal~~`, `==literal==` and links
  - `autolink_urls` inserted an anchor inside `<pre><code>`, and nested a second anchor around the
    visible text of an existing one
  - a table with no blank line above it was not parsed as a table
- Fence recognition matches python-markdown rather than approximating it: column zero only, the
  closing delimiter run must repeat the opener exactly, a language tag may contain `#`, `.` or
  attribute syntax, a `~~~` inside a backtick fence is content, and an unterminated fence is not a
  fence. That last rule is what keeps a lone `~~~~~` working as the ASCII rule line it was

### Fixed
- A line break between two consecutive `>` lines now survives. Preprocessing inserted a blank line
  between them, splitting one quoted paragraph into two and defeating the newline rule inside
  quotes
- `mcp` is pinned below 2. The dependency was `mcp>=1.0.0` with no upper bound, and mcp 2.x renamed
  `FastMCP` to `MCPServer`, removing `mcp.server.fastmcp` entirely - so a fresh install resolved
  2.1.1 and the server died at import with `ModuleNotFoundError: No module named
  'mcp.server.fastmcp'`. The plugin was dead on arrival for anyone installing it today; existing
  installs only worked because their environment still held a 1.x resolved earlier. Migrating to
  the 2.x API is a separate decision

### Changed
- `format` is now a **required top-level parameter** on draft actions, not a key inside the payload
  JSON. Everything inside `payload` is a JSON string, so none of it ever reached the tool schema -
  no type, no enum, no description - which is why a session had no way to learn that its draft body
  was markdown without opening the help. It now appears in the served schema with its two values
- There is no default format at any layer, including `convert_body`. A silent default is what let a
  caller send markdown while believing it was sending plain text
- `format` inside the draft payload is now an explicit error naming the new parameter
- `edit` refuses any draft that carries an HTML body. It re-rendered the HTML from the stored plain
  part, which is the lossy projection, so one replacement to an unrelated word turned `<strong>`
  into `<em>` and dropped `<del>` and `<mark>` entirely. Nothing stores the source, so it cannot be
  done correctly - send the whole body with a draft-modify instead. Editing a plain draft is
  unchanged

### Fixed
- A newline inside a paragraph is now a line break in the HTML part (`nl2br`). A signature block
  arrived as one running line, and the HTML and plain alternatives of the same message disagreed
- A line that is only a run of `=`, `~`, `*` or `_` survives into the plain part. `=====` became
  `=`, `*****` became `***`, `_____` became `*_*` - an ASCII rule is not emphasis. Indented and
  quoted rules, CRLF and bare CR are all covered

### Fixed
- Connection recovery: a call made after an idle pause paid a full 30 s socket timeout before it could
  reconnect. A connection believed dead is now dropped with `shutdown()`, which sends nothing, and one
  idle past `CONNECTION_MAX_IDLE` (60 s, was 300 s) is dropped without being probed. Measured against a
  fake server that completes LOGIN then goes silent: 30 s before, 0.2 s after
- `LOGOUT` is no longer sent to a connection suspected dead - it is an IMAP command and blocks for the
  full socket timeout on a silent socket
- One IMAP connection is a single protocol stream, so the lease now holds the session lock for the whole
  operation. `get_folders` and `get_messages` previously ran their commands outside any lock
- Transport failures are no longer swallowed inside a lease: `modify_flags` recorded them as per-message
  errors and the snippet preview turned them into empty results, in both cases leaving the dead
  connection cached for the next call to trip over
- A rejected login no longer leaks its client - it was a local that nothing could close, holding a server
  slot until garbage collection
- `download_attachment` writes its file outside the connection lease, so a slow filesystem cannot be
  reported as a lost server connection

### Added
- Connection failures now name their cause - stale socket, rejected login, or connection quota - and the
  stage they failed at, instead of a single opaque `Error: TimeoutError: timed out`

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
