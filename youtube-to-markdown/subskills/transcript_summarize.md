# Transcript Summarize Module

Creates tight summary from transcript.

Before calling Step 1: compute transcript file size in bytes (`wc -c` on the `_transcript_no_timestamps.txt` file) and substitute into TRANSCRIPT_BYTES in both Step 1 and Step 2 prompts.

## Step 1: Summarize transcript

task_tool:
- subagent_type: "general-purpose"
- model: "sonnet"
- prompt:
```
INPUT: <output_directory>/${BASE_NAME}_transcript_no_timestamps.txt
OUTPUT: <output_directory>/${BASE_NAME}_summary.md
TRANSCRIPT_BYTES: <size of transcript file in bytes>
ROUTING: ./summary_formats.md
FORMATS_DIR: ../formats/

1. Read ROUTING file. Note the length budget table (section 3) — it sets a hard ceiling based on TRANSCRIPT_BYTES.

2. Classify content type per ROUTING section 1. Key rule: single speaker opinions/complaints → TIPS, not INTERVIEW.

3. Check length budget (ROUTING section 3). If transcript < 5000 bytes, skip format template entirely — use flat bullets.

4. If format applies: resolve format file from routing table (section 2). Read it.

5. Analyze content structure:
   - Identify meaningful content units (topic shifts, argument structure, narrative breaks)
   - If single continuous topic and format allows headerless output (TIPS), omit content unit headers
   - Skip ads, sponsors, self-promotion
   - Merge content spanning ad breaks if thematically connected

6. Produce summary applying length budget + cross-cutting rules + format-specific rules. Verify output bytes < max ratio × TRANSCRIPT_BYTES before writing.


ACTION REQUIRED: Use the Write tool NOW to save output to OUTPUT file. Do not ask for confirmation.

Do not output text during execution - only make tool calls.
Your final message must be ONLY one of:
  summarize: wrote ${BASE_NAME}_summary.md [TYPE]
  summarize: FAIL - {what went wrong}
where [TYPE] is one of: TIPS, INTERVIEW, EDUCATIONAL, TUTORIAL
```

## Handoff: resolve format path for Step 2

Parse `[TYPE]` from Step 1 output (e.g. `[INTERVIEW]`). Look up format file in ROUTING file (section 2, routing table). Pass resolved path as FORMAT to Step 2.

## Step 2: Review and tighten summary

task_tool:
- subagent_type: "general-purpose"
- model: "sonnet"
- prompt:
```
INPUT: <output_directory>/${BASE_NAME}_summary.md
OUTPUT: <output_directory>/${BASE_NAME}_summary_tight.md
TRANSCRIPT_BYTES: <size of transcript file in bytes>
ROUTING: ./summary_formats.md
FORMAT: <resolved format file path from handoff>

You are an adversarial copy editor. Cut fluff, enforce quality.

Rules:
- Read ROUTING — check length budget (section 3) for max bytes based on TRANSCRIPT_BYTES
- Read FORMAT (format-specific rules). The format has been selected — preserve it unless length budget forces flat bullets
- Hard ceiling: output must be < max ratio × TRANSCRIPT_BYTES. If over, cut sections or collapse to flat bullets
- Hidden Gems: Remove if duplicates main content
- Tightness: Cut filler words, compress verbose explanations, prefer lists over prose

Preserve original language - do not translate.

ACTION REQUIRED: Use the Write tool NOW to save output to OUTPUT file. Do not ask for confirmation.

Do not output text during execution - only make tool calls.
Your final message must be ONLY one of:
  tighten: wrote ${BASE_NAME}_summary_tight.md
  tighten: FAIL - {what went wrong}
```
