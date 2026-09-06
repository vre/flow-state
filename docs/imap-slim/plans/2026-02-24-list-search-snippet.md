# Body Preview Snippet in List/Search Results

## Problem

LLM must call `read` to see any body content. Each `read` costs ~2000+ tokens. When browsing messages to find specific content, LLM reads many messages unnecessarily. A ~100 char preview would let LLM decide which messages to read fully.

**Origin:** Competitive analysis (`docs/imap-stream-mcp/research/2026-02-24-email-mcp-servers-survey.md`). baryhuang/mcp-headless-gmail provides 1,000-char body preview. marlinjai/email-mcp has compact search with `returnBody=false` default.

**Dependency:** Attachment-indicator plan (`2026-02-24-attachment-indicator.md`) — **implemented in v0.6.0**. BODYSTRUCTURE is already in FETCH calls.

## Current State (post v0.6.0)

List/search return envelope data + `attachment_count`. No body content. Current output:
```
**[123]** Re: Conference booking
  From: hotel@example.com | 2026-02-24 14:30 [seen] [att:1]

**[124]** Weekly report
  From: team@company.com | 2026-02-23 09:15
```

Key files (verified line numbers):
- `session.py:232` — FETCH includes `BODYSTRUCTURE`, result stored in `MessageListCache`
- `session.py:264` — `attachment_count` stored in message dict (int only, no raw BODYSTRUCTURE)
- `imap_client.py:571` — search FETCH includes `BODYSTRUCTURE`
- `imap_client.py:586` — `attachment_count` in search results
- `imap_stream_mcp.py:540-548` — list formatting (subject + From: line + empty line)
- `imap_stream_mcp.py:638-646` — search formatting (identical pattern)
- `bodystructure.py` — `count_attachments()`, `_get_disposition()`, `_is_attachment()`, `_has_filename()`
- `tests/` — 10 bodystructure + imap_client + imap_stream_mcp + markdown tests

## Proposed Change

Add first ~100 characters of plain text body as a third line in list/search output.

**Target format:**
```
**[123]** Re: Conference booking
  From: hotel@example.com | 2026-02-24 14:30 [seen] [att:1]
  > Thank you for your reservation. Your booking reference is HK-2026-...

**[124]** Weekly report
  From: team@company.com | 2026-02-23 09:15
  > Here are the highlights from this week: 1) Project Alpha shipped...
```

## Implementation

### Approach: BODYSTRUCTURE + selective BODY.PEEK (two-step fetch)

1. Parse BODYSTRUCTURE (already in first FETCH) to find text/plain part
2. Derive IMAP part number from BODYSTRUCTURE tree position
3. Fetch `BODY.PEEK[{part_number}]<0.600>` — 600 bytes, no mark-as-read
4. Decode transfer encoding → charset → truncate at ~100 chars on word boundary → "..."
5. If no text/plain: `find_html_part()` → strip tags via `html.parser` MLStripper → truncate
6. If neither: empty snippet

### IMAP part numbering (RFC 3501)

```
multipart/mixed                    (root — no number)
├── multipart/alternative          (part 1 — container, not fetchable)
│   ├── text/html                  (part 1.1)
│   └── text/plain                 (part 1.2)
└── application/pdf [attachment]   (part 2)
```

- Simple (non-multipart): `BODY.PEEK[1]<0.600>`
- Multipart: children numbered 1, 2, 3... Nested: dot notation 1.1, 1.2
- Example above text/plain: `BODY.PEEK[1.2]<0.600>`

### New functions in `bodystructure.py`

**`find_text_part()`** — find first text/plain body part (not attachment):

```python
def find_text_part(body: tuple | None, prefix: str = "") -> tuple[str, bytes, bytes] | None:
    """Find first text/plain body part (not attachment).

    Args:
        body: BODYSTRUCTURE tuple (or None).
        prefix: Part number prefix for recursion.

    Returns:
        (part_number, charset, transfer_encoding) or None.
    """
    if not isinstance(body, tuple) or not body:
        return None
    if isinstance(body[0], list):  # multipart
        for i, part in enumerate(body[0], 1):
            part_num = f"{prefix}{i}" if not prefix else f"{prefix}.{i}"
            result = find_text_part(part, part_num)
            if result:
                return result
        return None
    if not isinstance(body[0], bytes) or not isinstance(body[1], bytes):
        return None
    if body[0].lower() == b"text" and body[1].lower() == b"plain":
        disp = _get_disposition(body)
        if _is_attachment(body, disp):
            return None  # skip attached .txt files
        charset = _extract_charset(body)
        encoding = body[5] if len(body) > 5 else b"7BIT"
        return (prefix or "1", charset, encoding)
    return None
```

