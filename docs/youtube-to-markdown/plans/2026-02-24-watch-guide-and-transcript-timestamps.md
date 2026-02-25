# Watch Guide & Transcript Timestamp Preservation

## Problem

Two related issues:

**1. Stored transcript is the worst version.** Option A (summary + comments, ~80% of extractions) saves `_transcript_no_timestamps.txt` — uncleaned, no timestamps, no paragraph breaks. The pipeline produces a timestamped dedup (`_transcript_dedup.md` with `[HH:MM:SS.mmm]` per cue) but deletes it as intermediate. Users can't skim or deep-link into the stored transcript. Additionally, if user later on want to make actual cleaned polished transcript this saved transcript dump is now missing timestamps that are needed for paragraph timestamps.

**2. No watch guide.** Some videos have segments worth watching (physical demonstrations, emotional delivery, visual explanations) while others are better consumed as text. No mechanism exists to distinguish or recommend.

## Discovery (PoC Results)

Tested watch guide generation on two videos using existing artifacts:

**Talking head (Nate B Jones, 30 min, market analysis):**
- Verdict: SKIM — 9 min of 30 recommended
- Gate correctly identified most content is better as text
- 3 highlights: opening narrative hook, central metaphor, closing argument

**Dojo demo (Bas Rutten + Jesse Enkamp, 25 min, martial arts):**
- Verdict: WATCH — 14 min of 25 recommended
- Gate correctly identified physical techniques require visual medium
- 6 highlights with strong "why watch > read" justifications
- Skip list discriminated talk-heavy segments within a demo video

**Key findings:**
- Gate (WATCH / SKIM / READ-ONLY) works across content types
- "Why watch > read" justifications are stronger for physical/visual content
- Model infers visual content from transcript cues ("look at this", "let me show you") — reasonable heuristic
- YouTube deep links: `?t=Ns` (start time only, no end time parameter exists)
- Without timestamps, timing is approximate guesswork — timestamps are prerequisite

## Architecture Context

Key files (relative to `youtube-to-markdown/`):
- `SKILL.md` — main orchestrator, routes to subskills
- `subskills/transcript_polish.md` — full polish pipeline (3 LLM steps, option B/D only)
- `lib/paragraph_breaker.py` — generates YouTube deep links per paragraph: `[[HH:MM:SS]](https://youtube.com/watch?v=ID&t=Ns)`
- `lib/assembler.py` — `_save_raw_transcript()` saves `_transcript_no_timestamps.txt`; `find_existing_summary()` classifies output files; `assemble_transcript_content()` has fallback chain
- `lib/check_existing.py` — `find_existing_files()` classifies existing files by suffix
- `lib/intermediate_files.py` — defines which files are cleaned up
- `scripts/31_format_transcript.py` — applies paragraph breaks with timestamp links

Current pipelines:
```
A: transcript_extract → (transcript_summarize | comment_extract) → comment_summarize → assemble
   Stored transcript: _transcript_no_timestamps.txt (wrong file)

B: transcript_extract → (transcript_summarize | transcript_polish | comment_extract) → comment_summarize → assemble
   Stored transcript: _transcript.md (polished, with headings + YouTube links)

C: transcript_extract → transcript_summarize → assemble
D: transcript_extract → transcript_polish → assemble
```

Full polish pipeline (option B/D) — 3 LLM calls:
1. Sonnet: identify paragraph break line numbers → `31_format_transcript.py` applies breaks + YouTube links
2. Haiku: clean speech artifacts (fillers, punctuation)
3. Sonnet: add topic headings

## Design

### Part 1: Fix stored transcript for option A/C

**Change:** `assembler.py` `_save_raw_transcript()` saves `_transcript_dedup.md` instead of `_transcript_no_timestamps.txt`.

No new subskill, no extra LLM calls. The dedup file has per-cue timestamps (`[00:01:23.000] Text here`) — not as clean as the polished version but skimmable and timestamp-searchable. Users who want the polished version use option B.

**Fallback chain fix in `assemble_transcript_content()`:** Current chain is `_transcript.md` → `_transcript_no_timestamps.txt`. Updated chain:
```python
_transcript.md → _transcript_dedup.md → _transcript_no_timestamps.txt
```
This handles: (1) polished transcript exists (option B re-extract), (2) dedup exists (new option A), (3) legacy files from before this change.

