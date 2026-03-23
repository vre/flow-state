# Transcript Summarize Module

Creates tight summary from transcript.

## Step 1: Summarize transcript

task_tool:
- subagent_type: "general-purpose"
- model: "sonnet"
- prompt:
```
INPUT: <output_directory>/${BASE_NAME}_transcript_no_timestamps.txt
OUTPUT: <output_directory>/${BASE_NAME}_summary.md
ROUTING: ./summary_formats.md
FORMATS_DIR: ./formats/

1. Read ROUTING file.

2. Classify content type:
   - TIPS: gear reviews, rankings, "X ways to...", practical advice lists
   - INTERVIEW: podcasts, conversations, Q&A, multiple perspectives
   - EDUCATIONAL: concept explanations, analysis, "how X works"
   - TUTORIAL: step-by-step instructions, coding, recipes
   - Ambiguity: classify by dominant structure. Default fallback: INTERVIEW.

3. Resolve format file from routing table: FORMATS_DIR/<filename>. Read it.

4. Analyze content structure:
   - Identify meaningful content units (topic shifts, argument structure, narrative breaks)
   - If single continuous topic and format allows headerless output (TIPS), omit content unit headers. Formats requiring section headings (INTERVIEW, EDUCATIONAL, TUTORIAL) always use them.
   - Skip ads, sponsors, self-promotion ("like and subscribe", merch, etc.)
   - Merge content spanning ad breaks if thematically connected

5. Produce summary applying cross-cutting rules from ROUTING + format-specific rules from format file. Target <10% of transcript bytes.


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
ROUTING: ./summary_formats.md
FORMAT: <resolved format file path from handoff>

You are an adversarial copy editor. Cut fluff, enforce quality.

Rules:
- Read ROUTING (cross-cutting rules) and FORMAT (format-specific rules). The format has been selected — preserve it. Do not change the format structure.
- Byte budget: <10% of transcript bytes
- Hidden Gems: Remove if duplicates main content
- Tightness: Cut filler words, compress verbose explanations, prefer lists over prose

Preserve original language - do not translate.

ACTION REQUIRED: Use the Write tool NOW to save output to OUTPUT file. Do not ask for confirmation.

Do not output text during execution - only make tool calls.
Your final message must be ONLY one of:
  tighten: wrote ${BASE_NAME}_summary_tight.md
  tighten: FAIL - {what went wrong}
```
