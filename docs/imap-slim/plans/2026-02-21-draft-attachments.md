# Draft Attachments

## Problem

LLM can download attachments from emails (`attachment` action → temp file), but cannot attach files to drafts. Draft creation (`create_draft`, `modify_draft`) only supports text/HTML body.

User workflow gap: "forward this PDF to X" or "reply with the attached spreadsheet" requires manual intervention.

## Goal

Add file attachment support to drafts. LLM provides file path(s), MCP handles binary I/O — LLM never reads file content.

## Current State

| Direction | Status | Implementation |
|-----------|--------|---------------|
| Mail → file | Works | `attachment` action → `download_attachment()` → temp file |
| File → draft | Missing | `create_draft()` / `modify_draft()` use `msg.set_content()` only |

Existing `attachment` action saves to temp (`Path(tempfile.gettempdir()) / "streammail"`), returns path. On macOS this resolves to `/private/var/folders/.../T/streammail/`, not `/tmp/`. LLM can then use Read tool for images/text or pass path back to draft action.

**Known issue:** `modify_draft()` already rebuilds the message from scratch — existing attachments added via email client are silently dropped. This plan fixes that as part of the attachment work.

## Design

### API

Extend `draft` action payload with optional `attachments` field:

```
{action: "draft", payload: '{"to":"x@y","subject":"Y","body":"See attached","attachments":["/path/to/file.pdf"]}'}
```

- `attachments`: list of absolute file paths
- Works with both create and modify
- MCP reads files as binary, attaches as MIME parts via `EmailMessage.add_attachment()`
- Filename derived from path basename
- Content-type guessed via `mimetypes.guess_type()`, fallback `application/octet-stream`

### Roundtrip: forward attachment

```
1. read message → see "Attachments: (1) report.pdf (245 KB)"
2. attachment action → download to <tempdir>/streammail/report.pdf
3. draft action with attachments: ["<tempdir>/streammail/report.pdf"] → draft with attachment
4. User reviews in email client → send
```

### Implementation scope

**`imap_client.py`:**
- Add `import mimetypes` at top
- Extract shared helper `_attach_files(msg: EmailMessage, paths: list[str]) -> list[dict]`:
  - **Fail-fast:** validate ALL paths first, raise on first failure before reading any file data or modifying the message
  - For each path: `Path(p).is_absolute()` (reject relative), `Path.is_file()` (covers dirs and symlinks-to-dirs), size ≤25 MB via `Path.stat().st_size` before `read_bytes()`
  - `mimetypes.guess_type(path)` returns `(type, encoding)` — type can be `None` for unknown extensions. If `None` or no `/` in type string: fallback `application/octet-stream`. Otherwise split on `/` to get `maintype`, `subtype` for `msg.add_attachment(data, maintype, subtype, filename=basename)`
  - Returns list of `{name, size}` dicts for response formatting
- `create_draft()`: add `attachments: list[str] = None` param, call `_attach_files()`
- `modify_draft()` — **this is the largest piece of work**, refactoring required:
  - Current: reads original via `email.message_from_bytes()` (legacy `Message`, line 714), rebuilds as `EmailMessage` but **silently drops existing attachments**
  - New: build `EmailMessage` with the **new body from parameters** (not extracted from original — `modify_draft` always receives new body), copy headers (Subject, To, Cc, In-Reply-To, References) — generate **new Message-ID** (correct behavior: modified draft is a new message), **walk original parts to re-attach existing attachments** (`walk()` → identify attachments by `Content-Disposition` being `attachment` OR `inline` with a filename — matches existing `download_attachment` logic at line 381/454 → `add_attachment()`), then add new attachments via `_attach_files()`. Note: re-attached inline parts become `Content-Disposition: attachment` — acceptable, full inline MIME metadata preservation is out of scope.
  - **Append-before-delete:** build and append new draft first, only delete old draft after successful append. Current code deletes first (line 765/781) — with attachments adding failure points, this order change prevents data loss.
  - This fixes an existing bug (attachment loss on modify) as a side effect
- Response includes attachment info (name + human-readable size) for both create and modify — for `modify_draft`, include **both preserved existing and newly added** attachments in the response

**`imap_stream_mcp.py`:**
- Parse `attachments` from draft JSON payload, pass to `create_draft` / `modify_draft`
- Update `MailAction.payload` description (~line 202): add `attachments?` AND the already-missing `format?` field (NOT `html?` — html is derived from `format` via `convert_body()`, not a payload field): `'{"to":"x","subject":"y","body":"z","format?":"markdown","attachments?":["/path"]}'`
- Update `MailAction.action` description (~line 193): add missing `attachment` and `cleanup` to the action list
- Update overview help topic (~line 227): add `attachment` and `cleanup` to the action summary list
- Update draft help text

**Tests** — extend existing files in `tests/imap-stream-mcp/`. `conftest.py` exists there already.

