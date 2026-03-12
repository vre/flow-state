# Watch Guide Into Polish Pipeline

## Problem

Watch guide is a separate subskill (`watch_guide.md`) that runs after polish, re-reading the full `_transcript.md` (150KB+). The 150KB guard blocks it on long transcripts — exactly the videos where a watch guide is most useful (2-3h podcasts).

The cleaning subagent in Step 2 already reads each chunk of transcript. It understands the content but discards that understanding — it only outputs cleaned text. The watch guide, headings, and potentially summary all need content understanding that the cleaning step already has.

The current watch guide gives a single WATCH/SKIM/READ-ONLY verdict for the whole video. In a 2h37min podcast, some segments are WATCH (physical demos, emotional stories) and others are READ-ONLY (analytical monologue). A single verdict loses this information.

Secondary problem: update flow "Re-extract transcript" runs `50_assemble.py --transcript-only` which calls `finalize_transcript_only()` — this method does not call `_save_watch_guide()`. Only `finalize_full()` does. User must do "Full refresh" to get a watch guide.

## Goal

Each cleaning subagent produces cleaned text AND content analysis with per-chunk gate verdict. A synthesis step combines chunk analyses into headings + segment-level watch guide. No separate subskill, no 150KB guard, no re-reading the full transcript for watch guide.

## Architecture Context

Current pipeline B:
```
transcript_extract → (transcript_summarize | transcript_polish | comment_extract) → comment_summarize → watch_guide → assemble
```

Current transcript_polish steps:
```
Step 1: paragraph breaks (Sonnet, outputs line numbers → script inserts)
Step 2: clean artifacts (Sonnet per chunk, outputs cleaned text)
  33_split_for_cleaning.py → parallel cleaning subagents → 34_concat_cleaned.py
Step 3: AI headings (Sonnet reads full _transcript_cleaned.md, outputs _headings.json → script inserts)
```

Key code facts:
- `33_split_for_cleaning.py`: <80KB → returns `[original_path]` (no chunk files). >80KB → writes `{base}_chunk_001.md`, `{base}_chunk_002.md`, etc. Returns JSON `{"chunks": [...paths...]}`.
- `34_concat_cleaned.py`: concatenates cleaned chunks, deletes chunk files + cleaned variants via `cleanup_targets_for_chunk()` regex pattern `^(?P<prefix>.+_chunk_\d{3})(?P<cleaned>_cleaned)?\.md$`.
- `intermediate_files.py`: literal file lists per category, no glob patterns. `get_all_work_files()` aggregates all.
- `finalize_transcript_only()` (assembler:359): creates transcript file, cleans up transcript work files. Does NOT call `_save_watch_guide()`.
- `finalize_full()` (assembler:469): creates summary + transcript + comments + watch guide. Only place `_save_watch_guide()` is called.
- `find_existing_summary()` (assembler): finds final summary file by video ID pattern — filename is `YYYY-MM-DD - youtube - Title (ID).md`, does NOT contain word "summary".

### Key insight

MAX_OUTPUT_TOKENS (32k) is per Write call, not per subagent session. A chunk cleaning subagent can make multiple Write calls. Each chunk subagent produces both cleaned text and content analysis as separate files.

## Design

### New pipeline flow

```
Step 1: paragraph breaks (unchanged)
  ↓
33_split_for_cleaning.py → chunk list JSON (with global paragraph offsets)
  ↓
Step 2: per chunk subagent (parallel):
  - Write 1: cleaned chunk
  - Write 2: chunk analysis (topics with global paragraph numbers, per-chunk gate, watch signals)
  ↓
34_concat_cleaned.py → _transcript_cleaned.md (deletes chunk + cleaned files, keeps analysis files)
  ↓
Step 3: synthesis subagent:
  - Reads: chunk analyses (small), _chapters.json, _metadata.md, summary (if available)
  - Write 1: _headings.json
  - Write 2: _watch_guide.md
  ↓
35_insert_headings_from_json.py → _transcript.md
```

