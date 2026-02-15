# Plan: Constrained Subagent Output

## Situation

The youtube-to-markdown coordinator dispatches 2-7 Task subagents per video (depending on option: A=4, B=7, C=2, D=3). TaskOutput returns the agent's final text message to the coordinator's context. Unconstrained subagents produce verbose final messages — intermediate reasoning, confirmations, content echoing — inflating TaskOutput to ~30K chars per call (measured in session f3ce1cae, 10-video batch). Per-video context growth: ~44K tokens. Compaction every 2-3 videos.

The subagents already write results to files. The coordinator only needs a "done" or "failed" signal.

## Root Cause (verified by testing)

TaskOutput returns **only the agent's final text message**, not the full conversation log. The ~30K per call was from unconstrained agents producing verbose text — not from conversation log leakage.

Test results (2026-02-15):

| Model | Case | TaskOutput content | Chars |
|---|---|---|---|
| Sonnet | success | `summarize: wrote test_summary.md` | 32 |
| Sonnet | failure | `summarize: FAIL - File does not exist at ...` | 120 |
| Haiku | success | `summarize: wrote test_summary_haiku.md` | 40 |
| Haiku | failure | `summarize: FAIL - File does not exist at ...` | 128 |

Additional findings:
- Background agents cannot use the Write tool ("prompts unavailable" auto-deny) — not needed for the fix but rules out background-Task approaches
- Background task `<task-notification>` contains only `<result>{final message}</result>` (~250 chars total) — no conversation log leak
- Constrained output instruction works reliably with both Sonnet and Haiku

## Intent

Add a constrained output instruction to each subagent prompt. Subagents stay silent during execution and produce a one-line status as their final message. No architectural changes.

## Goal

Per-video coordinator context growth from subagent work: <2K tokens (currently ~44K). Process 10+ videos without compaction.

## Constraints

- Scripts unchanged
- Tests unchanged
- Model diversity preserved — Sonnet/Haiku assignments per step unchanged
- All output options (A-D) supported
- No new files, no new runtime artifacts
- Subskill files remain usable by `update_flow.md`

## Design

### The fix: constrained output instruction

Append to each subagent prompt in the subskill `.md` files. Placement:
- Steps with `ACTION REQUIRED` line: append after it
- Steps without `ACTION REQUIRED` (transcript_polish Step 1): insert before the closing ` ``` ` of the prompt block

The instruction:

```
Do not output text during execution — only make tool calls.
Your final message must be ONLY one of:
  {step}: wrote {output_file}
  {step}: FAIL - {what went wrong}
```

### Before / After

```
BEFORE (transcript_summarize Step 1):
  Subagent reads transcript, reasons about it, writes summary, says:
  "I've analyzed the transcript and written a comprehensive summary
   covering the main topics including..."
  → TaskOutput: verbose text in coordinator context

AFTER:
  Subagent reads transcript, writes summary, says:
  "summarize: wrote _summary.md"
  → TaskOutput: ~40 chars in coordinator context
```

Per video, Option A (4 Task calls): ~600 chars in coordinator (vs ~120K before).

### Task count per option

| Option | Subskills used | Task calls |
|---|---|---|
| A: Summary + Comments | transcript_summarize (2) + comment_summarize (2) | 4 |
| B: Summary + Comments + Transcript | transcript_summarize (2) + transcript_polish (3) + comment_summarize (2) | 7 |
| C: Summary Only | transcript_summarize (2) | 2 |
| D: Formatted Transcript Only | transcript_polish (3) | 3 |

### Affected Task prompts with exact insertion anchors

All paths relative to repo root (`youtube-to-markdown/subskills/`).

| File | Step | Anchor (append after) | Step label | Model |
|---|---|---|---|---|
| `youtube-to-markdown/subskills/transcript_summarize.md` | 1 | `ACTION REQUIRED: Use the Write tool NOW to save output to OUTPUT file. Do not ask for confirmation.` | `summarize` | Sonnet |
| `youtube-to-markdown/subskills/transcript_summarize.md` | 2 | `ACTION REQUIRED: Use the Write tool NOW to save output to OUTPUT file. Do not ask for confirmation.` | `tighten` | Sonnet |
| `youtube-to-markdown/subskills/comment_summarize.md` | 1 | `ACTION REQUIRED: Use the Write tool NOW to save output to OUTPUT file.` | `insights` | Sonnet |
| `youtube-to-markdown/subskills/comment_summarize.md` | 2 | `ACTION REQUIRED: Use the Write tool NOW to save output to OUTPUT file.` | `tighten` | Sonnet |
| `youtube-to-markdown/subskills/transcript_polish.md` | 1 | insert before closing ` ``` ` of prompt block (line 24) | `paragraphs` | Sonnet |
| `youtube-to-markdown/subskills/transcript_polish.md` | 2 | `ACTION REQUIRED: Use the Write tool NOW to save output to <output_directory>/${BASE_NAME}_transcript_cleaned.md. Do not ask for confirmation.` | `clean` | **Haiku** |
| `youtube-to-markdown/subskills/transcript_polish.md` | 3 | `ACTION REQUIRED: Use the Write tool NOW to save output to OUTPUT file. Do not ask for confirmation.` | `headings` | Sonnet |

