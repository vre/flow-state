# Watch Guide Module

Generates a watch guide from polished transcript with WATCH/SKIM/READ-ONLY gate.

## Step 1: Guard for long transcripts

```bash
python3 ./scripts/run.py guard "<output_directory>/${BASE_NAME}_transcript.md" --max-size 153600
```

If output starts with `skip:` then STOP and do not create `${BASE_NAME}_watch_guide.md`.

## Step 2: Generate watch guide

task_tool:
- subagent_type: "general-purpose"
- model: "sonnet"
- prompt:
```
INPUT_TRANSCRIPT: <output_directory>/${BASE_NAME}_transcript.md
INPUT_SUMMARY: <output_directory>/${BASE_NAME}_summary_tight.md
INPUT_COMMENTS: <output_directory>/${BASE_NAME}_comment_insights_tight.md
INPUT_CHAPTERS: <output_directory>/${BASE_NAME}_chapters.json
INPUT_METADATA: <output_directory>/${BASE_NAME}_metadata.md
OUTPUT: <output_directory>/${BASE_NAME}_watch_guide.md

Read all inputs that exist.

Write the watch guide in the same language as INPUT_TRANSCRIPT.

First line MUST be exactly one of:
- WATCH: {1-2 sentence justification}
- SKIM: {1-2 sentence justification}
- READ-ONLY: {1-2 sentence justification}

If verdict is READ-ONLY, write ONLY the first line and nothing else.

If verdict is WATCH or SKIM, output sections:
- Highlights: timestamped deep links and why watch > read
- Read Instead: what can be read instead of watched
- Watch Route: compact ordered route with total minutes

Cross-link references:
- Use dedicated lines that start with `→ `
- Each `→ ` line contains only a transcript heading name copied verbatim from INPUT_TRANSCRIPT
- No reason text on `→ ` lines; put reason text on the line before

Do not include transcript filenames, slugs, or anchors. The assembler creates links.

ACTION REQUIRED: Use the Write tool to save output to OUTPUT.
Do not use Bash. Use Read and Grep tools for file analysis, and Write for output.
Do not output text during execution - only make tool calls.
Your final message must be ONLY one of:
  watch_guide: wrote ${BASE_NAME}_watch_guide.md
  watch_guide: SKIP - transcript too large or missing
  watch_guide: FAIL - {what went wrong}
```
