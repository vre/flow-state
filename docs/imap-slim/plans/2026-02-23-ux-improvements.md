# IMAP MCP UX Improvements

## Problem

Session 8acd19bf (~4.5h, 967 JSONL lines) exposed three systemic problems:

1. **Inline image noise in read**: Outlook-style emails include 20-30 signature images as `Content-Disposition: inline` parts. Read action lists all of them alongside real attachments, adding useless metadata to context. Session: 25 "attachments" of which 24 were signature pixels, one real PDF.

2. **No incremental draft editing**: Every draft modification requires LLM to generate the full body text (~500-2000 tokens output) even for single-word changes. Session data: 22 draft calls, median 65s, worst 177s. The `modify_draft` action rebuilds the entire IMAP message. LLM has no way to make surgical edits — must always send complete body.

3. **Format validation missing**: `convert_body(body, format_type)` silently accepts any string as `format_type`. Unknown values (including `"html"`) fall through to plain text without warning. Session: LLM used `format: "html"` with raw markdown body, producing unformatted plain text email.

## Goal

Three targeted fixes to reduce token waste, speed up draft iteration, and prevent format misuse.

## Situational Context

- IMAP MCP follows Jesse Vincent single-tool pattern: one `use_mail` tool, actions via `action` parameter
- Draft modify is append-before-delete (IMAP has no in-place edit)
- Current actions: `list|read|search|draft|flag|attachment|cleanup|folders|accounts|help`
- LLM knows Claude's Edit tool semantics (`old_string`/`new_string` exact replacement)
- Tests in `tests/imap-stream-mcp/test_imap_client.py` (72 tests) and `test_imap_stream_mcp.py` (30 tests)

## Changes

### 1. Read: separate inline images from real attachments

**`imap_client.py` `read_message()` (line 370-415):**

Current: single `attachments` list with both `Content-Disposition: attachment` and `inline`+filename parts.

Change: return two lists in the result dict:
- `attachments`: only `Content-Disposition: attachment` parts (real attachments)
- `inline_images`: only `Content-Disposition: inline` with filename (signature images, embedded graphics)

Both lists keep same structure: `{filename, content_type, size, index}` where `index` is the walk-order position (0-based) matching `download_attachment()`'s enumeration. Both categories are downloadable via `attachment` action using this index.

**`imap_stream_mcp.py` read formatting (line 568-577):**

Current:
```
**Attachments:** (25)
  - image001.png (image/png, 1.2 KB)
  - ... (24 more)
  - list.pdf (application/pdf, 245.0 KB)
```

New:
```
**Attachments:** (1)
  - list.pdf (application/pdf, 245.0 KB)

**Inline images:** (24) image001.png, image002.png, image003.png, ... +21 more
```

Rules:
- Real attachments: one per line with full detail (current format), include download index
- Inline images: all listed with index, compact comma-separated format on one line. Every image addressable by index for `attachment` action download
- If only one category has items, omit the other heading
- **Index preservation**: `download_attachment()` (line 451-454) uses same walk filter as `read_message` (line 381). Both enumerate `attachment` + `inline`+filename parts in walk order. The display index shown in read output must match the download index. Implementation: `read_message` returns items with their walk-order index, display groups them by category.

Example output:
```
**Attachments:** (1)
  [24] list.pdf (application/pdf, 245.0 KB)

**Inline images:** (24) [0] image001.png, [1] image002.png, [2] image003.png, [3] image004.png, ... [23] image024.png
```

### 2. New `edit` action for surgical draft modifications

**`imap_client.py` — new function `edit_draft()`:**

```python
def edit_draft(
    folder: str,
    message_id: int,
    replacements: list[dict],  # [{"old": str, "new": str}, ...]
    account: str = None,
) -> dict:
```

Implementation:
1. Fetch draft (same as `modify_draft` start: fetch RFC822 + ENVELOPE)
2. Extract plain text body and HTML body from message parts
3. For each replacement in order:
   - Verify `old` appears exactly once in plain text body. If not found → error with suggestion. If multiple matches → error asking for more context.
   - `plain_body = plain_body.replace(old, new, 1)`
   - If HTML body exists: always regenerate HTML from edited plain text via `convert_body(plain_body, "markdown")`. Do not attempt surgical HTML text-node editing — too fragile with entities/tags. Same approach as `modify_draft` which always rebuilds from body parameter.
4. Rebuild message: same logic as `modify_draft` — preserve headers, threading, existing attachments, append-before-delete
5. Return: `{status, folder, to, subject, message_id, changes: [{old, new}], preserved_reply_to}`

HTML handling: always regenerate HTML from edited plain text via `convert_body()`. No attempt at surgical HTML editing. If original draft has no HTML part (plain-only draft), do not generate HTML — keep it plain-only after edit.

