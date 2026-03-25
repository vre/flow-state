# youtube-to-markdown: deterministic paragraph breaks

## Problem

Step 1 of transcript_polish delegates paragraph break detection to an LLM subagent. The agent must identify exact line numbers in 4000+ line files. LLMs can't reliably count lines at this scale, so they improvise `python3 -c` scripts (100+ lines, 100K+ tokens, security warnings). Explicit Steps instructions don't prevent this — the agent correctly recognizes it needs deterministic line counting.

## Goal

Replace LLM paragraph break detection (Step 1 only) with a deterministic script. Steps 2–3 (speech cleanup, analysis, headings, watch guide) remain LLM-driven.

## Design

New script `37_paragraph_breaks.py` (or `run.py paragraph-breaks` subcmd):

Input: `transcript_dedup.md` (has timestamps) + `chapters.json`
Output: `transcript_paragraphs.txt` (comma-separated line numbers)

**Critical: line counting uses `transcript_dedup.md`** — not `_no_timestamps.txt` which is safety-wrapped with XML tags and warning lines. `31_format_transcript.py` also reads dedup.md, so line numbers must match that file.

Algorithm:
1. Parse chapters.json → list of chapter start times (seconds)
2. Read `transcript_dedup.md` → parse timestamps from each line
3. Place mandatory breaks at chapter boundaries: first line whose timestamp ≥ chapter start time. If no exact match within 5s tolerance, use nearest following line.
4. Between chapters, walk lines and break at sentence endings (`.?!`) nearest ~500 char target
5. If no chapters.json or empty: break on sentence endings only (~500 char target)
6. Output break point line numbers

### What changes in transcript_polish.md

Step 1 becomes:
```bash
python3 ./scripts/run.py paragraph-breaks "<output_directory>/${BASE_NAME}_transcript_dedup.md" "<output_directory>/${BASE_NAME}_chapters.json" "<output_directory>/${BASE_NAME}_transcript_paragraphs.txt"
```
```bash
python3 ./scripts/run.py format-transcript "<output_directory>/${BASE_NAME}_transcript_dedup.md" "<output_directory>/${BASE_NAME}_transcript_paragraphs.txt" "<output_directory>/${BASE_NAME}_transcript_paragraphs.md"
```

No task_tool, no subagent. Pure script.

## Acceptance Criteria

- [x] AC1: Break points land on chapter boundaries (first line with timestamp ≥ chapter start)
- [x] AC2: Between chapters, breaks at sentence endings nearest ~500 char target
- [x] AC3: No LLM subagent in transcript_polish.md Step 1
- [x] AC4: `run.py paragraph-breaks` subcmd registered
- [x] AC5: Tests: with chapters (exact match + non-exact), without chapters, short transcript, empty chapters, empty input
- [x] AC6: Output line numbers compatible with `31_format_transcript.py` (uses same dedup.md file)

## Tasks

- [x] 1. Write tests for paragraph break algorithm (TDD)
- [x] 2. Implement `37_paragraph_breaks.py` — chapter matching + sentence-boundary breaks
- [x] 3. Add `paragraph-breaks` to `run.py` dispatcher
- [+] 3a. Make `run.py` dispatch through `sys.executable` instead of hardcoded `python3` so subcommands use the active project interpreter
- [x] 4. Update `transcript_polish.md` Step 1 — remove task_tool, use script
- [>] 5. Verify: full option B/D extraction produces correct paragraphs - deferred; Step 1 + formatter path verified locally via `run.py paragraph-breaks` and `run.py format-transcript`, but full extraction requires network/video access not available in this sandbox

## Reflection

<!-- Written post-implementation by IMP -->