Pipeline B becomes:
```
transcript_extract → (transcript_summarize | transcript_polish | comment_extract) → comment_summarize → assemble
```

### Global paragraph offsets in split output

`33_split_for_cleaning.py` currently outputs `{"chunks": [path, ...]}`. Extend to include global paragraph offsets per chunk:

```json
{
  "chunks": [
    {"path": "/abs/path/chunk_001.md", "para_start": 1, "para_end": 20},
    {"path": "/abs/path/chunk_002.md", "para_start": 21, "para_end": 40},
    {"path": "/abs/path/chunk_003.md", "para_start": 41, "para_end": 58}
  ]
}
```

Short transcript (<80KB, no split): `{"chunks": [{"path": "/abs/path/original.md", "para_start": 1, "para_end": N}]}`.

The orchestrator (transcript_polish.md) passes `para_start` and `para_end` to each chunk cleaning subagent prompt so it can report topics with global paragraph numbers.

### Step 2: chunk analysis format

Each chunk subagent writes analysis alongside cleaned text. File naming:
- Chunked (>80KB): `${BASE_NAME}_chunk_NNN_analysis.md`
- Passthrough (<80KB): `${BASE_NAME}_analysis.md` (single file)

Analysis content:

```markdown
## Chunk NNN (paragraphs X-Y, [HH:MM:SS]-[HH:MM:SS])

### Gate: WATCH | SKIM | READ-ONLY
{1 sentence justification for this segment}

### Topics
- [paragraph X] Topic name — brief description
- [paragraph Z] Topic name — brief description

### Watch moments
- [HH:MM:SS] What happens — why watch > read

### Skip
- [HH:MM:SS]-[HH:MM:SS] Reason (banter, ads, repetition)
```

Paragraph numbers are GLOBAL (provided by orchestrator from split JSON). ~1-2KB per analysis.

### Step 3: synthesis subagent

Inputs:
- All analysis files (chunk or single)
- `_chapters.json` (if exists)
- `_metadata.md` (if exists)
- Summary context (resolved, see below)

Output 1 — `_headings.json`:
```json
[{"before_paragraph": 1, "heading": "### Topic name"}, ...]
```
`before_paragraph` values are global (from analysis topic lists). `35_insert_headings_from_json.py` uses these directly.

Output 2 — `_watch_guide.md`:

**Short video (1 chunk, uniform verdict):**
```
WATCH: Physical technique demonstrations require visual observation.

## Highlights
**[03:12](url)** Boss Combination — load-up deception only visible in motion
→ Boss Combination with Deception

## Read Instead
Three Categories of AI Exposure — taxonomy reads faster than spoken enumeration
→ Three Categories of AI Exposure

## Watch Route
14 min of 25: [03:12](…) → [08:45](…) → [15:30](…)
```

**Long video (multiple chunks, mixed verdicts):**
```
MIXED: 2h37min podcast. 28 min worth watching, rest reads better as summary.

## Segment Map
| Time | Verdict | What |
|------|---------|------|
| 00:00-12:00 | SKIP | Intro banter |
| 12:00-25:00 | READ-ONLY | Market analysis |
| 25:00-34:00 | WATCH | Physical demo of portfolio rebalancing game |
| 34:00-1:02:00 | READ-ONLY | Historical analysis |
| 1:02:00-1:15:00 | WATCH | Emotional story about 2008 crash |
| 1:15:00-2:10:00 | READ-ONLY | Technical deep dive |
| 2:10:00-2:25:00 | WATCH | Live calculation demo |
| 2:25:00-2:37:00 | SKIP | Outro, self-promotion |

## Highlights
**[25:12](url)** Portfolio rebalancing game — physical props, must see
→ Portfolio Rebalancing Game

**[1:02:30](url)** 2008 crash personal story — emotional delivery
→ The 2008 Experience

**[2:10:15](url)** Live DCF calculation — follows spreadsheet on screen
→ Discounted Cash Flow Walkthrough

## Watch Route
28 min: [25:12](…) → [1:02:30](…) → [2:10:15](…)
```

