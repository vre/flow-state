# Transcript Polish Module

Cleans and formats transcript for readability.

## Step 1: Add natural paragraph breaks

task_tool:
- subagent_type: "general-purpose"
- model: "sonnet"
- prompt:
```
INPUT: <output_directory>/${BASE_NAME}_transcript_no_timestamps.txt
CHAPTERS: <output_directory>/${BASE_NAME}_chapters.json
OUTPUT: <output_directory>/${BASE_NAME}_transcript_paragraphs.txt

Analyze INPUT and identify natural paragraph break line numbers.

Read CHAPTERS. If it contains chapters, use chapter timestamps as primary break points.

Target ~500 chars per paragraph. Find natural break points at topic shifts or sentence endings.

Write to OUTPUT in format:
15,42,78,103,...

Do not output text during execution - only make tool calls.
Your final message must be ONLY one of:
  paragraphs: wrote ${BASE_NAME}_transcript_paragraphs.txt
  paragraphs: FAIL - {what went wrong}
```

```bash
python3 ./scripts/31_format_transcript.py "<output_directory>/${BASE_NAME}_transcript_dedup.md" "<output_directory>/${BASE_NAME}_transcript_paragraphs.txt" "<output_directory>/${BASE_NAME}_transcript_paragraphs.md"
```

## Step 2: Clean speech artifacts

task_tool:
- subagent_type: "general-purpose"
- model: "haiku"
- prompt:
```
Read <output_directory>/${BASE_NAME}_transcript_paragraphs.md and clean speech artifacts.

Tasks:
- Remove fillers (um, uh, like, you know)
- Fix transcription errors
- Add proper punctuation
- Reduce or add implicit words to improve flow
- Preserve natural voice and tone
- Keep timestamps at end of paragraphs

ACTION REQUIRED: Use the Write tool NOW to save output to <output_directory>/${BASE_NAME}_transcript_cleaned.md. Do not ask for confirmation.
Do not output text during execution - only make tool calls.
Your final message must be ONLY one of:
  clean: wrote ${BASE_NAME}_transcript_cleaned.md
  clean: FAIL - {what went wrong}
```

## Step 3: Add topic headings

task_tool:
- subagent_type: "general-purpose"
- model: "sonnet"
- prompt:
```
INPUT: <output_directory>/${BASE_NAME}_transcript_cleaned.md
OUTPUT: <output_directory>/${BASE_NAME}_transcript.md

Read the INPUT file. Add markdown headings.

Read <output_directory>/${BASE_NAME}_chapters.json:
- If contains chapters: Use chapter names as ### headings at chapter timestamps, add #### headings for subtopics
- If empty: Add ### headings where major topics change

ACTION REQUIRED: Use the Write tool NOW to save output to OUTPUT file. Do not ask for confirmation.
Do not output text during execution - only make tool calls.
Your final message must be ONLY one of:
  headings: wrote ${BASE_NAME}_transcript.md
  headings: FAIL - {what went wrong}
```