**`find_html_part()`** — identical structure, matches `text/html` instead of `text/plain`. Same `body: tuple | None` type hint, same None guard, same attachment skip logic.

**`_extract_charset(body)`** — shared helper (DRY):
```python
def _extract_charset(body: tuple) -> bytes:
    """Extract charset from BODYSTRUCTURE params, default utf-8."""
    params = body[2] if len(body) > 2 else None
    if isinstance(params, tuple):
        for j in range(0, len(params), 2):
            if isinstance(params[j], bytes) and params[j].lower() == b"charset" and j + 1 < len(params):
                return params[j + 1]
    return b"utf-8"
```

**`extract_snippet()`** — decode + truncate:
```python
def extract_snippet(
    raw_bytes: bytes, charset: bytes, encoding: bytes, is_html: bool = False, max_chars: int = 100
) -> str:
    """Decode raw IMAP body bytes and return truncated snippet.

    Args:
        raw_bytes: Raw bytes from BODY.PEEK partial fetch.
        charset: Character set from BODYSTRUCTURE (e.g. b"utf-8").
        encoding: Transfer encoding (e.g. b"BASE64", b"QUOTED-PRINTABLE", b"7BIT").
        is_html: If True, strip HTML tags before truncation.
        max_chars: Truncation length.

    Returns:
        Decoded, truncated text. Empty string on any decode failure.
    """
```

Decoding pipeline (order matters):
1. Transfer encoding decode: `7BIT`/`8BIT`/`BINARY` → as-is; `BASE64` → strip `\r\n`, round **down** to nearest 4-byte boundary (discard trailing 1-3 bytes), `base64.b64decode()`; `QUOTED-PRINTABLE` → `quopri.decodestring()`
2. Charset decode: `decoded_bytes.decode(charset_str, errors="ignore")` — `errors="ignore"` drops partial UTF-8 from byte truncation (safer than `replace` which inserts replacement chars)
3. If `is_html`: strip tags via stdlib `html.parser` MLStripper (~10 lines, no deps, fast for 600 bytes)
4. Collapse whitespace: `" ".join(text.split())` — normalizes `\r\n`, tabs, multiple spaces
5. Truncate at `max_chars` on word boundary, append "..."
6. Any exception → return `""`

**MLStripper vs html2text decision:** `html2text` is a dependency but does full Markdown conversion — overkill for 100 chars from 600 bytes. Snippet uses stdlib approach: `re.sub` to remove `<style>...</style>` and `<script>...</script>` blocks (content included), then `html.parser` MLStripper to strip remaining tags, then `html.unescape()` for entities. ~15 lines, zero overhead. `html2text` reserved for `read` action's full body.

### Two-step fetch flow

**Why not single FETCH:** Cannot include `BODY.PEEK[1]<0.600>` in the first FETCH because part 1 is not text/plain in most multipart messages. Must parse BODYSTRUCTURE first to determine the correct part number.

**Flow:**
1. First FETCH (existing): `ENVELOPE`, `FLAGS`, `RFC822.SIZE`, `BODYSTRUCTURE` → `data` dict
2. Pre-process: for each message in `data`, determine snippet source:
   ```python
   snippet_info = {}  # msg_id → (section, charset, encoding, is_html)
   for msg_id in selected_ids:
       bs = data[msg_id].get(b"BODYSTRUCTURE")
       result = find_text_part(bs)
       is_html = False
       if result is None:
           result = find_html_part(bs)
           is_html = True
       if result:
           section, charset, encoding = result
           snippet_info[msg_id] = (section, charset, encoding, is_html)
   ```