**Optional refactoring** (deferred, do after edit_draft works and tests pass): `edit_draft` and `modify_draft` share ~60 lines of identical logic (fetch draft, extract headers/threading, preserve attachments, rebuild message, append-before-delete). Extract shared `_rebuild_draft()` helper. This is a cleanup step, not a prerequisite — implement `edit_draft` first with copied logic, extract helper only when both functions are stable and tested.

**`imap_stream_mcp.py` — new action routing:**

- Add `"edit"` to `valid` actions set (line 213)
- Add action routing block:

```python
if action == "edit":
    if not folder:
        return "Error: folder required (e.g., 'Drafts')"
    if not params.payload:
        return "Error: payload required. Use 'help edit' for details."

    edit_data = json.loads(params.payload)
    # Validate payload structure
    if "id" not in edit_data:
        return "Error: 'id' required (draft message ID). Use 'help edit' for details."
    try:
        draft_id = int(edit_data["id"])
    except (ValueError, TypeError):
        return f"Error: 'id' must be a numeric message ID, got '{edit_data['id']}'"
    if draft_id <= 0:
        return f"Error: 'id' must be a positive integer, got {draft_id}"
    if "replacements" not in edit_data:
        return "Error: 'replacements' required. Use 'help edit' for details."
    replacements = edit_data["replacements"]
    if not isinstance(replacements, list) or len(replacements) == 0:
        return "Error: 'replacements' must be a non-empty list of {old, new} pairs"
    for i, r in enumerate(replacements):
        if not isinstance(r, dict) or "old" not in r or "new" not in r:
            return f"Error: replacement [{i}] must have 'old' and 'new' string fields"
        if not isinstance(r["old"], str) or not r["old"]:
            return f"Error: replacement [{i}] 'old' must be a non-empty string"
        if not isinstance(r["new"], str):
            return f"Error: replacement [{i}] 'new' must be a string"

    result = edit_draft(
        folder=folder,
        message_id=int(edit_data["id"]),
        replacements=edit_data["replacements"],
    )

    # Format response showing changes
```

Response format:
```
# Draft Edited

**Changes:** 2 replacements applied
  1. "11 ducks" → "12 ducks"
  2. "480 kg" → "450 kg"

**Draft:** Re: Foo Bar (Drafts)
```

No full body in response — LLM already knows what changed. If LLM needs to see the result, it uses `read`.

**Help text addition:**
```
"edit": """
# edit - Edit Draft (surgical replacement)

Edit specific text in an existing draft without rewriting the entire body.

## Parameters
- folder: Folder containing draft (e.g., 'Drafts')
- payload: JSON with id and replacements

## Payload
- id: Draft message ID (from list/read results)
- replacements: list of {old, new} pairs

## Example
{action: "edit", folder: "Drafts", payload: '{"id": 1444, "replacements": [{"old": "11 ducks", "new": "12 ducks"}]}'}

## Notes
- Each 'old' string must match exactly once in the draft body
- Multiple replacements applied in order
- Threading headers and attachments are preserved
- Use 'read' first to see current draft content
- For full rewrites, use 'draft' with id instead
"""
```

**Docstring update** (`MailAction.action` line 202):
```
"Action: list|read|search|draft|edit|flag|attachment|cleanup|folders|accounts|help"
```

**Overview help** (`HELP_TOPICS["overview"]` line 222-244):
- Add: `- **edit** - Edit specific text in a draft (old→new replacement)`

**`use_mail` tool docstring** (`imap_stream_mcp.py` line 433-445):
- Update action list in docstring to include `edit`
- Update examples to show edit usage

### 3. Format validation in `convert_body()`

**`markdown_utils.py` `convert_body()` (line 137-159):**

Current:
```python
if format_type == "markdown":
    ...
else:
    return None, body  # silently treats everything as plain
```

New:
```python
VALID_FORMATS = {"markdown", "plain"}

def convert_body(body: str, format_type: str = "markdown") -> tuple[str | None, str]:
    if format_type not in VALID_FORMATS:
        raise ValueError(
            f"Unknown format '{format_type}'. Use 'markdown' (default, converts to HTML) or 'plain' (text only). "
            f"Write your email in markdown — we handle the HTML conversion."
        )
    if format_type == "markdown":
        ...
    else:
        return None, body
```

**`imap_stream_mcp.py`** — add explicit `ValueError` catch before the existing `except Exception` (line 788) in `use_mail()`. This gives a clean error message without the `ValueError:` type prefix:

```python
except ValueError as e:
    return f"Error: {e}"
except IMAPError as e:
    ...
except Exception as e:
    return f"Error: {type(e).__name__}: {e}"
```