**UX note:** The dedup format is one line per VTT cue (short lines with timestamps). Not paragraph-formatted, but preserves all content with timing. The transcript template wraps it with the description section as before.

### Part 2: Watch guide — combined with option B polish

The watch guide lives in option B, where the full polish pipeline already runs. After polishing, the LLM has read and understood the entire transcript. The watch guide is generated as an additional step using the polished transcript + summary + comments.

**New subskill:** `watch_guide.md`

**Inputs:**
- `_transcript.md` (polished transcript with topic headings and YouTube deep links)
- `_summary_tight.md` (what the video covers)
- `_comment_insights_tight.md` (what resonated — if available)
- `_chapters.json` (chapter structure — if available)
- `_metadata.md` (video type, duration, engagement)

**Output:** `_watch_guide.md`

**Prompt structure:**
1. **Gate decision**: WATCH / SKIM / READ-ONLY with 1-2 sentence justification
2. **Highlights** (if WATCH/SKIM): Timestamped segments with:
   - YouTube deep link to start time
   - Heading name of corresponding transcript section (verbatim from polished transcript)
   - "Why watch > read" justification
3. **Read instead** (if WATCH/SKIM): Sections where reading the transcript or summary is sufficient, with heading name + brief reason
4. **Watch route**: Compact speed-run — total minutes, ordered deep links

**Gate signals:**
- Content type: TUTORIAL/demo → likely WATCH; pure analysis → likely SKIM/READ-ONLY
- Transcript cues: LLM deduces from speech patterns (demonstrations, physical actions, visual references)
- Multiple speakers/interaction → more watchable than monologue
- Comment references to specific moments → highlights exist

**Gate output handling:**
- First line of `_watch_guide.md` MUST be exactly one of: `WATCH:`, `SKIM:`, or `READ-ONLY:` followed by justification
- WATCH/SKIM: subagent writes full guide content after verdict line
- READ-ONLY: subagent writes only the verdict line (e.g. `READ-ONLY: Talking-head monologue, summary covers all content.`)
- Assembler parses first line: if starts with `READ-ONLY:`, skips file creation
- **Fail-safe:** If first line doesn't match any verdict pattern → treat as READ-ONLY (skip). Log warning.

**Language:** Subagent writes the watch guide in the same language as the transcript content. Prompt includes: "Write in the same language as the transcript."

**Long transcript fail-safe:** If `_transcript.md` exceeds 150 KB, skip watch guide generation entirely — the Sonnet call would likely hit output limits. Log skip reason. This is a temporary guard until the long transcript chunking plan is implemented.

**Model:** Sonnet. One call.

### Part 3: Cross-linking

The polished transcript (option B) has topic headings like `### Boss Combination with Deception`. The watch guide references these.

**LLM writes heading names only.** The watch guide subagent reads the polished transcript and copies heading text verbatim for each cross-link reference. No filenames, no slugs, no anchor formatting in the LLM output.

**Cross-link line format:** Lines starting with `→ ` (arrow + space) on their own line are cross-link references. Everything after `→ ` up to end of line is the heading name. No other content on the same line — reason text goes on the preceding line.

**Assembler post-processes cross-links.** After watch guide generation, the assembler:
1. Reads `_watch_guide.md`
2. Finds lines matching `^→ (.+)$` (regex: start of line, arrow, space, capture heading name)
3. Converts to: `  Transcript: [Heading Name](TRANSCRIPT_FILENAME#slug)`
4. Slug algorithm: `re.sub(r'[^\w\s-]', '', heading.lower()).strip().replace(' ', '-')` — same as GitHub-flavored markdown
5. Duplicate headings: GitHub appends `-1`, `-2` etc. Assembler reads the polished transcript, builds an ordered heading→slug map counting duplicates. When watch guide references a heading that appears multiple times, link to the first occurrence (LLM sees sequential transcript, first match is the natural reference)
6. Unresolved headings: if `→ Heading Name` doesn't match any transcript heading, keep the line as plain text (no link). Log warning. LLM typo is the likely cause — not a fatal error.
7. `TRANSCRIPT_FILENAME` is known to the assembler (it just created it)

This avoids the LLM needing to produce filenames or slugs — the assembler owns all file naming.