3. Group `snippet_info` by section number (most folders: 1-2 groups for 20 messages)
4. Per group: `conn.fetch(group_ids, [f"BODY.PEEK[{section}]<0.600>"])` → merge into `snippet_raw` dict
5. Build `snippets: dict[int, str]` mapping `msg_id → snippet_text`:
   ```python
   snippets: dict[int, str] = {}
   for msg_id, (section, charset, encoding, is_html) in snippet_info.items():
       raw = _get_body_peek(snippet_raw.get(msg_id, {}), section)  # key lookup with fallback
       snippets[msg_id] = extract_snippet(raw, charset, encoding, is_html) if raw else ""
   ```
6. Build message dicts (existing loop): `"snippet": snippets.get(msg_id, "")`

**IMAP FETCH constraint:** All messages in a single FETCH get the same data items. Cannot mix `BODY.PEEK[1]` and `BODY.PEEK[1.2]` in one call.

**Response key format (verified via IMAPClient parser):** IMAPClient preserves the key as the server sends it. Observed variants for `BODY.PEEK[1.2]<0.600>`:
- `b'BODY[1.2]<0.600>'` — server echoes full range
- `b'BODY[1.2]<0>'` — server strips length from range
- `b'BODY[1.2]'` — server strips range entirely

**`_get_body_peek(msg_data, section)` lookup strategy:** iterate `msg_data` keys matching `b'BODY[{section}]'` prefix (covers all three variants). Do NOT use exact key lookup — server behavior varies. This is the only reliable approach.

**Fetch size: 600 bytes.** Raw encoded content. For base64: 600 raw bytes ≈ 450 decoded. Generous margin for 100-char truncation.

**Latency:** 2-3 IMAP roundtrips (1 metadata + 1-2 snippet groups). Acceptable.

### Error handling

- BODYSTRUCTURE missing or unparseable → empty snippet, not crash
- `find_text_part()` returns None AND `find_html_part()` returns None → empty snippet
- BODY.PEEK fetch fails for a group → those messages get empty snippet, other groups unaffected
- `extract_snippet()` catches all exceptions internally → returns `""`
- Partial success is fine: some messages with snippets, some without
- **Snippet FETCH must not break message listing.** The entire snippet pre-processing + batch FETCH block (steps 2-5 in flow above) is wrapped in `try/except Exception` → on failure, `snippets` defaults to empty dict and all messages get empty snippet. This is critical because `session.py:get_messages()` does not use `connection_ctx()` and has no connection error recovery of its own.
- **Sticky empty snippets in cache:** If snippet FETCH fails transiently, messages get cached with empty snippets that persist until mailbox metadata changes (uidnext/uidvalidity/exists). Acceptable trade-off: cache is in-memory only (dies on process restart), and typical mailbox activity (new message arrival) changes uidnext within minutes. Alternative (skip caching on snippet failure) adds complexity for marginal benefit.

### Known limitations

- **`message/rfc822` parts:** `find_text_part()`/`find_html_part()` do not recurse into embedded `message/rfc822` parts. A forwarded `.eml` without its own text body yields no snippet. Acceptable — these are rare in inbox listings.
- **Truncated `<style>` tags:** 600-byte partial fetch may cut mid-`<style>` block. MLStripper removes the tag but CSS content leaks into snippet text. Cosmetic only — `" ".join(text.split())` collapses it, and 100-char truncation limits exposure.

### Changes by file

#### `bodystructure.py` — new functions
- `find_text_part(body: tuple | None, prefix) -> tuple[str, bytes, bytes] | None`
- `find_html_part(body: tuple | None, prefix) -> tuple[str, bytes, bytes] | None`
- `_extract_charset(body) -> bytes`
- `extract_snippet(raw_bytes, charset, encoding, is_html, max_chars) -> str`
- `_strip_html_tags(text) -> str` — remove `<style>`/`<script>` blocks, strip tags, unescape entities

No project imports (consistent with existing module convention). Only stdlib: `base64`, `quopri`, `html.parser`.

#### `session.py` — `get_messages()` (line 232+)

