# 2026-02-24 Planning Reflections: IMAP MCP UX Improvements

Plan: `docs/imap-stream-mcp/plans/2026-02-23-ux-improvements.md`

## How planning went

HC identified the three problems from real usage (VikingPLoP2026 session) and brought concrete pain points: LLM doesn't find modify, attachments flood context, draft editing is slow. My role was to mine the session data for evidence, quantify the problems (22 draft calls, 43KB read results, 177s worst case), and propose solutions.

HC steered key design decisions:
- Inline images should still be listed (not hidden) so they're retrievable
- Edit action should follow Claude's Edit tool pattern (old_string/new_string)
- Format validation should reject everything except `plain` and `markdown`
- Challenged my initial "show first 3 + count" inline image display — all should be addressable

I proposed three options for edit (MCP action, tmp file + Edit tool, replace field in draft action). HC picked the standalone action, which was also my recommendation.

## Codex review value

Codex (o4-mini fallback to default) found 9 issues. Most valuable findings:
- `except Exception` already catches `ValueError` — my plan claimed it didn't (factual error against code)
- Attachment schema inconsistency: I said `{filename, content_type, size}` then later required index without updating the schema
- Missing test for `download_attachment` index preservation with mixed parts — the highest regression risk
- HTML text-node editing is infeasible — I had a half-baked "preserve tags" approach that would have been brittle

Less valuable: scope concern about `_rebuild_draft` refactor was valid but I had already flagged it in self-review.

## Lessons

1. **Real session data beats hypotheticals.** The 967-line JSONL analysis gave precise numbers (22 drafts, 24 inline images, 43KB per read) that made the plan concrete. Without this, the plan would have been "read is too verbose" instead of "Outlook signature images produce 24 useless metadata lines."

2. **HC's domain knowledge is irreplaceable.** I would have hidden inline images entirely. HC knew they should be visible but compact — email users sometimes need signature images. This is domain knowledge that no amount of code analysis provides.

3. **Codex catches factual errors against code.** My ValueError claim was wrong — I didn't check the outer exception handler. The reviewer's first instinct was to verify claims against actual source, which caught the error immediately.