**Watch guide format (LLM output):**
```markdown
WATCH: Physical technique demonstrations require visual observation.

## Highlights

**[03:12](https://youtube.com/watch?v=ID&t=192s)** Boss Combination — identical load-up deception only visible in motion
→ Boss Combination with Deception

**[08:45](https://youtube.com/watch?v=ID&t=525s)** Liver kick angle — camera shows exact hip rotation
→ Liver Kick Technique

## Read Instead

Three Categories of AI Exposure — taxonomy reads faster than spoken enumeration
→ Three Categories of AI Exposure

## Watch Route

14 min of 25: [03:12](…) → [08:45](…) → [15:30](…)
```

Note: In "Read Instead", the reason text is on the line above the `→` reference. The `→` line contains only the heading name.

**Assembler transforms `→ Heading Name` lines to:**
```markdown
  Transcript: [Boss Combination with Deception](YYYY-MM-DD - youtube - Title - transcript (ID).md#boss-combination-with-deception)
```

**No backward links.** Watch guide links to transcript sections. Transcript does not link back to watch guide — would add complexity for marginal value.

### Part 4: Assembly changes

**New file:** `YYYY-MM-DD - youtube - Title - watch guide (VIDEO_ID).md`

**File classification fix — 3 locations:**
1. `lib/assembler.py` `find_existing_summary()`: Add `" - watch guide "` to exclusion list alongside `" - transcript "` and `" - comments "`
2. `lib/check_existing.py` `find_existing_files()`: Add `elif " - watch guide " in name:` branch, store as `watch_guide_file`
3. `subskills/update_flow.md`: Watch guide classification in re-extraction logic

**Template** (`templates/watch_guide.md`):
```
## Watch Guide

{watch_guide}
```

**Assembler changes:**
- New method `_save_watch_guide()`:
  1. Read `_watch_guide.md`
  2. Parse first line for verdict — if READ-ONLY or unparseable, return (no file)
  3. Post-process cross-links: replace `→ Heading Name` lines with markdown links to transcript file
  4. Create final watch guide file
- Add to `finalize_full()` (option B) — called after transcript file is created (needs transcript filename for cross-links)
- Add `_watch_guide.md` to intermediate files list

### Part 5: Pipeline integration

Updated flows — only option A/C transcript storage and option B watch guide change:

```
A: transcript_extract → (transcript_summarize | comment_extract) → comment_summarize → assemble
   Change: assemble saves _transcript_dedup.md instead of _transcript_no_timestamps.txt

B: transcript_extract → (transcript_summarize | transcript_polish | comment_extract) → comment_summarize → watch_guide → assemble
   Change: watch_guide added after comment_summarize (needs polished transcript)

C: transcript_extract → transcript_summarize → assemble
   Change: assemble saves _transcript_dedup.md instead of _transcript_no_timestamps.txt

D: transcript_extract → transcript_polish → assemble
   No change
```

### Part 6: Update flow (re-extraction lifecycle)

**Data model changes:**

`lib/check_existing.py` `find_existing_files()` currently returns `summary_file`, `comment_file`, `transcript_file`. Add `watch_guide_file`:
```python
elif " - watch guide " in name:
    watch_guide_file = f
```

`lib/prepare_update.py` `prepare_update()` has two `existing_files` dicts — `EXISTS` (line ~285) and `UNAVAILABLE` (line ~258). Add `"watch_guide": existing.get("watch_guide_file")` to both for schema consistency.

`lib/check_existing.py` `check_existing()` — propagate `watch_guide_file` from `find_existing_files()` into `existing` dict so `prepare_update()` can access it.

**`subskills/update_flow.md` changes:**

Step U2 status table — add Watch Guide row:
```
| Watch Guide | exists/missing | - | - |
```

Step U3 options — no new option needed. Watch guide is affected by transcript re-extract (backup+delete) and full refresh (backup+delete+regenerate if user picks option B).

Step U4 behavior:
- **"Re-extract transcript":** If `existing_files.watch_guide` exists, backup and delete original. Watch guide is NOT regenerated during transcript re-extract — the watch guide subskill needs `_summary_tight.md` and `_comment_insights_tight.md` which are not available (cleaned up after original run). User must do full refresh to regenerate watch guide. Inform user: "Watch guide backed up. Full refresh needed to regenerate."
- **"Full refresh":** If `existing_files.watch_guide` exists, backup and delete original. Watch guide regenerated as part of option B pipeline.
- **"Re-extract comments":** Watch guide unchanged.
- **"Update metadata only":** Watch guide unchanged.
- **"Add comments":** Watch guide unchanged.
- **"Keep existing":** No change.