Code flow (numbers reference existing lines):
1. **Line 232:** First FETCH → `data` dict (existing, unchanged)
2. **NEW (insert after 232):** Pre-process + snippet fetch (see two-step flow steps 2-5) → `snippets: dict[int, str]`
3. **Lines 235-266 (existing loop, modified):** Build message dict, add `"snippet": snippets.get(msg_id, "")` alongside `attachment_count` (line 264)
4. **Line 269:** Cache includes snippet in `MessageListCache` → served from cache on hit

Entire step 2 wrapped in `try/except Exception` → on failure, `snippets = {}`.

Key: snippet fetch happens between the existing first FETCH and the message dict loop. The `conn` object from line 198 (`conn = self.get_connection()`) is reused for snippet FETCH calls — folder is already selected (line 202).

- **Import:** add `find_text_part, find_html_part, extract_snippet` to existing `from bodystructure import` (line 11)

#### `imap_client.py` — `search_messages()` (line 571+)

Same two-step pattern, but different code structure:
1. **Line 571:** `messages = client.fetch(selected_ids, [..., "BODYSTRUCTURE"])` (note: variable is `client` not `conn`, from `session.connection_ctx()` at line 535)
2. **NEW (after 571):** Pre-process + snippet fetch using same `client` object within same `connection_ctx()` block → `snippets: dict[int, str]`. Wrapped in `try/except Exception` → on failure, `snippets = {}`.
3. **Line 574 loop:** `for msg_id, data in messages.items()` — add `"snippet": snippets.get(msg_id, "")` to results dict (line ~586)

No caching — snippet computed fresh each search.
- **Import:** add `find_text_part, find_html_part, extract_snippet` to existing `from bodystructure import` (line ~30)

#### `imap_stream_mcp.py` — formatting (lines 540-548, 638-646)
- After `From:` line (line 547 for list, line 645 for search):
  ```python
  snippet = msg.get("snippet", "")
  if snippet:
      if _contains_injection_patterns(snippet):
          snippet = "[content hidden]"
      lines.append(f"  > {snippet}")
  ```
- Uses `.get("snippet", "")` for cache backward compatibility
- Injection check via existing `_contains_injection_patterns()` — no code duplication
- Help text updates: `HELP_TOPICS` dict (lines 222+): overview (228, 230), list (249), search (279)

### Snippet activation: mandatory `preview` parameter [+] amended during review

~~Always-on (Option B)~~ → Changed to mandatory `preview: bool` on `MailAction` for list/search.

LLM must explicitly choose `preview: true` or `preview: false` per call. Validation error if omitted.

**Rationale (amended):**
- Context is LLM's scarcest resource — 20 snippets = ~1000 tokens unconditionally is wasteful
- LLM should decide per-call: "do I need to skim content?" vs "just show headers"
- Mandatory choice forces intentional resource allocation, no hidden cost
- `preview: false` skips BODY.PEEK fetch entirely (0 extra roundtrips)

**Implementation:**
- `MailAction.preview: bool | None = None` with `model_validator` → error if None for list/search
- `list_messages(preview=)` / `search_messages(preview=)` / `get_messages(preview=)` gate snippet fetch
- Help text and docstring updated with both `preview: true` and `preview: false` examples

### Security: prompt injection

- Snippet uses blockquote prefix (`  > ...`) — visually distinct as untrusted content
- `_contains_injection_patterns()` check before rendering — if detected, replace with `[content hidden]`
- Same function used by `_wrap_email()` for `read` action — no pattern duplication
- 100 chars is minimal surface, but sufficient for injection attempts, so check is warranted

### Token cost

~25-50 tokens per message (100 chars + formatting). For 20 messages: ~500-1000 extra tokens. Saves one `read` call (~2000 tokens) per message LLM would have read unnecessarily.

## Implementation Tasks

### Task 1: `bodystructure.py` — new functions
- [x] `_extract_charset()` helper
- [x] `_strip_html_tags()` MLStripper
- [x] `find_text_part()` with attachment skip
- [x] `find_html_part()` with attachment skip
- [x] `extract_snippet()` with full decoding pipeline