## Testing Strategy

Extend existing test files.

**`test_imap_client.py`:**
- `read_message` returns separate `attachments` and `inline_images` lists with `index` field
- `read_message` with only real attachments → `inline_images` empty
- `read_message` with only inline images → `attachments` empty
- `read_message` mixed → correct separation, indices match walk order
- `download_attachment` index still works correctly with mixed attachment+inline message (regression)
- `edit_draft` single replacement: body updated, headers/threading preserved
- `edit_draft` multiple replacements: applied in order
- `edit_draft` old_string not found → `IMAPError` with actionable message
- `edit_draft` old_string matches multiple times → `IMAPError` asking for more context
- `edit_draft` preserves existing attachments (same as `modify_draft` test pattern)
- `edit_draft` append-before-delete ordering
- `edit_draft` plain-only draft stays plain-only after edit (no HTML generated)
- `edit_draft` draft with HTML → HTML regenerated from edited plain text

**`test_imap_stream_mcp.py`:**
- `edit` action: payload parsing, validation
- `edit` action: invalid payload (missing id, missing replacements, non-numeric id, negative id) → error
- `edit` action: response format includes changes
- `edit` action: old_string not found → actionable error
- `draft` action with `format: "html"` → error with guidance
- `draft` action with `format: "plain"` → works (regression)
- `draft` action with `format: "markdown"` → works (regression)
- `read` action: inline images formatted compactly, real attachments full detail

**`test_markdown_utils.py`:**
- `convert_body` with invalid format → `ValueError`
- `convert_body` with `"html"` → `ValueError` with helpful message
- `convert_body` with `"HTML"` → `ValueError` (case sensitive)
- `convert_body` existing `"markdown"` and `"plain"` → unchanged (regression)

## Constraints

- `attachment` action download uses part walk index — both `read_message` and `download_attachment` enumerate parts in same walk order with same filter. Display categorization (attachments vs inline images) must preserve these indices. Verified: `download_attachment` line 451-454 uses identical filter to `read_message` line 381.
- `edit_draft` HTML handling: always regenerate HTML from edited plain text via `convert_body()` — no surgical HTML editing. If original draft was plain-only (no HTML part), do not generate HTML — keep it plain-only after edit.
- Error messages must suggest the correct action. "old_string not found" → suggest `read` to verify current content. Multiple matches → include snippet with surrounding context to help LLM pick unique match.
- `_rebuild_draft` refactor is deferred — implement `edit_draft` with duplicated logic first, extract helper only after both are stable and tested.

## Acceptance Criteria

- [x] `read_message` returns `attachments` (real) and `inline_images` (inline+filename) separately
- [x] Read response shows real attachments prominently, inline images compactly
- [x] `attachment` action download still works with original part indices
- [x] `edit_draft` applies old→new replacements to draft body
- [x] `edit_draft` preserves threading headers and existing attachments
- [x] `edit_draft` uses append-before-delete
- [x] `edit_draft` errors clearly on: not found, multiple matches, missing fields
- [x] `edit` action registered, routed, help text complete
- [x] `MailAction.action` and overview help updated with `edit`
- [x] `convert_body` rejects unknown format with actionable error message
- [x] `draft` action catches format validation error, returns to LLM
- [/] All existing tests pass (no regressions) — blocked in sandbox (cannot install missing deps / trio backend)
- [x] New tests cover all changes
- [x] Manual test: read Outlook email with signature images → compact inline display (1 real PDF, 24 inline images separated)
- [x] Manual test: edit draft with single replacement → text replacement works; inline images lost due to MIME structure limitation (documented in README, TODO)

## Reflection

**What went well:**
- Read separation and format validation landed cleanly — straightforward implementation with clear test coverage
- Edit action design (Claude Edit tool semantics) fit naturally into the single-tool pattern
- Code review via Codex caught real bugs: double IMAP fetch and readonly select in edit_draft
- Manual testing with real Outlook email immediately revealed the inline image separation value (25 flat → 1+24 separated)

**What changed from plan:**
- `_rebuild_draft` refactor deferred as planned — duplication accepted for now
- Inline image preservation in modify_draft turned out to be a deeper MIME structure issue (`multipart/related` reconstruction) — out of scope, documented as limitation and future TODO
- Edit action works for user-composed drafts; editing rich-client drafts (Outlook) loses inline images — documented in README

**Lessons learned:**
- Manual testing on real production data is essential — unit tests passed but real Outlook email exposed MIME structure gap that no mock would catch
- Scope discipline matters — inline image preservation was a rabbit hole that could have consumed the session. Reverting and documenting was the right call.
- `add_attachment()` always sets `Content-Disposition: attachment` regardless of what the original part had — Python email library quirk worth knowing
