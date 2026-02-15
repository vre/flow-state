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
FORMATS: ./summary_formats.md

1. Classify content type:
   - TIPS: gear reviews, rankings, "X ways to...", practical advice lists
   - INTERVIEW: podcasts, conversations, Q&A, multiple perspectives
   - EDUCATIONAL: concept explanations, analysis, "how X works"
   - TUTORIAL: step-by-step instructions, coding, recipes

2. Analyze content structure:
   - Identify meaningful content units (topic shifts, argument structure, narrative breaks)
   - If single continuous topic, omit content unit headers
   - Skip ads, sponsors, self-promotion ("like and subscribe", merch, etc.)
   - Merge content spanning ad breaks if thematically connected

3. Read FORMATS file and use format for detected content type. Target <10% of transcript bytes.


ACTION REQUIRED: Use the Write tool NOW to save output to OUTPUT file. Do not ask for confirmation.
Do not output text during execution - only make tool calls.
Your final message must be ONLY one of:
  summarize: wrote ${BASE_NAME}_summary.md
  summarize: FAIL - {what went wrong}
```

## Step 2: Review and tighten summary

task_tool:
- subagent_type: "general-purpose"
- model: "sonnet"
- prompt:
```
INPUT: <output_directory>/${BASE_NAME}_summary.md
OUTPUT: <output_directory>/${BASE_NAME}_summary_tight.md
FORMATS: ./summary_formats.md

You are an adversarial copy editor. Cut fluff, enforce quality.

Rules:
- Read FORMATS - the format has been selected based on the content type - preserve format and do not count a reason to squeeze more from budget.
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