**Backup + delete pattern:** `40_backup.py backup` copies the file. After backup, delete the original to prevent stale watch guide remaining when new verdict is READ-ONLY or when re-extract changes transcript headings.

### Option A description update

Current: "Summary cross-analyzed with comments. Transcript stored if user would like to format it later."
New: "Summary cross-analyzed with comments. Timestamped transcript stored for reference."

Option B description stays — add mention of watch guide:
New: "Option A + cleaned and formatted full transcript with watch guide → double tokens"

## Implementation Tasks

- [x] 1. Update `lib/assembler.py` — `_save_raw_transcript()` prefers `_transcript_dedup.md` over `_transcript_no_timestamps.txt`
- [x] 2. Update `lib/assembler.py` — `assemble_transcript_content()` fallback chain: `_transcript.md` → `_transcript_dedup.md` → `_transcript_no_timestamps.txt`
- [x] 3. Update `lib/assembler.py` — `find_existing_summary()` excludes `" - watch guide "` in name
- [x] 4. Update `lib/check_existing.py` — `find_existing_files()` adds `watch_guide_file` field for `" - watch guide "` suffix; `check_existing()` propagates it
- [x] 5. Create `subskills/watch_guide.md` — prompt based on PoC, gate + highlights + read-instead + watch route. Heading names only (no slugs/filenames). Language matches transcript. Long transcript fail-safe at 150 KB.
- [x] 6. Create `templates/watch_guide.md`
- [x] 7. Update `lib/intermediate_files.py` — add `_watch_guide.md` to work file lists
- [x] 8. Update `lib/assembler.py` — new `_save_watch_guide()` method: verdict parsing (fail-safe to READ-ONLY), cross-link post-processing (`^→ (.+)$` → markdown anchor link with duplicate heading numbering), integrate into `finalize_full()`
- [x] 9. Update `scripts/50_assemble.py` — if `finalize_full()` signature or return type changes
- [x] 10. Update `SKILL.md` — option B flow adds watch_guide step, update option A/B descriptions
- [x] 11. Update `lib/prepare_update.py` — add `watch_guide` to `existing_files` dict in `prepare_update()`
- [x] 12. Update `subskills/update_flow.md` — watch guide row in status table, backup+delete on transcript re-extract (no regenerate), backup+delete on full refresh (regenerate only if user picks option B)
- [x] 13. Tests (fixture-based, CI-compatible):
  - Unit: assembler dedup transcript fallback chain (mock filesystem with each combination)
  - Unit: `_save_watch_guide()` — gate=WATCH produces file, gate=READ-ONLY skips, gate=unparseable skips
  - Unit: cross-link post-processing — `→ Heading Name` → `[Heading Name](file.md#heading-name)`. Slug map builds with `-1` suffixes for duplicates, but `→` reference resolves to first occurrence (no suffix). Unresolved heading kept as plain text (no link)
  - Unit: `find_existing_summary()` excludes watch guide files
  - Unit: `find_existing_files()` classifies watch guide files and returns `watch_guide_file`
  - Unit: `prepare_update()` includes `watch_guide` in `existing_files` (both EXISTS and UNAVAILABLE paths)
  - Manual (non-CI): test on Bas Rutten (demo, expect WATCH) + Nate B Jones (talking head, expect SKIM/READ-ONLY)
- [x] 14. Verify cross-linking: watch guide heading anchors match actual polished transcript headings

## Acceptance Criteria