### Task 2: `test_bodystructure.py` — unit tests
- [x] `find_text_part(None)` → `None` (None guard, matches `count_attachments` convention)
- [x] `find_html_part(None)` → `None`
- [x] `find_text_part` on `SIMPLE_TEXT` → `("1", b"utf-8", b"7BIT")`
- [x] `find_text_part` on `NESTED_MULTIPART` → `("1.2", b"utf-8", b"7BIT")` (text/plain is at 1.2 in that fixture)
- [x] `find_text_part` on text/plain with `disposition=attachment` → `None`
- [x] `find_text_part` on HTML-only → `None` (needs new `HTML_ONLY` fixture: `(b"TEXT", b"HTML", ...)`)
- [x] `find_html_part` on HTML-only → `("1", charset, encoding)` (same fixture)
- [x] `find_html_part` on `NESTED_MULTIPART` → `("1.1", b"utf-8", b"7BIT")` (text/html is at 1.1)
- [x] `_extract_charset` with params, without params, with non-tuple params, with odd-length params tuple
- [x] `extract_snippet` with invalid charset (e.g. `b"INVALID-XYZ"`) → falls back gracefully (empty or partial)
- [x] `extract_snippet` 7BIT UTF-8 → first ~100 chars with "..."
- [x] `extract_snippet` BASE64 → decoded, truncated
- [x] `extract_snippet` QUOTED-PRINTABLE → decoded, truncated
- [x] `extract_snippet` `is_html=True` → tags stripped, truncated
- [x] `extract_snippet` truncated UTF-8 at byte boundary → no crash
- [x] `extract_snippet` unknown encoding → `""`
- [x] `extract_snippet` empty bytes → `""`
- [x] `_strip_html_tags` with `<style>`, `<script>` → content removed

### Task 3: `session.py` — snippet fetch in `get_messages()`
- [x] After first FETCH: parse BODYSTRUCTURE for each message
- [x] Group by section number, batch FETCH `BODY.PEEK[{section}]<0.600>`
- [x] `_get_body_peek()`: iterate keys matching `b'BODY[{section}]'` prefix (covers `<0>`, `<0.600>`, bare variants)
- [x] Add `"snippet"` to message dict
- [x] Handle: no text part → empty snippet, FETCH error → empty snippet
- [x] Entire snippet block in `try/except Exception` → `snippets = {}`

### Task 4: `imap_client.py` — snippet fetch in `search_messages()`
- [x] Same pattern as session.py
- [x] No caching — computed fresh each search

### Task 5: `imap_stream_mcp.py` — formatting + help
- [x] List formatting: add snippet line after From: line (line 547)
- [x] Search formatting: same (line 645)
- [x] Injection check on snippet before rendering
- [x] Help text updates: overview, list, search

### Task 6: Integration tests
- [x] **MockIMAPClient.fetch() enhancement:** Current mock ignores selectors (returns same pre-stored blob for any `data` param). Must be extended to: (a) store snippet body bytes per message via new `add_message()` param (e.g. `snippet_body`), (b) return `b'BODY[{section}]<0>'` key when `BODY.PEEK` is in the requested selectors. Without this, integration tests cannot verify the two-step FETCH path.
- [x] `test_imap_client.py`: list_messages returns snippet, search_messages returns snippet
- [x] `test_imap_stream_mcp.py`: list/search output includes blockquote snippet line
- [x] Cache hit serves snippet
- [x] Empty body → empty snippet
- [x] Injection pattern in snippet → `[content hidden]`
- [x] `_get_body_peek()` response key variants: `<0>`, `<0.600>`, bare key

### Review findings [+] discovered and fixed
- [x] `_get_body_peek()` duplicated in session.py and imap_client.py → consolidated to `get_body_peek()` in bodystructure.py
- [x] Missing search injection snippet test → added `test_search_hides_injection_like_snippet`
- [x] Word-boundary truncation not explicitly tested → added `test_extract_snippet_truncates_on_word_boundary`
- [x] `find_html_part` attachment-skip not tested → added `test_find_html_part_skips_html_attachment` + `HTML_ATTACHMENT` fixture
- [+] Mandatory `preview` parameter → added `MailAction.preview`, gated snippet fetch, validation tests

