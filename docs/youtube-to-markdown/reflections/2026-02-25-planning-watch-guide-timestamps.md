# 2026-02-25 Planning Reflections: Watch Guide & Transcript Timestamps

Plan: `docs/youtube-to-markdown/plans/2026-02-24-watch-guide-and-transcript-timestamps.md`

## How planning went

Started as a loose idea ("what if we suggest parts to watch?") and evolved through PoC discovery into a two-part plan. Three distinct phases: PoC testing, plan writing, and review-driven amendment.

**PoC phase.** Tested watch guide generation on two contrasting videos before writing any plan. Talking head (Nate B Jones) → SKIM verdict, 9/30 min. Dojo demo (Bas Rutten) → WATCH verdict, 14/25 min. Gate mechanism validated across content types. During PoC, HC noticed timestamps were lost in the stored transcript — this coupled the watch guide idea with a transcript quality fix.

**Plan v1 (overengineered).** I proposed a "light polish" subskill for option A that would add an extra LLM call. HC corrected: option A just needs to save a different file (dedup instead of no-timestamps). No new subskill, no extra cost.

**Plan v2 (rewritten).** HC's architecture: option A swaps file (1 line change), watch guide lives only in option B (where polish already runs). Simpler and correct.

**Self-review.** Found 6 issues: invalid cross-link markdown format, missing READ-ONLY gate protocol, dedup UX note needed, missing script update task, option C question, anchor format risk.

**Codex review.** Found 9 issues (5 critical/high). Most impactful: watch guide filename collides with summary detection in 3 locations, assembler fallback chain underspecified, cross-link filenames can't be reliably produced by LLM, update mode doesn't handle watch guide, tests aren't CI-compatible.

**Amendment.** Addressed all 9 issues. Key design change: moved cross-link generation from LLM to assembler (LLM writes `→ Heading Name`, assembler creates `[Heading Name](file.md#slug)`). Implementation tasks grew from 9 to 13.

## HC's part

- Originated the watch guide idea and steered it toward practical implementation
- Selected test videos and drove PoC testing before planning
- Corrected overengineering twice: no "light polish" subskill, watch guide only in option B
- Noticed timestamp loss during PoC — coupled the two features
- Directed Codex review via codex-session skill

## My part

- Ran PoC tests on two videos, validated gate mechanism
- Discovered transcript timestamp loss in pipeline (confirmed HC's observation)
- Wrote and rewrote plan (v1 overengineered → v2 correct)
- Self-reviewed: found 6 issues
- Amended plan based on 9 Codex review findings

## What I learned about planning

1. **PoC before plan eliminates format speculation.** The PoC proved the gate works, showed what output looks like, and revealed the timestamp dependency — all before writing a single plan line. Without PoC, I would have speculated about gate signals and output format.

2. **HC corrects architecture, not details.** Both corrections were structural: "don't add a subskill, just swap the file" and "watch guide lives in option B only." These aren't typos or missing edge cases — they're fundamental architecture decisions that prevent unnecessary complexity.

3. **LLMs should not generate filenames or slugs.** The Codex review caught that expecting the LLM to produce correct markdown anchor slugs and filenames is fragile. Moving this to the assembler (Python) is both more reliable and testable. General principle: deterministic formatting belongs in code, not prompts.

4. **File classification is a cross-cutting concern.** Adding a new output file type (watch guide) requires updates in 3+ locations that classify files by suffix. Easy to miss one. A future refactor could centralize file type detection.
