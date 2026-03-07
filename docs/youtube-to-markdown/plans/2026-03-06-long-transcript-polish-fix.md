# Long Transcript Polish Pipeline Fix

## Problem

Polish pipeline fails on long transcripts (>~80 KB). Research completed in `2026-02-24-long-transcript-chunking-research.md`.

**Root causes:**
- Step 2: Haiku silently fails (copies input unchanged). Sonnet single-pass fails on English (MAX_OUTPUT_TOKENS).
- Step 3: Sonnet full-rewrite exceeds MAX_OUTPUT_TOKENS (32k) on any long transcript.

## Solution Summary

| Step | Current | New |
|------|---------|-----|
| Step 2 | Haiku, single-pass | Sonnet, chunked if >80 KB |
| Step 3 | Sonnet full-rewrite | Sonnet metadata JSON → script inserts (always AI headings) |

**Step 3 decision:** Always use AI-generated headings, even when author chapters exist. Rationale:
- AI headings are more granular (26 vs 21 on Lex Fridman test) and sometimes better named
- One code path instead of branching on chaptered/non-chaptered
- chapters.json is still provided to the Sonnet prompt as context (helps anchor timing)
- Cost: +30-50k tokens (~25-35% overhead on top of Step 2's ~140k). Acceptable.
- `32_insert_headings.py` (scripted) kept as fallback — can be used if cost is a concern

## Architecture

### New pipeline flow

```
Step 1: paragraph breaks (unchanged — Sonnet, outputs line numbers)
  ↓
31_format_transcript.py (unchanged)
  ↓
33_split_for_cleaning.py → check size
  ├─ ≤80 KB: single chunk list (1 file path)
  └─ >80 KB: split into ~20-paragraph chunks → chunk list (N file paths)
  ↓
Step 2: clean artifacts (Sonnet, one subagent per chunk, parallel)
  ↓
34_concat_cleaned.py → merge chunks, delete chunk files → _transcript_cleaned.md
  ↓
Step 3: Sonnet metadata JSON → 35_insert_headings_from_json.py
  (chapters.json provided as optional context to improve heading placement)
  ↓
_transcript.md (final)
```

### Files to create

1. **`scripts/33_split_for_cleaning.py`**
   - Input: `_transcript_paragraphs.md`, output directory
   - Output: JSON to stdout with chunk file paths
   - Logic: if file ≤80 KB → `{"chunks": ["<full_path>/_transcript_paragraphs.md"]}` (no split)
   - If >80 KB → split by `\n\n` into paragraphs, group ~20 per chunk (max ~40 KB each), write `${BASE_NAME}_chunk_001.md`, `${BASE_NAME}_chunk_002.md`, etc. → `{"chunks": ["<full_path>/${BASE_NAME}_chunk_001.md", ...]}`
   - All paths in output JSON are absolute

2. **`scripts/34_concat_cleaned.py`**
   - Input: list of cleaned chunk file paths (argv), output path (last argv)
   - Output: concatenated file
   - Read each, join with `\n\n`, write to output
   - **Cleanup:** delete input chunk files and their cleaned counterparts after successful concatenation

3. **`scripts/35_insert_headings_from_json.py`**
   - Input: `_transcript_cleaned.md`, headings JSON file, output path
   - JSON format: `[{"before_paragraph": 3, "heading": "### Topic name"}, ...]`
   - Logic: split transcript by `\n\n`, insert heading before paragraph N (1-indexed), write output
   - **Validation:** reject `before_paragraph` values outside 1..paragraph_count range, log warning and skip

### Files to modify

4. **`subskills/transcript_polish.md`** — rewrite Steps 2 and 3:

#### Step 2 — chunked cleaning

```
bash: python3 ./scripts/33_split_for_cleaning.py "<output_directory>/${BASE_NAME}_transcript_paragraphs.md" "<output_directory>"
```

Read stdout JSON. For each chunk path in `chunks` array, launch a parallel task_tool:
- subagent_type: "general-purpose"
- model: "sonnet"
- run_in_background: true (for parallel execution when multiple chunks)
- prompt:

```
Read {chunk_path} and clean speech artifacts.

Tasks:
- Remove fillers (um, uh, like, you know)
- Fix transcription errors
- Add proper punctuation
- Reduce or add implicit words to improve flow
- Preserve natural voice and tone
- Keep timestamps at end of paragraphs
- IMPORTANT: Do not merge, split, or reorder paragraphs. Preserve the exact paragraph count.

ACTION REQUIRED: Use the Write tool NOW to save output to {chunk_path_cleaned}. Do not ask for confirmation.
Do not output text during execution - only make tool calls.
Your final message must be ONLY one of:
  clean: wrote {filename}
  clean: FAIL - {what went wrong}
```

Wait for all cleaning subagents to complete. If a chunk fails, retry once.

```
bash: python3 ./scripts/34_concat_cleaned.py {chunk_1_cleaned} ... {chunk_N_cleaned} "<output_directory>/${BASE_NAME}_transcript_cleaned.md"
```

#### Step 3 — AI headings

Launch task_tool:
- subagent_type: "general-purpose"
- model: "sonnet"
- prompt:

```
INPUT: <output_directory>/${BASE_NAME}_transcript_cleaned.md
CHAPTERS: <output_directory>/${BASE_NAME}_chapters.json
OUTPUT: <output_directory>/${BASE_NAME}_headings.json

Read INPUT. Paragraphs are separated by blank lines. Number them starting from 1.

If CHAPTERS file exists and contains chapters, use them as context to anchor topic boundaries. Generate more granular headings than the chapter titles.

If no chapters, identify topic boundaries from content alone.

Target: ~1 heading per 5-10 minutes of content. Use 3-6 word heading titles.

Output ONLY a valid JSON array to OUTPUT:
[{"before_paragraph": 1, "heading": "### Topic name"}, ...]

ACTION REQUIRED: Use the Write tool NOW to save output to OUTPUT file. Do not ask for confirmation.
Do not output text during execution - only make tool calls.
Your final message must be ONLY one of:
  headings: wrote ${BASE_NAME}_headings.json
  headings: FAIL - {what went wrong}
```

Then:
```
bash: python3 ./scripts/35_insert_headings_from_json.py "<output_directory>/${BASE_NAME}_transcript_cleaned.md" "<output_directory>/${BASE_NAME}_headings.json" "<output_directory>/${BASE_NAME}_transcript.md"
```

5. **`lib/intermediate_files.py`** — add `_headings.json` to `get_transcript_work_files()`:
   - Add `f"{base_name}_headings.json"` to the literal file list
   - Chunk files (`_chunk_NNN.md`, `_chunk_NNN_cleaned.md`) are NOT registered here — `34_concat_cleaned.py` deletes them after successful concatenation (cleanup is in-script, not in assembler)

### Files to keep (no changes)

- **`scripts/32_insert_headings.py`** — kept as scripted fallback. Not used in default pipeline.
- **`scripts/31_format_transcript.py`** — unchanged.

## Implementation Tasks

- [x] 1. Create `scripts/33_split_for_cleaning.py`
  - Split by `\n\n`, count paragraphs, group by ~20 paragraphs or ~40 KB max
  - Output JSON with absolute chunk paths to stdout
  - Handle edge case: ≤80 KB → no split, return original file path
  - Tests (pytest): <80 KB passthrough, >80 KB split, paragraph boundary integrity, chunk size cap

- [x] 2. Create `scripts/34_concat_cleaned.py`
  - Argv: chunk files... output_file
  - Read each, join with `\n\n`, write output
  - Delete input chunk files and their cleaned counterparts after successful write
  - Verify: no duplicate newlines at boundaries
  - Tests (pytest): single chunk passthrough, multiple chunks, cleanup verification

- [x] 3. Create `scripts/35_insert_headings_from_json.py`
  - Read transcript + headings JSON, insert `### heading` before paragraph N (1-indexed)
  - Validate: skip out-of-range paragraph numbers with warning to stderr
  - Tests (pytest): basic insertion, multiple headings at same paragraph, out-of-range handling, empty JSON

- [x] 4. Rewrite `subskills/transcript_polish.md`
  - Step 2: split → parallel clean → concat
  - Step 3: always AI headings via metadata JSON → script inserts
  - Keep Step 1 unchanged
  - Cleaning prompt: explicit "preserve paragraph count" rule
  - File naming: `${BASE_NAME}_chunk_NNN.md`, cleaned: `${BASE_NAME}_chunk_NNN_cleaned.md`

- [x] 5. Update `lib/intermediate_files.py`
  - Add `_headings.json` to `get_transcript_work_files()` (literal entry, not glob)
  - Chunk files are NOT registered here — cleaned up by `34_concat_cleaned.py`

- [x] 6. Integration test on Finnish transcript (peliteoreetikko, 170 KB)
  - 5 chunks (35, 36, 40, 38, 22 KB), all under 40 KB cap
  - Output: 156 KB cleaned (9% reduction), 39 AI headings in Finnish
  - Headings cover full arc: poker AI, game theory, nuclear strategy, crypto, AI ethics
  - Chunk files cleaned up after concat

- [x] 7. Integration test on English transcript (Lex Fridman OpenClaw, 169 KB)
  - 5 chunks (39, 37, 39, 38, 16 KB), all under 40 KB cap
  - Output: 151 KB cleaned (11% reduction), 31 AI headings
  - Headings cover full arc: prototype story, viral growth, security, architecture, career advice
  - Chunk files cleaned up after concat

- [x] 8. Edge case test: short transcript (50 KB, under 80 KB threshold)
  - Passthrough confirmed: no chunk files created, original returned as single-element array
  - Full pipeline ran: cleaning + concat (single file) + headings + insertion
  - 6 valid headings inserted, 2 out-of-range correctly skipped with warnings
  - Script handled truncated transcript gracefully

## Acceptance Criteria

- [x] Finnish 170 KB transcript: cleaned with artifacts removed, 39 AI headings placed, no errors
- [x] English 169 KB transcript: cleaned with fillers removed, 31 AI headings placed, no errors
- [x] Short transcript (50 KB): works without chunking, full pipeline completes, no regression
- [x] AI heading quality: covers major topics, ~1 heading per 2-3 paragraphs (good granularity)
- [x] Paragraph count preserved: cleaning subagents maintained paragraph structure
- [x] No intermediate chunk files left after pipeline completes (verified by ls)
- [>] Token usage: not measured precisely in integration tests — subagent token tracking not available in this mode. Research baselines suggest ~140-170k total per long transcript.

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| Sonnet subagent writes to wrong path | Chunk paths in prompt are absolute, verified by split script |
| Chunk boundary splits mid-sentence | Split on paragraph boundaries (double newline), not byte count |
| AI heading quality varies | Provide chapters.json as context when available; ~1 per 5-10 min target |
| Parallel subagent failures | ORC checks each result; retry failed chunks once. Fallback: run sequentially |
| 40 KB chunk still too large | Script caps at 40 KB, splits further if needed |
| Step 2 merges/splits paragraphs | Prompt says "preserve paragraph count"; 34_concat validates count before/after |
| Step 3 Sonnet reads full cleaned transcript | Step 3 only outputs small JSON (~1 KB), MAX_OUTPUT_TOKENS not a risk |
| Invalid heading JSON from Sonnet | 35_insert_headings validates JSON; out-of-range indices skipped with warning |

## Cost Impact

| Scenario | Before (broken) | After |
|----------|--------|-------|
| Short transcript (<80 KB) | Haiku ~20k + Sonnet Step 3 ~50k | Sonnet ~50k + Sonnet headings ~30k = **~80k** |
| Long Finnish (170 KB) | Haiku 56k + Sonnet Step 3 (fail) | Sonnet ~114k + Sonnet headings ~50k = **~164k** |
| Long English (169 KB) | Haiku (fail) + Sonnet Step 3 (fail) | Sonnet ~140k + Sonnet headings ~30k = **~170k** |

Before: broken, producing wrong or no output. After: correct output, ~80-170k tokens total.

## Reflection

### What went well

- Research phase (RQ1-RQ6) identified root causes precisely — no surprises during implementation
- Chunking strategy (paragraph-boundary splits, ~20 paragraphs / ~40 KB cap) worked on both languages without tuning
- AI-generated headings produced better results than expected — 31-39 headings per long transcript with good topic coverage
- Script decomposition (split → clean → concat → headings → insert) kept each piece testable and simple
- Parallel cleaning subagents completed all chunks successfully on first attempt for both transcripts

### What changed from plan

- No changes. Implementation matched plan exactly. All 8 tasks completed as specified.
- Token usage acceptance criterion deferred — subagent token tracking not available in integration test mode

### Lessons learned

- `CLAUDE_CODE_MAX_OUTPUT_TOKENS` (32k) is the real constraint, not model capability — chunking output size is the fix, not switching models
- Paragraph-boundary chunking is robust because transcripts already have natural break points from Step 1
- "Always AI headings" simplification eliminated a branching code path with no quality loss — chapters.json as context input is sufficient
- Codex sandbox git limitations required workaround (rename `.git`) — document this for future delegated implementations
- `normalize_chunk_content()` (strip boundary newlines) prevents `\n\n\n` at chunk joins — a subtle but important detail
