# Thread-Aware Read: Quoted Reply Truncation

## Problem

`read` action returns the full email body including all quoted replies. Outlook-style full-quote threading causes massive token waste: a 19-message thread consumed ~10k tokens where only the newest message (~500 tokens) was relevant. Every quoted reply duplicates all previous messages, growing quadratically.

Complication: not all users top-post. Some write **interleaved replies** (comments inline within quoted text). Naive truncation at the first quote marker would lose these responses.

## Goal

Reduce token usage for threaded emails by separating the primary message from quoted history, with on-demand access via `:full`.

## Approach: Quote-Boundary Detection

### Detection Strategy

Identify the boundary between primary content and quoted replies using multiple signals:

1. **Outlook separator**: `________________________________` (30+ underscores) followed by `From:` — high confidence
2. **Attribution + quote**: any line ending with `:` where the next line starts with `>` — language-independent structural detection (covers "On ... wrote:", "Am ... schrieb:", etc.)
3. **Classic quoting**: Continuous block of lines starting with `>` or `> >` at the tail — medium confidence, could be interleaved
4. **Bare quote**: `>` prefixed lines without attribution line — some clients omit the "X wrote:" line

**NOT truncated:**
- Interleaved replies — if `>` quoted blocks alternate with unquoted blocks multiple times, treat the entire message as primary content

**Forwarded messages:** no programmatic detection — forwarded markers vary by client and language. If a forwarded message matches quote patterns, its tail gets truncated like any quoted tail. The key difference: unlike quoted replies (which exist as separate messages in the IMAP folder), forwarded content is unique to this message and not available elsewhere. The truncation notice informs the LLM that content was omitted, so it can reason about whether `:full` is needed — e.g. when the visible text references a forwarded message below.

Heuristic: find the **last unquoted line before a continuous quoted tail**. Everything after that boundary is the truncatable quoted section.

### Response Format

Current output structure (unchanged, only body content is truncated):
```
[UNTRUSTED CONTENT...]
<untrusted_email_content>
<header>From: ... To: ... Subject: ...</header>
<body>
[entire 10k token email including all quoted replies]
</body>
</untrusted_email_content>
**Attachments:** ...
```

New (truncation notice placed **outside** wrapper, between `</untrusted_email_content>` and attachments):
```
<untrusted_email_content>
<header>From: ... To: ... Subject: ...</header>
<body>
[primary message content only]
</body>
</untrusted_email_content>
**Quoted reply tail omitted** (~34k chars, estimated 4 messages). Use `read` with `payload: "MSG_ID:full"` for complete message. Note: composing a reply that continues the full quote chain requires `:full`.
**Attachments:** ...
```

The truncation notice is trusted metadata (like attachments), not untrusted email content — must be outside the `<untrusted_email_content>` wrapper.

### `read` Payload Extension

Current: `payload: "1450"` — read message by ID

New grammar: `^\d+(?::full)?$`
- `payload: "1450"` — read with quote truncation (default)
- `payload: "1450:full"` — read complete message without truncation
- `payload: "1450:foo"` — error: `unknown modifier 'foo'. Use '1450' or '1450:full'`

### Changes

**`imap_client.py` — new function `split_quoted_tail()`:**

```python
def split_quoted_tail(body: str) -> tuple[str, str | None, int]:
    """Separate primary content from quoted reply tail.

    Args:
        body: Plain text email body

    Returns:
        (primary_content, quoted_tail_or_none, estimated_quote_message_count)
    """
```

Detection logic:
1. Scan lines bottom-up to find the start of the continuous quoted tail
2. Outlook: look for `____...` + `From:` pattern
3. Attribution+quote: line ending `:` followed by `>` lines
4. Classic: find where continuous `>` prefixed lines begin (no unquoted breaks)
5. If interleaved pattern detected (multiple alternating quoted/unquoted blocks), return body as-is (no split)
6. Count `From:` lines in tail to estimate message count