Top-level verdict rules:
- `WATCH:` — all/most chunks WATCH
- `SKIM:` — all/most chunks SKIM
- `READ-ONLY:` — all chunks READ-ONLY
- `MIXED:` — chunks have different verdicts

### Option B vs D signal

Both options B and D run `transcript_polish.md`. Watch guide should only be generated for option B.

Mechanism: SKILL.md creates a marker file `${BASE_NAME}_watch_guide_requested.flag` before calling `transcript_polish.md` for option B. Transcript_polish Step 3 checks for this flag — if present, synthesis produces `_watch_guide.md`. If absent (option D), synthesis produces only `_headings.json`.

Alternative considered: pass a parameter to transcript_polish.md. Rejected — subskills don't have a parameter mechanism, only files and environment.

### Summary file resolution

`transcript_summarize` and `transcript_polish` run concurrently in pipeline B. `_summary_tight.md` may not exist when Step 3 starts.

Resolution logic in transcript_polish.md Step 3 (bash before synthesis subagent):

```bash
python3 -c "
from pathlib import Path
import json, sys
sys.path.insert(0, '.')
from lib.assembler import Finalizer

d = Path('<output_directory>')
base = '${BASE_NAME}'
tight = d / f'{base}_summary_tight.md'
if tight.exists():
    print(json.dumps({'summary': str(tight)}))
    sys.exit(0)

# Find existing final summary file (re-extract scenario)
f = Finalizer()
video_id = base.replace('youtube_', '', 1)
existing = f.find_existing_summary(video_id, d)
if existing:
    print(json.dumps({'summary': str(existing)}))
    sys.exit(0)

print(json.dumps({'summary': None}))
"
```

Uses `Finalizer.find_existing_summary()` which already handles the non-obvious filename pattern. No duplicate glob logic.

Priority:
1. `_summary_tight.md` — available if transcript_summarize finished before Step 3
2. Existing final summary file on disk — available during re-extract
3. None — watch guide from chunk analyses + metadata only (PoC confirmed gate works without summary)

### Assembler changes

**1. `_save_watch_guide()` verdict parsing:** Add `MIXED:` to accepted verdicts alongside `WATCH:` and `SKIM:`. All three produce a watch guide file.

**2. `finalize_transcript_only()`:** Add `_save_watch_guide()` call after transcript file creation. Identical pattern to `finalize_full()`. This enables watch guide during "Re-extract transcript".

**3. `cleanup_work_files()`:** Currently deletes literal file paths from lists. Analysis files need cleanup. Two approaches:
- **A.** Add explicit analysis filenames to `get_transcript_work_files()`: `f"{base_name}_analysis.md"` (passthrough) + `f"{base_name}_chunk_{i:03d}_analysis.md"` for i in 1..MAX_CHUNKS. Problem: MAX_CHUNKS unknown.
- **B.** Add a glob-based cleanup step in assembler: after literal cleanup, also `glob(f"{base_name}_chunk_*_analysis.md")` and delete matches.

Decision: **B.** Add a `cleanup_analysis_files()` method in assembler that globs and deletes. Called from both `finalize_full()` and `finalize_transcript_only()`. Also add `f"{base_name}_analysis.md"` to `get_transcript_work_files()` for the passthrough case.

Also add `f"{base_name}_watch_guide_requested.flag"` to `get_all_work_files()` for cleanup.

### Cross-links

Heading names come from `_headings.json` which the synthesis subagent just produced. `→ ` lines use exact heading names from the JSON. Assembler cross-link processing unchanged.

### Update flow changes

`update_flow.md` "Re-extract transcript":
- Still backup + delete old watch guide before re-extract
- Remove "Full refresh needed to regenerate" message
- SKILL.md always creates `_watch_guide_requested.flag` before calling transcript_polish for re-extract (user re-extracting transcript likely wants watch guide if summary exists)
- `finalize_transcript_only()` now calls `_save_watch_guide()`

### `34_concat_cleaned.py` changes