### Instruction format (avoid Haiku literal-copying)

Haiku copies instruction formatting literally (included `Success:` prefix from dash-list format in testing). Use plain indented format without labels:

```
Do not output text during execution — only make tool calls.
Your final message must be ONLY one of:
  {step}: wrote {output_file}
  {step}: FAIL - {what went wrong}
```

## Tasks

### 1. Modify `youtube-to-markdown/subskills/transcript_summarize.md`

Append constrained output instruction to both Task prompts (Steps 1 and 2), inside the prompt ``` block, after the `ACTION REQUIRED` line.

Step 1 step label: `summarize`, output file: `${BASE_NAME}_summary.md`
Step 2 step label: `tighten`, output file: `${BASE_NAME}_summary_tight.md`
Status: [x] done

### 2. Modify `youtube-to-markdown/subskills/comment_summarize.md`

Append constrained output instruction to both Task prompts (Steps 1 and 2), inside the prompt ``` block, after the `ACTION REQUIRED` line.

Step 1 step label: `insights`, output file: `${BASE_NAME}_comment_insights.md`
Step 2 step label: `tighten`, output file: `${BASE_NAME}_comment_insights_tight.md`
Status: [x] done

### 3. Modify `youtube-to-markdown/subskills/transcript_polish.md`

Append constrained output instruction to all three Task prompts (Steps 1, 2, and 3).

Step 1: insert before closing ` ``` ` of prompt block. Step label: `paragraphs`, output file: `${BASE_NAME}_transcript_paragraphs.txt`
Step 2: after `ACTION REQUIRED`. Step label: `clean`, output file: `${BASE_NAME}_transcript_cleaned.md`
Step 3: after `ACTION REQUIRED`. Step label: `headings`, output file: `${BASE_NAME}_transcript.md`
Status: [x] done

## Acceptance Criteria

- [x] All 7 Task prompts in 3 subskill files include constrained output instruction
- [x] Model diversity preserved (transcript_polish Step 2 stays Haiku)
- [x] All existing tests pass (scripts unchanged)
- [x] Manual: extract 1 video option A, compare output against unconstrained baseline (same structure, same key points, no missing sections)
- [x] Manual: extract 3+ videos sequentially, verify no compaction (method: `list_recent_sessions` → check session token count stays under 170K)
- [x] Manual: run one `update_flow.md` scenario ("Re-extract transcript" on existing video), verify it works unchanged
- [x] Measure: capture TaskOutput char count for one constrained extraction, verify <200 chars per Task call

## Implementation Notes

- [+] `docs/youtube-to-markdown/plans/2026-02-15-fire-and-forget-subagents.md` was untracked on `main`; copied into worktree so implementation branch is self-contained.
- [+] `uv sync` setup completed for all pyproject directories except `youtube-to-markdown/`, which fails with a pre-existing Hatch packaging configuration error unrelated to this prompt-only change.

## Verification

```bash
# Both test suites (scripts unchanged)
python3 -m pytest tests/youtube-to-markdown/ -v
python3 -m pytest youtube-to-markdown/tests/ -v

# Manual: single video option A, compare quality
# 1. Extract with constraint → /tmp/claude/test-constrained/
# 2. Compare against existing extraction from same video
# Check: same content type, same sections, same key points

# Manual: 3+ videos, check context
# After extraction, use historian: list_recent_sessions → session token total < 170K

# Manual: update flow regression
# Re-extract transcript on video already in /tmp/claude/test-constrained/

# Measure: TaskOutput size
# During manual test, note TaskOutput content length in historian session detail
```

## Risks

1. **Subagent ignores constraint**: Agent might still produce intermediate text despite instruction. Mitigation: tested with both Sonnet and Haiku — both comply. Monitor first batch extraction.
2. **Error messages too terse**: FAIL line might not give enough detail. Mitigation: instruction says `{what went wrong}` — agent includes relevant context (tested: includes file path).
3. **Reasoning quality degradation**: "Do not output text during execution" suppresses all text blocks, including intermediate reasoning. Could reduce summarization quality. Mitigation: acceptance test compares against unconstrained baseline. If quality degrades → new plan to find the right balance (out of scope for this plan).
4. **Unconstrained baseline not measured**: The ~30K figure comes from session analysis aggregate, not individual agent measurement. The fix works regardless (tested), but the reduction factor is approximate. Mitigation: measure actual TaskOutput size before and after during manual testing.

## Reflection

- What went well: Prompt-only change delivered the intended behavior with minimal risk; all seven prompts were updated with exact status-line contracts and zero script changes.
- What changed from plan: The approved plan file was untracked on `main`, so it had to be copied into the implementation worktree before progress tracking and final reflection updates.
- Lessons learned: For prompt-only optimizations, include an explicit static verification step (count/grep for inserted blocks) plus dual-suite test execution, and keep manual context-token verification as a hard release gate.