**`imap_client.py` `read_message()` — add `full` parameter:**

```python
def read_message(folder: str, message_id: int, account: str = None, full: bool = False) -> dict:
```

- When `full=False` (default): apply `split_quoted_tail()` to `body_text`, add quote info to result. If `body_text` is empty (HTML-only email), apply to html2text output instead (html2text preserves `>` markers from blockquotes — verified).
- When `full=True`: return body as-is (current behavior)
- Result dict gets new fields: `quoted_truncated: bool`, `quoted_message_count: int`, `quoted_chars_truncated: int`

**`imap_stream_mcp.py` read action — payload parsing:**

```python
# Parse "1450" or "1450:full"
if ":" in params.payload:
    id_str, modifier = params.payload.split(":", 1)
    if modifier != "full":
        return f"Error: unknown modifier '{modifier}'. Use '{id_str}' or '{id_str}:full'"
    full = True
else:
    id_str = params.payload
    full = False

try:
    msg_id = int(id_str)
except ValueError:
    return f"Error: payload must be numeric message ID, got '{id_str}'"
```

**`imap_stream_mcp.py` read formatting — truncation notice:**

Placed outside `</untrusted_email_content>` wrapper, before attachments:
```python
# After wrapped = _wrap_email(...), before attachments_info
truncation_notice = ""
if msg.get("quoted_truncated"):
    count = msg["quoted_message_count"]
    chars = msg["quoted_chars_truncated"]
    truncation_notice = (
        f"\n**Quoted reply tail omitted** (~{chars // 1000}k chars, estimated {count} messages). "
        f'Use read with payload: "{msg_id}:full" for complete message. '
        f"Note: composing a reply that continues the full quote chain requires `:full`.\n"
    )

return security_notice + wrapped + truncation_notice + attachments_info
```

**Documentation updates:**
- `MailAction.payload` description: add `:full` modifier
- Help topic `read`: document `:full` option
- `use_mail` docstring: update read example
- `README.md` MCP API section: update read example

### What This Does NOT Do

- Does not parse individual quoted messages — binary choice: truncated or full. Original messages are available as separate IMAP messages in the same folder; quoted text is a redundant copy, not the only source.
- Does not split interleaved replies — treats those as primary content
- Does not paginate individual quoted messages
- Does not programmatically detect forwarded messages — LLM can infer from context and use `:full` when needed

## Testing Strategy

**`test_imap_client.py`:**
- `split_quoted_tail` with Outlook separator (`____` + `From:`) → correct split point
- `split_quoted_tail` with attribution + quote (line ending `:` + `>` lines) → correct split point
- `split_quoted_tail` with classic `>` tail → correct split point
- `split_quoted_tail` with bare `>` lines (no attribution) → correct split point
- `split_quoted_tail` with interleaved quoting → returns body as-is (no split)
- `split_quoted_tail` with no quotes → returns body as-is
- `split_quoted_tail` counts `From:` lines in tail for message count estimate
- `split_quoted_tail` with HTML-only email (html2text output) → correct split
- `read_message` default → truncated, `quoted_truncated=True`
- `read_message` with `full=True` → complete body, `quoted_truncated` absent or False

**`test_imap_stream_mcp.py`:**
- `read` with `payload: "123"` → truncated response with notice including `:full` hint
- `read` with `payload: "123:full"` → full response, no truncation notice
- `read` with `payload: "123:foo"` → error with guidance
- `read` with short email (no quotes) → no truncation notice
- Truncated response preserves `<untrusted_email_content>` wrapper intact
- Truncation notice placed outside wrapper, before attachments
- Injection detection still works on truncated content

**Benchmark fixture:**
- Outlook-style thread body as test fixture (19-message thread with full-quote nesting)
- Assert character reduction >80% when truncated

