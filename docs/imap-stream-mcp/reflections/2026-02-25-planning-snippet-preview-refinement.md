# 2026-02-25 Planning Reflections: Snippet Preview Plan Refinement

Plan: `docs/imap-stream-mcp/plans/2026-02-24-list-search-snippet.md`

## How planning went

The snippet plan was drafted in a previous session alongside the attachment indicator plan. This session's task: refine the plan from draft to implementation-ready. Not a new plan — a hardening pass.

**Codebase verification.** Read all four key source files against the plan's claims. Found the plan's line numbers were estimates ("post att-indicator") since attachment indicator (v0.6.0) was now implemented. Updated all line numbers to actual current code. Also discovered test count had changed: 202 tests (plan said 86+43=129 from pre-v0.6.0).

**Structural additions.** The original plan was research-heavy (BODYSTRUCTURE format, IMAP part numbering, decoding pipeline) but lacked implementation structure. Added: 7-step task breakdown, explicit error handling strategy, `is_html` flag tracking pseudocode, session.py code flow description.

**Self-review.** Found 4 issues: `find_text_part`/`find_html_part` missing None guard (inconsistent with `count_attachments` which accepts `tuple | None`), `is_html` tracking not shown in caller code, `_strip_html_tags` didn't handle `<style>`/`<script>` content, session.py code flow vague about insertion point.

**External review (subagent).** Found 6 actionable items: hardcoded "202 tests" in acceptance criteria, `message/rfc822` not recursed (undocumented limitation), `imap_client.py` uses `client` not `conn` (plan handwaved "same pattern"), snippet FETCH error could break entire message listing without try/except, explicit `dict[int, str]` mapping needed for snippet merge, base64 rounding direction unspecified.

## HC's part

- Directed session scope: snippet plan refinement here, attachment indicator discovery via parallel agent
- Rejected worktree creation (not implementation, just planning)
- Chose "send to applicant" for review step

## My part

- Verified all plan claims against actual source code (line numbers, function signatures, data flow)
- Added implementation tasks, error handling, code flow descriptions
- Self-reviewed as skeptic, found and fixed 4 issues
- Incorporated all 6 actionable review findings
- Added "Known limitations" section (message/rfc822, truncated style tags)

## What I learned about planning

1. **Plans written during research need a separate hardening pass.** The original plan had excellent research (BODYSTRUCTURE format, decoding pipeline, competitive analysis) but lacked the practical structure an implementing agent needs: task order, error handling, code flow insertion points. Research and implementation planning are different skills.

2. **Line numbers drift.** The plan was written pre-v0.6.0 with estimated "post att-indicator" line numbers. After implementation of the dependency, all references were stale. Plans that reference specific line numbers need re-verification when the dependency is implemented.

3. **Consistency with existing conventions matters more than correctness alone.** `find_text_part(body: tuple)` was correct but inconsistent with `count_attachments(body: tuple | None)` in the same module. The review caught this — the implementing agent might not. Convention consistency prevents subtle bugs.

4. **"Same pattern" is not a plan.** Saying `imap_client.py` uses "same pattern as session.py" is insufficient when the code structures differ (variable names, loop patterns, context managers). The implementing agent needs explicit instructions per file, even when the logic is similar.
