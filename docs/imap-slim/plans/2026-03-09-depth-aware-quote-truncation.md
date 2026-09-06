# Depth-aware quote truncation for inline replies

## Problem

`split_quoted_tail()` cuts at the first separator (Outlook `________________________________`+`From:`, `On ... wrote:`, localized headers). When someone replies inline (writes answers between the quoted message's lines — common pre-Outlook practice, still used by Outlook users), the actual reply content lives at depth 1 and gets truncated.

Real example: Harriniva message #67 where Meeri says "Löydät vastaukset alta edellisestä sähköpostista" and her answers (prices, confirmations, details) are interspersed in Ville's quoted message at depth 1. Current code returns ~1k chars (Meeri's intro only), discarding ~6k of inline answers. Before `split_quoted_tail` existed (23.2 session), the full 44k came through and blew the token limit.

## Goal

Three-level progressive disclosure via payload modifiers:

| Payload | Content | Token cost | Use case |
|---------|---------|-----------|----------|
| `"67"` | depth 0 only | minimal | default, quick scan |
| `"67:1"` | depth 0+1 | moderate | inline answers, reply context |
| `"67:2"` | depth 0+1+2 | more | deeper chain context |
| `"67:full"` | all depths | maximum | composing reply with full chain |

Truncation notice guides the LLM to request deeper levels. Numeric `:N` modifiers for any depth, `:full` for everything.

> **Post-implementation note**: Originally planned as `:more` (fixed depth 1), changed to numeric `:N` during review for extensibility.

## Acceptance Criteria

- [ ] AC1: Default read returns depth 0 only, truncation notice mentions `:more` and `:full`
- [ ] AC2: `:more` returns depth 0+1, truncation notice mentions `:full` for remaining depth 2+
- [ ] AC3: `:full` returns everything unchanged (existing behavior)
- [ ] AC4: Messages with only 1 separator: `:more` and `:full` produce identical output
- [ ] AC5: Messages with no separators: all three modifiers return the same body
- [ ] AC6: Truncation notices show correct char counts and estimated message counts for omitted section
- [ ] AC7: Invalid modifier (e.g. `:bogus`) returns error message with valid options
- [ ] AC8: HTML-only messages work correctly with `:more` (html2text conversion before boundary detection)
- [ ] AC9: Interleaved `>`-quote messages (≥3 transitions) no longer bypass truncation — depth 0 returned by default, depth 0+1 via `:more`
- [ ] AC10: Unit tests in existing test files with synthetic fixtures, deterministic expected outputs

## Design

### Separator detection

Reuse existing patterns — they already detect boundaries well:
1. Outlook: `_{30,}` + `From:` line
2. Localized Outlook: `\w[\w\s]*:.*<email>` + ≥2 header lines
3. Classic attribution: `On ... wrote:` or equivalent + `>` lines
4. Tail `>` block with `:` attribution

### Core function

```python
_find_all_boundaries(lines: list[str]) -> list[int]
```
Returns sorted, deduplicated list of line indices where each depth boundary starts. Scans entire body forward.

**Precedence rules when patterns overlap:**
- If Outlook separator (`_{30,}` + `From:`) and localized header start at same or adjacent lines, Outlook wins (higher confidence)
- Classic attribution (`On ... wrote:`) that immediately precedes an Outlook separator is part of that boundary, not a separate one
- Minimum gap between boundaries: 3 non-blank lines (prevents email signature `From:`-lines and short metadata blocks from creating false boundaries — signatures typically have 0-2 content lines between separator patterns)
- Tail `>` block detection (backward scan) used only as fallback when forward scan finds 0 boundaries

### `split_quoted_tail()` change

New signature:
```python
def split_quoted_tail(body: str, depth: int = 0) -> tuple[str, str | None, int]:
```

- `depth=0`: cut at boundaries[0] (default — depth 0 only)
- `depth=1`: cut at boundaries[1] if exists (depth 0+1)

If requested depth ≥ len(boundaries), return full body (no tail to cut).

### Interleaved reply safety (lines 393-397)

Remove. The old heuristic (≥3 transitions between quote/plain) returned the entire body untruncated (44k+). With depth-based approach, interleaved content at depth 1 is accessible via `:more`. Default returns only depth 0.

**Regression guard**: existing test at `test_imap_client.py:875` must be updated — expected behavior changes from "return full body" to "return depth 0, truncate at first boundary". Add new test verifying `:more` returns depth 0+1 for interleaved messages.

### Payload parsing

In `imap_stream_mcp.py` action dispatch (around line 580):
- `"67"` → `full=False, depth=0`
- `"67:more"` → `full=False, depth=1`
- `"67:full"` → `full=True` (skip `split_quoted_tail` entirely, unchanged)
- `"67:bogus"` → error with valid modifiers listed

Update payload description string (line ~208) and tool docstring to include `:more`.

### `read_message()` contract

Add `depth: int = 0` parameter to `read_message()`. Passed through to `split_quoted_tail()`. `full=True` still skips truncation entirely (unchanged).

### Truncation notice

Depth 0 (default), boundaries exist:
```
**Quoted reply chain omitted** (~44k chars, ~11 messages).
Use ":more" for previous message with inline replies, ":full" for complete chain.
```

Depth 1 (`:more`), deeper boundaries exist:
```
**Older reply chain omitted** (~38k chars, ~9 messages).
Use ":full" for complete chain.
```

Depth 1 (`:more`), no deeper boundaries:
No truncation notice (full content shown).

### `>` quoting edge case

`_find_all_boundaries()` scans forward for Outlook/localized/classic-attribution separators only. The tail-`>` detection (current lines 433-446, scanning backwards) remains as fallback when forward scan finds 0 boundaries — it produces a single boundary, not multiple. Nested `>>` / `>>>` within a `>` block are not separate boundaries.

### Help text update

Update `action: "help", payload: "read"` to document `:more` modifier.

## Tasks

Order: core logic → API contract → wiring → docs → tests → verify.

- [x] 1. Extract `_find_all_boundaries(lines) → list[int]` from existing separator detection, with precedence/dedup rules
- [x] 2. Refactor `split_quoted_tail()` to accept `depth` param and use `_find_all_boundaries()`
- [x] 3. Remove interleaved reply early-return (lines 393-397)
- [x] 4. Add `depth` param to `read_message()`, pass through to `split_quoted_tail()`
- [x] 5. Parse `:more` modifier in `imap_stream_mcp.py` payload handling (alongside `:full`), error on invalid modifiers
- [x] 6. Update truncation notice to show `:more` / `:full` guidance based on available depths
- [x] 7. Update payload description string, tool docstring, and help text (add `:more`)
- [x] 8. Add unit tests to `tests/imap-stream-mcp/test_imap_client.py`: `_find_all_boundaries()` and `split_quoted_tail()` with depth param — synthetic fixtures with deterministic assertions
- [x] 9. Add/update unit tests in `tests/imap-stream-mcp/test_imap_stream_mcp.py`: `:more` parsing, invalid modifier error, truncation notice content
- [x] 10. Update existing interleaved test (test_imap_client.py:875) to match new behavior
- [x] 11. Add edge case tests: HTML-only + `:more`, boundary at line 0, localized header false positive guard, interleaved `>` with fallback-only boundary, min-gap boundary suppression (short gap = no false split, legitimate boundary with 4+ lines = kept)
- [x] 12. Run full test suite (ran; 20 pre-existing draft-flag test failures outside this plan scope)
- [x] 13. Manual verification: `"67"`, `"67:1"`, `"67:full"` on Hotelli message (vre@mail.vre.iki.fi) — depth 0: 1690 chars, depth 1: 13326 chars with inline answers, full: 47376 chars
- [x] 14. Manual verification: `"35"`, `"35:1"` on single-separator message — 9 boundaries found in long thread

## Reflection

<!-- Written post-implementation by IMP -->
<!-- ### What went well -->
<!-- ### What changed from plan -->
<!-- ### Lessons learned -->