**Manual tests:**
- [>] Read a long Outlook thread → truncated, primary message only (deferred: requires real mailbox thread)
- [>] Read with `:full` → complete thread (deferred: requires real mailbox thread)
- [>] Read an interleaved reply email → no truncation (treated as primary) (deferred: requires real mailbox sample)

## Acceptance Criteria

- [x] `split_quoted_tail` correctly identifies Outlook, attribution+quote, and classic `>` boundaries
- [x] Interleaved quoting preserved as primary content (no false truncation)
- [x] Default `read` truncates quoted tail with notice outside wrapper
- [x] Truncation notice shows message count + chars truncated + `:full` hint
- [x] `read` with `:full` suffix returns complete body
- [x] `read` with unknown modifier returns error with guidance
- [x] Short emails without quotes returned as-is (no notice)
- [x] Wrapper/injection invariants preserved (existing tests pass)
- [x] Help, docstring, README updated with `:full` modifier
- [x] Character reduction >80% on benchmark fixture
- [x] HTML-only emails: truncation works on html2text output
- [x] All existing tests pass (no regressions)
- [>] Manual test: read interleaved reply email → no truncation (deferred: requires real mailbox sample)

## Implementation Status Updates (2026-02-25)

- [x] Setup: plan file committed in worktree as deliverable
- [x] Architecture check: plan direction fits existing `read_message`/`use_mail` boundaries; no refactor needed
- [x] Automated validation: `uv run --directory imap-stream-mcp pytest ../tests/imap-stream-mcp -q` passed (`194 passed`)
- [x] Automated validation: `uv run --directory imap-stream-mcp ruff check ../imap-stream-mcp ../tests/imap-stream-mcp` passed
- [+] Surprise handled: source copy path `/Users/vre/work/flow-state/docs/imap-stream-mcp/plans/2026-02-25-thread-aware-read.md` did not exist; proceeded with final reviewed plan present in this worktree and committed it
- [+] Review-follow-up: fixed Outlook multi-separator boundary bug (first separator now wins) and added missing plan tests for bare `>` tails, no-quote bodies, and short-email read output (no truncation notice)
- [+] Review note (accepted): HTML-only messages without quote tails can now populate `body_text` from `html2text` during split evaluation; behavior is intentional and output remains functionally correct because `read` prioritizes `body_text`
- [+] Discovered scope extension (acceptance testing): added 5th quote-boundary signal for localized Outlook header blocks without underscore separators (validated with Finnish and German fixtures), prioritized after underscore detection and before `>`-tail detection

## Reflection

**What went well:**
- Plan was tight enough for Codex to implement independently with minimal guidance. Self-contained plan requirement paid off.
- Three-phase Codex review (plan review → implementation → code review) caught the Outlook multi-separator boundary bug before it reached acceptance testing.
- Acceptance testing against real mailbox (7 emails in Test folder) immediately surfaced the localized Outlook gap — Finnish/German messages without `____` separators were not being truncated.
- Scope extension (5th detection signal) was clean — added without disrupting the existing detection priority chain.

**What changed from plan:**
- Plan originally had 4 detection signals. Acceptance testing revealed the need for a 5th: localized Outlook header blocks (e.g. Finnish `Lähettäjä:`, German `Von:`) without underscore separators.
- HTML-only email handling was discovered during implementation: `body_text` gets populated from `html2text` output during split evaluation when no plain text part exists. Not in original plan but functionally correct.
- Outlook multi-separator bug: plan assumed bottom-up scanning would naturally find the right boundary, but implementation initially took the LAST separator instead of FIRST.

**Lessons learned:**
- Real mailbox testing is irreplaceable. The Finnish/German Outlook pattern would never have been caught by fixture-based tests alone — no one would think to write that fixture without seeing the real email first.
- "First match wins" vs "last match wins" is a recurring boundary detection bug pattern. Worth adding to review checklist.
- Codex session continuity (resume) across plan review → implementation → code review saved significant context and tokens. The reviewer already knew the plan when reviewing code.