`tests/imap-stream-mcp/test_imap_client.py` (extend):
- Unit `_attach_files`: correct MIME type detection, fallback to octet-stream for unknown extension, `None` type handling
- Unit `_attach_files`: missing file → clear error, relative path → rejected, directory → rejected, >25 MB → rejected
- Unit `create_draft` + attachment: multipart message with correct MIME parts
- Unit `create_draft` plain text (no HTML) + attachment: valid multipart/mixed
- Unit `modify_draft` + new attachments: preserves threading headers (In-Reply-To, References)
- Unit `modify_draft`: preserves existing attachments (both `attachment` and `inline`+filename) from original draft
- Unit `modify_draft`: append-before-delete — verify append called before delete
- Unit roundtrip: mock `download_attachment` returning a temp path, pass path to `create_draft` — verify attachment in resulting message

`tests/imap-stream-mcp/test_imap_stream_mcp.py` (extend):
- MCP-layer: `attachments` field parsed from draft JSON payload, validated as `list[str]`
- MCP-layer: invalid `attachments` type (string instead of list) → clear error
- MCP-layer: response output includes attachment names + sizes

### Response format

Draft response includes attachment info when present:

```
# Draft Created

**To:** x@y.com
**Subject:** See attached
**Attachments:** report.pdf (245 KB), data.csv (12 KB)
**Saved to:** Drafts
```

## Constraints

- File size: max 25 MB per file. Check `Path.stat().st_size` before `read_bytes()` to avoid loading oversized files into memory. Error: `"File too large: {name} is {size} MB (max 25 MB)"`.
- Path validation: `Path.is_absolute()` required, then `Path.is_file()` — returns `False` for directories and symlinks-to-directories, `True` for regular files and symlinks-to-files. No glob/wildcard.
- modify_draft: rebuilds as `EmailMessage` (original uses legacy `Message` from `email.message_from_bytes()`), copies existing attachments via walk + re-attach, then adds new ones. Append-before-delete to prevent data loss. **Fixes existing bug** where modify silently dropped attachments from the original draft.
- Security: LLM already has file access via Read/Bash tools. MCP attachment reads arbitrary absolute paths as binary — this adds no new capability beyond what Read/Bash provide. No path restriction beyond is_absolute + is_file. Note: 25 MB per-file limit does not account for base64 MIME overhead (~37% increase); total message size depends on server limits — IMAP append will return an error if exceeded.

## Out of scope

- Save attachment to user-specified path (current: always `tempfile.gettempdir() / "streammail"`). Separate feature.
- Inline images in HTML body. Only discrete attachments.

## Acceptance Criteria

- [x] `create_draft` with `attachments` produces multipart email with correct MIME parts
- [x] `create_draft` plain text (no HTML) + attachment produces valid multipart/mixed
- [x] `modify_draft` with `attachments` works, preserves threading headers and existing attachments
- [x] Error on missing/unreadable file with actionable message
- [x] Error on relative path, non-file path, or >25 MB file
- [x] `modify_draft` appends new draft before deleting old (append-before-delete)
- [x] `modify_draft` preserves existing inline+filename attachments from original
- [x] `MailAction.payload` description includes `attachments?`, `format?` hints
- [x] `MailAction.action` description includes `attachment` and `cleanup`
- [x] Help text updated — overview help now includes `attachment` and `cleanup` actions
- [x] Response format includes attachment names + sizes for both create and modify — `modify_draft` now reports preserved + new attachments
- [x] Tests (imap_client): single attachment, multiple, plain text + attachment, missing file, relative path, oversize, modify preserves existing attachments, append-before-delete, roundtrip
- [x] Tests (imap_stream_mcp): payload parsing, invalid attachments type, response formatting
- [x] Manual test: create draft with attachment (verified in Thunderbird), modify draft adds second attachment while preserving first (verified in Thunderbird)

## Reflection

### What went well

- Plan was thorough enough that implementation was straightforward — no architectural surprises
- TDD approach caught nothing during red→green (clean implementation), but gave confidence for the modify_draft refactor
- Three-round review process (self-review, codex review, fixes) caught real bugs: zero-byte attachment loss (`if payload:` vs `if payload is not None:`), missing OSError handling, shallow input validation
- Append-before-delete pattern was identified in planning and implemented correctly first time
- Existing test infrastructure (MockIMAPClient, conftest fixtures) made new tests easy to write

### What changed from plan

- Added OSError→IMAPError wrapping in `_attach_files` (not in original plan, found in codex review)
- Added element-type validation for attachments list in MCP layer (not in plan)
- Added zero-byte attachment preservation test (not in plan)
- Plan had 14 acceptance criteria, 13 met via automated tests, 1 pending manual test

### Lessons learned

- `if payload:` vs `if payload is not None:` is a classic Python trap — empty bytes `b""` is falsy. Code review caught what self-review missed.
- Codex review found 3 actionable issues that self-review did not. External review adds value even after careful self-review.
- The plan's explicit Content-Disposition filtering spec (`attachment` OR `inline` with filename) translated directly to code without ambiguity — precise specs prevent implementation debates.
- Second codex review (post-implementation) found 2 implementation gaps missed by first review: modify_draft response omitting preserved attachments, overview help not updated. Plan review is not enough — implementation review against the plan catches different class of bugs.
