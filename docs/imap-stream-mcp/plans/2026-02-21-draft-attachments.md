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

Existing `attachment` action saves to temp (`/tmp/streammail/`), returns path. LLM can then use Read tool for images/text or pass path back to draft action.

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
2. attachment action → download to /tmp/streammail/report.pdf
3. draft action with attachments: ["/tmp/streammail/report.pdf"] → draft with attachment
4. User reviews in email client → send
```

### Implementation scope

**`imap_client.py`:**
- Add `import mimetypes` at top
- `create_draft()`: add `attachments: list[str] = None` param
  - For each path: validate (exists, is file, not symlink-to-dir, ≤25 MB)
  - `mimetypes.guess_type(path)` returns `(type/subtype, encoding)` — split on `/` to get `maintype`, `subtype` for `msg.add_attachment(data, maintype, subtype, filename=basename)`
  - Fallback: `application/octet-stream` → `maintype='application'`, `subtype='octet-stream'`
- `modify_draft()`: same attachment handling, but legacy `Message` problem:
  - `email.message_from_bytes()` returns legacy `Message`, not `EmailMessage`
  - Cannot call `add_attachment()` on legacy `Message`
  - Solution: build new `EmailMessage`, copy headers (Subject, To, Cc, In-Reply-To, References, Message-ID), extract body from old message, then walk old message parts to re-attach existing attachments (`walk()` → filter non-text parts → `add_attachment()`), then add new attachments
- Response includes attachment info (name + human-readable size) for both create and modify

**`imap_stream_mcp.py`:**
- Parse `attachments` from draft JSON payload, pass to `create_draft` / `modify_draft`
- Update `MailAction` description field (~line 203) — this is the LLM tool schema hint, always visible. Add `attachments?` to the draft JSON example: `'{"to":"x","subject":"y","body":"z","attachments?":["/path"]}'`
- Update draft help text

**Tests** (`tests/test_draft_attachments.py`):
- Mock pattern: patch `session.get_session` and `imap_client.get_credentials`
- Unit: draft with attachment creates multipart message with correct MIME type
- Unit: plain text (no HTML) + attachment — verify multipart/mixed structure
- Unit: missing file raises clear error
- Unit: directory path rejected, symlink-to-dir rejected
- Unit: file >25 MB rejected with actionable error
- Unit: modify with attachments preserves threading (In-Reply-To, References headers)
- Unit: modify preserves existing attachments from original draft

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
- Path validation: file must exist, be a regular file, be readable. Reject directories and symlinks pointing to directories. No glob/wildcard.
- modify_draft: rebuilds as `EmailMessage` (original uses legacy `Message` from `email.message_from_bytes()`), copies existing attachments via walk + re-attach, then adds new ones. Avoids surprise data loss when user added attachments via email client.
- Security: LLM already has file access via Read/Bash tools. MCP attachment adds no new attack surface — it just avoids routing binary content through the LLM context.

## Out of scope

- Save attachment to user-specified path (current: always `/tmp/streammail/`). Separate feature.
- Inline images in HTML body. Only discrete attachments.

## Acceptance Criteria

- [ ] `create_draft` with `attachments` produces multipart email with correct MIME parts
- [ ] `create_draft` plain text (no HTML) + attachment produces valid multipart/mixed
- [ ] `modify_draft` with `attachments` works, preserves threading headers and existing attachments
- [ ] Error on missing/unreadable file with actionable message
- [ ] Error on directory, symlink-to-dir, or >25 MB file
- [ ] `MailAction` description field includes `attachments?` hint
- [ ] Help text updated
- [ ] Response format includes attachment names + sizes for both create and modify
- [ ] Tests for: single attachment, multiple attachments, plain text + attachment, missing file, invalid path types, oversize file, modify preserves existing attachments, roundtrip with download
- [ ] Manual test: create draft with PDF, verify visible in Thunderbird
