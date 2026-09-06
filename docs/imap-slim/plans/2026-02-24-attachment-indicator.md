# Attachment Indicator in List/Search Results

## Problem

LLM must call `read` to determine if a message has attachments. Each unnecessary `read` costs ~2000+ tokens (full body + headers + attachment metadata). In sessions where LLM browses 10-20 messages looking for one with an attachment, this wastes 20-40k tokens.

**Origin:** Competitive analysis (`docs/imap-stream-mcp/research/2026-02-24-email-mcp-servers-survey.md`). marlinjai/email-mcp returns attachment metadata in search results. No other IMAP MCP shows attachment info in list/search.

## Current State

### List response (`session.py` line 231)
IMAP FETCH: `ENVELOPE, FLAGS, RFC822.SIZE`

```
# Messages in INBOX
Showing 5 messages

**[123]** Subject line here
  From: user@example.com | 2026-02-24 14:30 [seen,flagged]
```

### Search response (`imap_client.py` line 570)
IMAP FETCH: `ENVELOPE, FLAGS`

```
# Search Results: from:boss
Found 3 in INBOX

**[456]** Matching subject
  From: person@host.com | 2026-02-22 11:22
```

### Fields per message

| Field | list | search | read | proposed list | proposed search |
|---|---|---|---|---|---|
| ID | x | x | x | x | x |
| Subject | x | x | x | x | x |
| From | x | x | x (full list) | x | x |
| Date | x | x | x | x | x |
| Flags | x | x | x | x | x |
| Size | x | - | - | x | - |
| Body | - | - | x | - | - |
| Attachments | - | - | x | **[att:N]** | **[att:N]** |

## Proposed Change

Add `[att:N]` to the response line when a message has N>0 attachments.

**Proposed format:**
```
**[123]** Subject line here
  From: user@example.com | 2026-02-24 14:30 [seen] [att:2]

**[124]** Another subject (no attachments — no indicator)
  From: sender@domain.com | 2026-02-23 09:15
```

## Implementation

### IMAP BODYSTRUCTURE

IMAP `BODYSTRUCTURE` returns the MIME tree without fetching body content. From it, attachment count can be derived by counting parts that match the attachment predicate.

**Attachment definition (single rule):** A MIME part is counted as an attachment if `Content-Disposition: attachment` OR `Content-Disposition: inline` with a `filename` parameter. This matches existing `read_message()` behavior (imap_client.py:381). Inline images without filename (e.g. CID-referenced `<img>`) are NOT counted.

Change FETCH calls:
- list: `ENVELOPE, FLAGS, RFC822.SIZE` → `ENVELOPE, FLAGS, RFC822.SIZE, BODYSTRUCTURE`
- search: `ENVELOPE, FLAGS` → `ENVELOPE, FLAGS, BODYSTRUCTURE`

### BODYSTRUCTURE parsing (verified against IMAPClient 3.1.0)

IMAPClient returns `BodyData` objects — a `tuple` subclass with `is_multipart` property. All string values are `bytes`, not `str`.