Current `cleanup_targets_for_chunk()` regex matches `_chunk_NNN.md` and `_chunk_NNN_cleaned.md`. Analysis files (`_chunk_NNN_analysis.md`) do NOT match this pattern because the regex requires the name to end after optional `_cleaned`. Analysis files persist until assembler cleanup. No change needed to this script.

Verification: regex `^(?P<prefix>.+_chunk_\d{3})(?P<cleaned>_cleaned)?\.md$`
- `youtube_xyz_chunk_001.md` → matches (deleted)
- `youtube_xyz_chunk_001_cleaned.md` → matches (deleted)
- `youtube_xyz_chunk_001_analysis.md` → does NOT match (kept)

## Tasks

- [x] 1. Modify `scripts/33_split_for_cleaning.py`:
  - Output JSON includes `para_start` and `para_end` per chunk
  - Passthrough (<80KB): count paragraphs, output `{"chunks": [{"path": ..., "para_start": 1, "para_end": N}]}`
  - Tests: verify JSON schema, global paragraph offsets correct, passthrough includes counts
- [x] 2. Modify `subskills/transcript_polish.md` Step 2 prompt:
  - Pass `para_start`/`para_end` from split JSON to each chunk subagent
  - Extend prompt: two Write calls (cleaned chunk + analysis with global paragraph numbers)
  - Analysis naming: `_chunk_NNN_analysis.md` (chunked) or `_analysis.md` (passthrough)
- [x] 3. Modify `subskills/transcript_polish.md` Step 3:
  - Replace full-transcript heading generation with synthesis subagent
  - Reads analysis files + chapters + metadata + summary (resolved)
  - Check `_watch_guide_requested.flag` — if present, two Write calls (`_headings.json` + `_watch_guide.md`). If absent, one Write (`_headings.json` only).
  - Summary resolution using `Finalizer.find_existing_summary()`
  - Short video: single verdict. Long video with mixed chunks: MIXED verdict + segment map.
- [x] 4. Add `_watch_guide_requested.flag` creation in `SKILL.md`:
  - Pipeline B: create flag before `transcript_polish.md`
  - Option D: no flag
  - Update flow "Re-extract transcript": always create flag (user re-extracting transcript likely wants watch guide if summary exists)
- [x] 5. Update `lib/assembler.py`:
  - `_save_watch_guide()`: accept `MIXED:` verdict
  - `finalize_transcript_only()`: add `_save_watch_guide()` call
  - New `cleanup_analysis_files(base_name, output_dir)`: glob `{base_name}_chunk_*_analysis.md` + delete. Called from `finalize_full()` and `finalize_transcript_only()`.
- [x] 6. Update `lib/intermediate_files.py`:
  - Add `f"{base_name}_analysis.md"` to `get_transcript_work_files()`
  - Add `f"{base_name}_watch_guide_requested.flag"` to `get_all_work_files()` AND `get_transcript_work_files()` (flag must be cleaned in both full and transcript-only paths)
  - Add `f"{base_name}_watch_guide.md"` to `get_transcript_work_files()` (prevent stale intermediate in transcript-only flow)
- [x] 7. Modify `SKILL.md`: remove `→ watch_guide.md` from pipeline B
- [x] 8. Delete `subskills/watch_guide.md`
- [x] 9. Modify `subskills/update_flow.md`:
  - Remove "Full refresh needed to regenerate" message
  - Add flag creation (always, not conditional on old watch guide existence)
- [x] 10. Update `tests/youtube-to-markdown/test_watch_guide.py`:
  - Test MIXED verdict accepted by assembler
  - Test `finalize_transcript_only()` calls `_save_watch_guide()`
  - Adjust tests referencing watch_guide subskill
- [x] 11. New tests for `33_split_for_cleaning.py`:
  - JSON output includes para_start/para_end
  - Passthrough includes paragraph count
- [x] 12. New tests for assembler `cleanup_analysis_files()`:
  - Globs and deletes chunk analysis files
  - Preserves non-analysis files