- [x] Option A/C stored transcript is `_transcript_dedup.md` with per-cue timestamps, not `_transcript_no_timestamps.txt`
- [x] `assemble_transcript_content()` fallback chain: polished → dedup → no-timestamps (handles all legacy cases)
- [x] `find_existing_summary()` and `find_existing_files()` correctly classify watch guide files (not as summary); `prepare_update()` includes `watch_guide` in `existing_files`
- [x] Option B generates watch guide file when gate fires WATCH or SKIM
- [x] No watch guide file when gate fires READ-ONLY or verdict is unparseable
- [x] Watch guide written in same language as transcript
- [>] Watch guide contains YouTube deep links that open video at correct timestamp
- [x] Watch guide cross-links to transcript section headings via assembler post-processing (LLM writes `→ Heading Name` lines, assembler creates links with duplicate heading numbering)
- [x] Watch guide "read instead" sections point to specific transcript sections
- [>] Gate correctly distinguishes demo videos (WATCH) from talking-head (SKIM/READ-ONLY)
- [x] Watch guide skipped for transcripts > 150 KB
- [x] Update flow handles watch guide lifecycle: `prepare_update.py` reports watch guide, `update_flow.md` backs up + deletes on transcript re-extract (no regenerate), backs up + deletes on full refresh (regenerate only if user picks option B)
- [x] Existing tests pass
- [x] New fixture-based unit tests for assembler changes (dedup fallback, watch guide assembly, gate parsing, cross-link processing, file classification)

## Scope Boundaries

**In scope:**
- Save timestamped dedup transcript for option A/C (assembler fix)
- Watch guide generation for option B with gate
- Cross-linking: watch guide → transcript headings (assembler post-processing)
- Assembly of watch guide as separate file
- File classification fix for watch guide
- Update flow lifecycle for watch guide

**Out of scope (future):**
- Watch guide for option A/C (no polished transcript to cross-link)
- Watch guide for option D (transcript-only mode)
- Clip end-time parameters (YouTube doesn't support)
- Long transcript chunking (separate plan: `2026-02-24-long-transcript-chunking.md`)

## Open Question

**Option C watch guide?** Option C (summary only) has no polished transcript but does have `_transcript_dedup.md` (timestamps) and `_summary_tight.md`. The PoC worked with just transcript + summary (Nate B Jones test had no comments). Could offer a degraded watch guide (YouTube deep links, no cross-links to transcript headings) for option C. Decision: defer — option C is rarely used and the value of a watch guide without a readable transcript to cross-link is limited.

## Risk

- **Watch guide quality without seeing video:** Model infers visual content from transcript cues. Heuristic, not ground truth. Mitigation: gate suppresses guide for READ-ONLY + fail-safe for unparseable verdict. Acceptable for v1, will improve with user feedback.
- **Timestamp precision:** Per-cue timestamps are accurate to the VTT source. Paragraph-level timestamps in polished transcript pick the first cue — may be off by seconds. Acceptable for "jump to this section."
- **Token cost:** Watch guide adds 1 Sonnet call to option B. Option A/C cost unchanged.
- **Cross-link fragility:** Assembler post-processing eliminates LLM slug/filename generation risk. Remaining risk: LLM copies heading name with typo. Mitigated: subagent reads polished transcript and copies headings verbatim. Both generated in same pipeline run.
- **Anchor format:** Assembler generates GitHub-flavored markdown anchors (lowercase, hyphens, strip special chars). Obsidian uses `#heading` with original casing. If target is Obsidian, may need to adjust slug format. Verify during integration testing.
- **Long transcripts:** Watch guide skipped at 150 KB — temporary guard. Proper fix in long transcript chunking plan.

## Reflection

**What went well:**
- Plan went through 5 Codex review rounds, each progressively finding fewer and less severe issues. The iterative review process eliminated contradictions and underspecified behaviors before implementation.
- Cross-link design (LLM writes `→ Heading Name`, assembler creates links) cleanly separates concerns — LLM handles content, Python handles formatting.
- Implementation was straightforward because the plan was detailed enough to be self-contained for delegation.

**What changed from plan:**
- Codex couldn't commit during implementation due to sandbox limitations (review session inherited read-only mode). Commits done manually after.
- Test file initially placed in wrong directory (`youtube-to-markdown/tests/` instead of `tests/youtube-to-markdown/`). Caught in code review.
- `_watch_guide.md` intermediate file initially placed in `get_transcript_work_files()` — moved to `get_all_work_files()` aggregation level during review.
- SKIM verdict test was missing — added via parametrization during acceptance testing.

**Lessons learned:**
- Codex session resume inherits sandbox settings from first run. For implementation after review, a new session or worktree-mode first run is needed.
- Plan review iterations are high-value: each round caught real contradictions (e.g., "regenerate" vs "NOT regenerated" for transcript re-extract).
- Acceptance testing against explicit AC list is effective — the SKIM test gap would have been missed without systematic verification.