### Task 7: Manual testing
- [x] Gmail/live server: multipart messages, text/plain snippets decoded correctly
- [>] Outlook: not available for testing — deferred, covered by unit tests for key variants
- [x] Response key validation: server returns `b'BODY[1]<0>'` (range stripped), prefix match works ✓
- [x] preview=False: empty snippets, no BODY.PEEK fetch
- [x] preview=True: snippets present, search works, UTF-8 decoded
- [x] No \\Seen flag added after snippet fetch (BODY.PEEK confirmed)
- [>] S/MIME: not available for testing — deferred

## Testing Strategy

**Unit tests (`test_bodystructure.py`):** Task 2 above. Pure functions, no mocks needed for bodystructure functions. Test fixtures reuse existing `SIMPLE_TEXT`, `NESTED_MULTIPART`, etc.

**Integration tests (`test_imap_client.py`, `test_imap_stream_mcp.py`):** Task 6 above. Requires MockIMAPClient enhancement: current mock ignores FETCH selectors and returns same pre-stored data for any request. Must be extended to return `BODY[{section}]` keys when BODY.PEEK is requested. Alternative for `test_imap_stream_mcp.py`: mock at `list_messages`/`search_messages` level (already done for attachment indicator tests, line 79+) — add `"snippet"` to mock return dicts.

**Manual tests:** Task 7. Validate response key format, real-world MIME structures.

## Acceptance Criteria

- [x] Snippet field in list and search message dicts (cache miss: BODY.PEEK, cache hit: from cache)
- [x] Decoded (transfer encoding + charset) and truncated at max 100 chars on word boundary; "..." appended only when truncated (not on short messages)
- [x] Shown as blockquote line (`  > ...`) after From: line in list/search
- [x] `find_text_part()` and `find_html_part()` skip parts with `disposition=attachment`
- [x] HTML-only: `find_html_part()` fallback with MLStripper tag stripping
- [x] No message marked as read: all snippet fetches use `BODY.PEEK` (not `BODY`). Verified by: code review ✓ + manual test ✓ (flags unchanged after list with preview)
- [x] UTF-8 safe: `errors="ignore"` drops partial multi-byte chars
- [-] ~~Always-on: no opt-in needed~~ — replaced by mandatory `preview` parameter
- [+] Mandatory `preview: bool` parameter for list/search — validation error if omitted
- [+] `preview: false` skips snippet fetch entirely (0 extra IMAP roundtrips)
- [x] Injection mitigation: `_contains_injection_patterns()` check, `[content hidden]` on match
- [x] Response key: `get_body_peek()` uses prefix match on `b'BODY[{section}]'` (covers `<0>`, `<0.600>`, bare). Unit tested for all 3 variants ✓ + validated against live server: `b'BODY[1]<0>'` ✓
- [x] Help text updated (overview, list, search)
- [x] All existing tests pass (257 total)
- [x] New unit tests for `find_text_part`, `find_html_part`, `_extract_charset`, `extract_snippet`, `_strip_html_tags`
- [x] New integration tests: snippet in list/search output, cache serves snippet

**Out of scope:**
- Flag formatting differences between list/search (pre-existing)
- Search result ordering (IMAP SEARCH does not guarantee order)

## Reflection
### What Went Well
- The two-step FETCH approach worked as designed: BODYSTRUCTURE parsing identified snippet parts correctly, and grouping by section minimized IMAP roundtrips.
- MLStripper was the right HTML strategy over html2text for snippet extraction: lightweight and fast for 600-byte partial fetches.
- Live server testing surfaced IMAPClient internal `SEQ` key behavior; prefix-based BODY key matching remained correct and robust.

### What Changed From Plan
- Biggest change: the original always-on snippet design was challenged in review. HC flagged LLM context as the scarcest resource, so the design shifted to a mandatory `preview` parameter.
- Self-review found a DRY violation: `_get_body_peek` logic was duplicated in `session.py` and `imap_client.py`, then consolidated into `bodystructure.py`.
- MockIMAPClient enhancement (selector-aware fetch behavior) took more effort than planned, but was required for meaningful integration coverage.

### Lessons Learned
- For LLM-facing tools, context/token budget is a first-order product constraint and must shape defaults early.
- IMAP integration quality depends on realistic mocks: selector handling and response-key variants are not optional details.
- Protocol-edge validation on live servers still matters even with strong automated tests.
- Final state: 257 tests passing.