- [>] 13. Integration test: pipeline B on long transcript (>150KB) — verify MIXED watch guide with segment map (deferred to ORC)
- [>] 14. Integration test: short transcript (<80KB) — verify single verdict watch guide (no regression) (deferred to ORC)
- [>] 15. Integration test: "Re-extract transcript" with existing summary — verify watch guide generated (deferred to ORC)
- [>] 16. Integration test: option D — verify NO watch guide generated (deferred to ORC)
- [>] 17. Quality check: compare headings from chunk analyses vs previous full-transcript headings on test corpus (deferred to ORC)

## Acceptance Criteria

- [ ] Watch guide generated for transcripts >150KB (no guard)
- [ ] Long videos: MIXED verdict with per-segment map when chunks have different gate values
- [ ] Short videos: single WATCH/SKIM/READ-ONLY verdict (backward compatible)
- [ ] Watch guide generated during "Re-extract transcript" when summary file exists on disk
- [ ] Option D: no watch guide generated (flag absent)
- [ ] Per-chunk gate verdicts in analysis files with global paragraph numbers
- [ ] `33_split_for_cleaning.py` outputs para_start/para_end per chunk
- [ ] Heading quality: task 17 produces side-by-side comparison on 2 test videos (fi + en). Pass if ≥80% of headings match same paragraph ±2 positions. If <80% → follow-up plan for synthesis fallback.
- [ ] Assembler accepts MIXED verdict, produces watch guide file
- [ ] `finalize_transcript_only()` calls `_save_watch_guide()`
- [ ] Analysis files cleaned up by assembler (glob-based)
- [ ] Pipeline B has one fewer sequential step
- [ ] Existing assembler unit tests pass (16 tests)
- [ ] `watch_guide.md` subskill removed

## Scope boundaries

**In scope:** Pipeline B watch guide integration, re-extract transcript watch guide, MIXED verdict format, assembler changes.

**Out of scope:**
- Option D watch guide (excluded in original plan, same exclusion)
- Option A/C watch guide (no polished transcript)
- Summary from chunk analyses (future — format routing needs adaptation)
- Heading quality fallback (if task 17 shows degradation, a follow-up plan reads `_transcript_cleaned.md` in synthesis)

## Risks

| Risk | Mitigation |
|------|-----------|
| Heading quality degrades without full transcript | Chunk analyses have global paragraph numbers + topic shifts. Task 17 measures quality. If insufficient → follow-up plan. |
| Per-chunk gate verdicts inconsistent | Synthesis subagent sees all chunk verdicts together, smooths boundaries. |
| Chunk boundary splits a watch-worthy moment | Adjacent chunks both report the moment. Synthesis merges overlapping time ranges. |
| `_summary_tight.md` not ready when Step 3 runs | Summary resolution falls through to existing file or none. Gate still works without summary. |
| Analysis adds cost to Step 2 | ~1-2KB extra Write per chunk. Negligible vs 30KB cleaned text. |
| `34_concat_cleaned.py` accidentally deletes analysis files | Verified: regex `_chunk_\d{3}(_cleaned)?\.md$` does NOT match `_analysis.md`. |

## Reflection

### What went well

- Prompt iteration across A-H variants on real videos improved the watch-guide output quality and reduced hallucinated structure.
- Heatmap extraction from `yt-dlp` provided a concrete replay-intensity signal that improved highlight selection in synthesis.

### What changed from plan

- `_save_watch_guide()` contract was simplified: verdict-line parsing and transcript cross-link rewriting were removed; assembler now saves plain markdown watch guide content when non-empty.
- Chunk analysis generation was consolidated into Step 2 cleaning subagents (same pass as cleaning) instead of an additional separate analysis phase.
- Split output now carries paragraph range metadata per chunk (`para_start`/`para_end`) for global-position synthesis logic.

### Lessons learned

- Synthesis prompt quality had larger impact on final watch-guide usefulness than additional gate-control logic in assembler.
- Prompt evaluation needs diverse video types (talking head, demo-heavy, long podcast, mixed-format) early; narrow test sets hid quality regressions.
