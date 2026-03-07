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

## Step 2: Clean speech artifacts (chunked)

```bash
python3 ./scripts/33_split_for_cleaning.py "<output_directory>/${BASE_NAME}_transcript_paragraphs.md" "<output_directory>"
```

Read stdout JSON. For each chunk path in `chunks` array, launch a parallel `task_tool`:
- subagent_type: "general-purpose"
- model: "sonnet"
- run_in_background: true
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

```bash
python3 ./scripts/34_concat_cleaned.py {chunk_1_cleaned} ... {chunk_N_cleaned} "<output_directory>/${BASE_NAME}_transcript_cleaned.md"
```

## Step 3: Add AI topic headings

Launch `task_tool`:
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

```bash
python3 ./scripts/35_insert_headings_from_json.py "<output_directory>/${BASE_NAME}_transcript_cleaned.md" "<output_directory>/${BASE_NAME}_headings.json" "<output_directory>/${BASE_NAME}_transcript.md"
```