**Single-part text/* message (12 elements):**
```python
BodyData((
    b"TEXT",             # [0] maintype
    b"PLAIN",            # [1] subtype
    (b"CHARSET", b"utf-8"),  # [2] params (flat key/value tuple)
    None,                # [3] body-id
    None,                # [4] description
    b"7BIT",             # [5] encoding (Content-Transfer-Encoding)
    16,                  # [6] size in bytes
    1,                   # [7] number of lines (text/* only!)
    None,                # [8] MD5 (extension)
    None,                # [9] DISPOSITION — None or (b'attachment', (b'filename', b'x'))
    None,                # [10] language (extension)
    None,                # [11] location (extension)
))
body.is_multipart  # False
```

**Single-part basic type (APPLICATION, IMAGE, etc.) (11 elements — no `lines` field):**
```python
BodyData((
    b"APPLICATION",      # [0] maintype
    b"PDF",              # [1] subtype
    (b"NAME", b"report.pdf"),  # [2] params
    None,                # [3] body-id
    None,                # [4] description
    b"BASE64",           # [5] encoding
    5000,                # [6] size in bytes
    None,                # [7] MD5 (extension) — NOT lines!
    (b"attachment", (b"filename", b"report.pdf")),  # [8] DISPOSITION
    None,                # [9] language (extension)
    None,                # [10] location (extension)
))
```

**Single-part message/rfc822 (14 elements — extra envelope, body, lines):**
```python
BodyData((
    b"MESSAGE",          # [0] maintype
    b"RFC822",           # [1] subtype
    None,                # [2] params
    None,                # [3] body-id
    None,                # [4] description
    b"7BIT",             # [5] encoding
    1234,                # [6] size in bytes
    None,                # [7] envelope
    BodyData((...)),     # [8] nested body (BODYSTRUCTURE of enclosed message)
    42,                  # [9] lines
    None,                # [10] MD5 (extension)
    (b"attachment", (b"filename", b"fwd.eml")),  # [11] DISPOSITION
    None,                # [12] language (extension)
    None,                # [13] location (extension)
))
```

**Disposition index varies by content type (verified empirically against IMAPClient 3.1.0):**

| Content type | Tuple length | Disposition index | Reason |
|---|---|---|---|
| text/* | 12 | **[9]** | Has `lines` at [7] |
| basic (application/*, image/*, audio/*, video/*) | 11 | **[8]** | No `lines` field |
| message/rfc822 | 14 | **[11]** | Extra envelope[7], body[8], lines[9] |
| multipart | 6 | **[3]** | Always None in practice |

**Multipart message:**
```python
BodyData((
    [part1_BodyData, part2_BodyData],  # [0] list of parts (recursive)
    b"MIXED",            # [1] subtype
    (b"boundary", b"==abc=="),  # [2] params
    None,                # [3] DISPOSITION
    None,                # [4] language
    None,                # [5] location
))
body.is_multipart  # True — checks isinstance(body[0], list)
```

**Key difference:** disposition index varies by content type (see table above). `_get_disposition()` encapsulates this logic.

**Disposition format:**
- `None` — no Content-Disposition header
- `(b'attachment', (b'filename', b'report.pdf'))` — attachment with params
- `(b'inline', (b'filename', b'logo.png'))` — inline with params

**Nested multipart example (verified from IMAPClient tests):**
```
multipart/mixed
├── multipart/alternative  (part 1)
│   ├── text/html          (part 1.1)
│   └── text/plain         (part 1.2)
└── text/plain [att]       (part 2, disposition=attachment)
```

**Attachment counting algorithm:**
```python
def _has_filename(body: tuple, disp: tuple | None) -> bool:
    """Check for filename in disposition params OR Content-Type name param.

    Python's email.message.get_filename() checks both:
    1. Content-Disposition filename parameter
    2. Content-Type name parameter (fallback)
    BODYSTRUCTURE exposes these separately:
    - disp[1] has disposition params (filename)
    - body[2] has Content-Type params (name)
    """
    if disp and len(disp) > 1 and disp[1]:
        params = disp[1]
        for j in range(0, len(params), 2):
            if params[j].lower() == b'filename':
                return True
    ct_params = body[2]
    if ct_params:
        for j in range(0, len(ct_params), 2):
            if ct_params[j].lower() == b'name':
                return True
    return False

def _is_attachment(body: tuple, disp: tuple | None) -> bool:
    """Match existing read_message() logic: attachment OR inline with filename."""
    if not disp:
        return False
    disp_type = disp[0].lower()
    if disp_type == b'attachment':
        return True
    if disp_type == b'inline' and _has_filename(body, disp):
        return True
    return False

def _get_disposition(body: tuple) -> tuple | None:
    """Get disposition from single-part BODYSTRUCTURE, handling type-specific indices.

    IMAPClient does NOT normalize indices — tuple layout follows RFC 3501:
    - text/*:    [7]=lines, [8]=MD5, [9]=disposition  (12 elements)
    - basic:     [7]=MD5,   [8]=disposition            (11 elements, no lines)
    - message/rfc822: [7]=envelope, [8]=body, [9]=lines, [10]=MD5, [11]=disp (14 elements)

    Verified empirically: IMAPClient 3.1.0 parse_fetch_response() returns
    raw tuples matching these indices exactly.
    """
    maintype = body[0].lower()
    if maintype == b"message" and body[1].lower() == b"rfc822":
        return body[11] if len(body) > 11 else None
    if maintype == b"text":
        return body[9] if len(body) > 9 else None
    # Basic types: application/*, image/*, audio/*, video/*
    return body[8] if len(body) > 8 else None

def count_attachments(body) -> int:
    """Count attachments in BODYSTRUCTURE. Accepts BodyData or plain tuple."""
    if isinstance(body[0], list):  # multipart detection without .is_multipart
        return sum(count_attachments(part) for part in body[0])
    disp = _get_disposition(body)
    return 1 if _is_attachment(body, disp) else 0
```

**Consistency with existing code:** Matches `read_message()` (imap_client.py:381) predicate: `disposition == "attachment" or (disposition == "inline" and get_filename())`. Python's `get_filename()` checks both `Content-Disposition filename` and `Content-Type name` params as fallback. `_has_filename()` replicates this by checking both `disp[1]` (disposition params) and `body[2]` (Content-Type params).

**Testability:** `count_attachments()` uses `isinstance(body[0], list)` instead of `body.is_multipart` — this lets tests pass plain tuples without importing `BodyData`. Same detection logic IMAPClient uses internally.

**Multipart container disposition:** Multipart nodes have disposition at `[3]`, but in practice it is always `None`. The algorithm skips it and only counts leaf parts. If a multipart node somehow had `disposition: attachment`, it would be ignored — this is correct behavior (you can't "download" a multipart container).

**Short tuple fallback:** If server omits extension fields, `_get_disposition()` returns `None` (length checks: `> 9` for text/*, `> 8` for basic, `> 11` for message/rfc822) → not counted as attachment. This is a silent miss. Implementation should log a debug warning on first occurrence per session to aid troubleshooting, but not fail.

### Token and IMAP cost

- **Token cost:** ~5 tokens per message with attachments. Zero for messages without.
- **IMAP cost:** BODYSTRUCTURE is metadata-only — server doesn't fetch body content. Minimal overhead vs current ENVELOPE+FLAGS fetch.

### Cache impact

`session.py` caches list results in `MessageListCache` dataclass (line 103). Cache is **in-memory only** — not persisted across process restarts. Each cached message is a dict with fields: `id`, `subject`, `from`, `date`, `size`, `flags`. Adding BODYSTRUCTURE means adding `attachment_count` to this dict.

No version check needed — cache is cleared on every process restart. Runtime compatibility: formatter uses `msg.get("attachment_count", 0)` so missing field is handled gracefully.

## Architecture Context

Key files and exact change points:

### `session.py` — list FETCH + cache
- **Line 231:** `conn.fetch(selected_ids, ["ENVELOPE", "FLAGS", "RFC822.SIZE"])` → add `"BODYSTRUCTURE"`
- **Lines 254-262:** `messages.append({...})` → add `"attachment_count": count_attachments(msg_data[b"BODYSTRUCTURE"])` if key present, else `0`. Use `msg_data.get(b"BODYSTRUCTURE")` with None check.
- **Lines 103-110:** `MessageListCache` dataclass — no schema change needed, `attachment_count` goes into message dict
- **Line 215:** Cache hit returns `cached.messages[:limit]` — old cache entries without `attachment_count` need `.get("attachment_count", 0)` in formatter

### `imap_client.py` — search FETCH
- **Line 570:** `client.fetch(selected_ids, ["ENVELOPE", "FLAGS"])` → add `"BODYSTRUCTURE"`
- **Lines 578-586:** `results.append({...})` → add `"attachment_count": count_attachments(data[b"BODYSTRUCTURE"])` if key present, else `0`. Same `.get()` pattern.

### `imap_stream_mcp.py` — response formatting
- **Line 541 (list):** `lines.append(f"  From: {msg['from']} | {msg['date']} {flag_str}")` → append `[att:N]` if `msg.get("attachment_count", 0) > 0`
- **Line 635 (search):** identical change
- **Lines 221+ (HELP_TOPICS):** update help text

### New: `bodystructure.py` module
Location: `imap-stream-mcp/bodystructure.py` — shared module for BODYSTRUCTURE parsing. Contains `_is_attachment()`, `count_attachments()`, and later `find_text_part()` for snippet plan. Both `session.py` and `imap_client.py` import from here. No circular dependencies — `bodystructure.py` has no imports from the project.

### Tests
- `tests/imap-stream-mcp/test_imap_client.py` (90 tests) — CI testpath
- `tests/imap-stream-mcp/test_imap_stream_mcp.py` (48 tests) — CI testpath
- `imap-stream-mcp/tests/test_session.py` — session cache tests, **separate location**, not in CI testpath. New `count_attachments` unit tests go into `tests/imap-stream-mcp/` so CI runs them. If session cache integration tests are needed, add to `tests/imap-stream-mcp/test_imap_client.py`.

Related plans:
- `2026-02-23-ux-improvements.md` — separates inline images from real attachments in `read`. This plan uses same predicate as `read`: attachment OR inline+filename.
- `2026-02-24-list-search-snippet.md` — adds body preview snippet (Phase 2, builds on BODYSTRUCTURE from this plan). Snippet will reuse the BODYSTRUCTURE already fetched here.

**Help text:** Defined in `imap_stream_mcp.py` `HELP_TOPICS` dict (line 221+). Update:
- Overview help (line 222): add attachment indicator mention to list/search descriptions
- `help list` (line 246): document `[att:N]` indicator in output format
- `help search` (line 275): same as list

## Testing Strategy

**Mock data construction:** Plain tuples work because `count_attachments()` uses `isinstance(body[0], list)` instead of `.is_multipart`. No need to import `BodyData`:
```python
# Simple text message (no attachments)
SIMPLE_TEXT = (b"TEXT", b"PLAIN", (b"CHARSET", b"utf-8"), None, None, b"7BIT", 100, 5, None, None, None, None)

# Multipart with 1 attachment
# Note: TEXT/* parts have 12 elements (lines at [7]), APPLICATION/* has 11 (no lines)
MIXED_1ATT = (
    [
        (b"TEXT", b"PLAIN", (b"CHARSET", b"utf-8"), None, None, b"7BIT", 100, 5, None, None, None, None),
        (b"APPLICATION", b"PDF", (b"NAME", b"report.pdf"), None, None, b"BASE64", 5000, None, (b"attachment", (b"filename", b"report.pdf")), None, None),
    ],
    b"MIXED", (b"BOUNDARY", b"==abc=="), None, None, None,
)

# Inline image WITH filename (SHOULD count — matches read_message predicate)
# IMAGE/* = basic type: 11 elements, disposition at [8]
INLINE_IMG = (b"IMAGE", b"PNG", (b"NAME", b"logo.png"), None, None, b"BASE64", 2000, None, (b"inline", (b"filename", b"logo.png")), None, None)

# Inline without filename (should NOT count — CID-referenced inline)
INLINE_NO_NAME = (b"IMAGE", b"PNG", None, None, None, b"BASE64", 2000, None, (b"inline", None), None, None)

# Inline with Content-Type name= but NO disposition filename (SHOULD count — get_filename() fallback)
INLINE_CT_NAME = (b"IMAGE", b"PNG", (b"NAME", b"chart.png"), None, None, b"BASE64", 3000, None, (b"inline", None), None, None)

# Forwarded message/rfc822 attachment — disposition at index [11], not [9]
# Layout: maintype, subtype, params, id, desc, enc, octets, envelope, body, lines, MD5, disp, lang, loc
MESSAGE_RFC822_ATT = (
    b"MESSAGE", b"RFC822", None, None, None, b"7BIT", 1234,
    None,  # [7] envelope (simplified)
    (b"TEXT", b"PLAIN", (b"CHARSET", b"utf-8"), None, None, b"7BIT", 100, 5, None, None, None, None),  # [8] nested body
    42,    # [9] lines
    None,  # [10] MD5
    (b"attachment", (b"filename", b"forwarded.eml")),  # [11] DISPOSITION
    None,  # [12] language
    None,  # [13] location
)
```

**`tests/imap-stream-mcp/test_bodystructure.py` (unit tests for `count_attachments`):**
- `SIMPLE_TEXT` → 0
- `MIXED_1ATT` → 1
- Multipart with 3 attachments → 3
- `INLINE_IMG` (inline with disposition filename) → 1 (consistent with read_message)
- `INLINE_NO_NAME` (inline without filename) → 0
- Inline with Content-Type `name=` but no disposition filename → 1 (get_filename() fallback)
- Nested multipart/mixed inside multipart/mixed → correct recursive count
- `MESSAGE_RFC822_ATT` → 1 (disposition at index [11], not [9])
- `message/rfc822` without disposition extensions (short tuple, len < 12) → 0
- Short tuple (no extension fields, len < 10) → 0 with debug warning

**`test_imap_client.py` (integration):**
- list_messages returns `attachment_count` field per message
- search_messages returns `attachment_count` field per message

**`test_imap_stream_mcp.py`:**
- list action: messages with attachments show `[att:N]`
- list action: messages without attachments show no indicator
- search action: same formatting as list

**Manual tests:**
- Gmail messages with various MIME structures
- Outlook messages with inline signature images (should not inflate attachment count)

## Implementation Progress

- [x] Add tests and fixtures for BODYSTRUCTURE parsing, list/search `attachment_count`, and `[att:N]` formatting
- [x] Implement `bodystructure.py` parser/counting helpers
- [x] Integrate BODYSTRUCTURE fetch and `attachment_count` in `session.py` and `imap_client.py`
- [x] Integrate `[att:N]` rendering and help text updates in `imap_stream_mcp.py`
- [>] Run manual validation against Gmail/Outlook mailboxes (deferred: no live mailbox credentials in this environment)
- [x] Run automated feature test suite (`test_bodystructure.py`, `test_imap_client.py`, `test_imap_stream_mcp.py`)

## Implementation Notes

- Decision: short BODYSTRUCTURE tuple diagnostics use module-level `logging.debug` with single-emission guard, because session-scoped logging context is not available in current architecture.
- Decision: list/search paths use `.get(b"BODYSTRUCTURE")` and default `attachment_count=0` to preserve compatibility with older cache entries and mocks.
- Surprise: `uv sync` in `/youtube-to-markdown` fails due existing hatch packaging metadata issue (`Unable to determine which files to ship`); unrelated to this feature and left unchanged.

## Acceptance Criteria

- [x] BODYSTRUCTURE fetched in list and search IMAP calls
- [x] Attachment count extracted from BODYSTRUCTURE matching `read_message()` predicate: `attachment` OR `inline` with filename (checks both disposition `filename` and Content-Type `name` params)
- [x] `[att:N]` shown in list/search response for messages with N>0 attachments
- [x] No indicator for messages without attachments
- [x] Inline images without filename excluded from count
- [x] Missing BODYSTRUCTURE handled gracefully (`.get()` → count 0, no crash)
- [x] `bodystructure.py` module created with `count_attachments()`, `_get_disposition()`, `_is_attachment()`, `_has_filename()`
- [x] `message/rfc822` parts handled correctly (disposition at index [11], not [9])
- [x] Help text updated for list and search
- [x] All existing tests pass (90 in test_imap_client.py, 48 in test_imap_stream_mcp.py + conftest fixtures updated with BODYSTRUCTURE mock data)
- [x] New unit tests in `tests/imap-stream-mcp/test_bodystructure.py` using plain tuples
- [x] New formatting tests for `[att:N]` in list and search responses
- [>] Manual validation: attachment count matches between `list`/`search` indicator and `read` attachment list for same messages (deferred: requires live IMAP accounts)

## Reflection

**What went well:**
- Plan was thorough enough that Codex implemented it correctly on the first pass — TDD approach, test data, exact change points all held up
- Disposition index table (text/*/basic/message/rfc822) was the critical insight from planning — would have caused bugs if discovered during implementation
- `_iter_params()` abstraction was correctly identified and removed in review — KISS over premature abstraction
- Two review iterations caught 7 issues total, all minor — no architectural rework needed

**What changed from plan:**
- `_iter_params()` helper added by Codex then removed in review — plan didn't specify it, was Codex's own abstraction
- Test sys.path hack added by Codex then removed in review — conftest.py already handled imports
- Plan line numbers drifted slightly from main (86→90 tests, 43→48) due to parallel work merged to main

**Lessons learned:**
- Delegating to Codex with `--dangerously-bypass-approvals-and-sandbox` works but requires thorough review — Codex adds its own abstractions that may not match project conventions
- Self-contained plan with verified test data is the difference between one-pass and multi-pass implementation
- Review iterations converge fast when the core logic is correct — round 1 was code quality, round 2 was documentation consistency
