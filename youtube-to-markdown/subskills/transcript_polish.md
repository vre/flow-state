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

## Step 2: Clean speech artifacts + write chunk analysis

```bash
python3 ./scripts/33_split_for_cleaning.py "<output_directory>/${BASE_NAME}_transcript_paragraphs.md" "<output_directory>"
```

Read stdout JSON.

Expected schema:
```json
{
  "chunks": [
    {"path": "/abs/path/chunk_001.md", "para_start": 1, "para_end": 20},
    {"path": "/abs/path/chunk_002.md", "para_start": 21, "para_end": 40}
  ]
}
```

For each chunk object in `chunks`, launch a parallel `task_tool`:
- subagent_type: "general-purpose"
- model: "sonnet"
- run_in_background: true
- prompt:
```
INPUT_CHUNK: {chunk_path}
PARAGRAPH_RANGE: {para_start}-{para_end} (global paragraph numbers)
OUTPUT_CLEANED: {chunk_path_cleaned}
OUTPUT_ANALYSIS: {analysis_path}

PERMISSION TEST: First, Write "test" to OUTPUT_CLEANED. If Write succeeds, proceed normally (Mode A). If Write fails, use Mode B.

Read INPUT_CHUNK and clean speech artifacts.

Tasks:
- Remove fillers (um, uh, like, you know)
- Fix transcription errors
- Add proper punctuation
- Reduce or add implicit words to improve flow
- Preserve natural voice and tone
- Keep timestamps at end of paragraphs
- IMPORTANT: Do not merge, split, or reorder paragraphs. Preserve the exact paragraph count.

Also write chunk analysis in markdown:
- Header: chunk identity + paragraph range + time range
- Gate: WATCH | SKIM | READ-ONLY with 1-sentence rationale
- Topics: include GLOBAL paragraph numbers from PARAGRAPH_RANGE context
- Watch moments: timestamped moments where visual context matters
- Skip: timestamp ranges with reason

Mode A (Write works): Write cleaned text to OUTPUT_CLEANED and analysis to OUTPUT_ANALYSIS. Final message:
  clean+analyze: wrote {cleaned_filename} and {analysis_filename}

Mode B (Write denied): Return content in final message. Format:
  CONTENT:{OUTPUT_CLEANED}
  <cleaned text>
  END_CONTENT
  CONTENT:{OUTPUT_ANALYSIS}
  <analysis markdown>
  END_CONTENT

Do not ask for confirmation. Do not output text during execution — only make tool calls (Mode A) or return CONTENT blocks (Mode B).
On failure: clean+analyze: FAIL - {what went wrong}
```

Analysis naming convention:
- If chunk file matches `${BASE_NAME}_chunk_NNN.md`: analysis path is `${BASE_NAME}_chunk_NNN_analysis.md`
- If chunk file is passthrough `${BASE_NAME}_transcript_paragraphs.md`: analysis path is `<output_directory>/${BASE_NAME}_analysis.md`

Wait for all subagents. If a chunk fails, retry once.

If any subagent returned `CONTENT:` blocks (Mode B fallback), parse and write each file with Write tool:
- Extract path from `CONTENT:<path>` line
- Extract content between that line and `END_CONTENT`
- Write to the specified path

```bash
python3 ./scripts/34_concat_cleaned.py {chunk_1_cleaned} ... {chunk_N_cleaned} "<output_directory>/${BASE_NAME}_transcript_cleaned.md"
```

## Step 3: Synthesize headings + optional watch guide

Resolve summary file before synthesis:

```bash
python3 ./scripts/36_resolve_summary.py "${BASE_NAME}" "<output_directory>"
```

Collect analysis files:
- Include `<output_directory>/${BASE_NAME}_analysis.md` if it exists
- Include all `<output_directory>/${BASE_NAME}_chunk_*_analysis.md` files

Check heatmap file:
- `HEATMAP=<output_directory>/${BASE_NAME}_heatmap.json`
- If it exists, include as input. If not, omit.

Check flag file:
- `FLAG=<output_directory>/${BASE_NAME}_watch_guide_requested.flag`

If `FLAG` exists, launch synthesis `task_tool` (headings + watch guide):
- subagent_type: "general-purpose"
- model: "sonnet"
- prompt:
```
INPUT_ANALYSES: {analysis_file_list}
INPUT_CHAPTERS: <output_directory>/${BASE_NAME}_chapters.json
INPUT_METADATA: <output_directory>/${BASE_NAME}_metadata.md
INPUT_HEATMAP: {heatmap_path_or_none}
INPUT_SUMMARY: {resolved_summary_or_none}
VIDEO_ID: {video_id}
OUTPUT_HEADINGS: <output_directory>/${BASE_NAME}_headings.json
OUTPUT_WATCH_GUIDE: <output_directory>/${BASE_NAME}_watch_guide.md

Read all existing inputs.

Output 1: headings JSON
- Format: [{"before_paragraph": <global int>, "heading": "### Topic"}, ...]
- Use global paragraph numbers from analysis topics

Output 2: watch guide — curated viewing path

Write in the same language as the source content. Never reference chunks or internal terms.

Format: summary paragraphs alternating with video links.
- Summary = what was discussed, key claims and data. Reader gets 95% of value from summaries alone.
- Video link = `▶ [Title](https://youtube.com/watch?v={video_id}&t=SECONDS) MM:SS–MM:SS — Why watch: reason`
- Calculate t=SECONDS: hours*3600 + minutes*60 + seconds. Over 1 hour use H:MM:SS.
- Only link moments where WATCHING adds value over READING. Ask: "Does seeing this give something the text cannot?" Physical demo, humor timing, on-screen data, emotional reaction → yes. Expert analysis, verbal anecdote, facts → no, summarize instead. Zero links is fine for talking-head content.
- Heatmap (if provided): {start_time, end_time, value 0-1} = viewer replay intensity. Use as tiebreaker, not primary signal — popular ≠ must-watch when the transcript exists.

ACTION REQUIRED:
1) Write valid JSON to OUTPUT_HEADINGS.
2) Write markdown to OUTPUT_WATCH_GUIDE.
Do not ask for confirmation.

Do not output text during execution - only make tool calls.
Your final message must be ONLY one of:
  synthesize: wrote ${BASE_NAME}_headings.json and ${BASE_NAME}_watch_guide.md
  synthesize: FAIL - {what went wrong}
```

If `FLAG` does not exist, launch synthesis `task_tool` (headings only):
- subagent_type: "general-purpose"
- model: "sonnet"
- prompt:
```
INPUT_ANALYSES: {analysis_file_list}
INPUT_CHAPTERS: <output_directory>/${BASE_NAME}_chapters.json
INPUT_METADATA: <output_directory>/${BASE_NAME}_metadata.md
INPUT_HEATMAP: {heatmap_path_or_none}
INPUT_SUMMARY: {resolved_summary_or_none}
OUTPUT_HEADINGS: <output_directory>/${BASE_NAME}_headings.json

Read all existing inputs.

Output headings JSON:
[{"before_paragraph": <global int>, "heading": "### Topic"}, ...]

ACTION REQUIRED: Write valid JSON to OUTPUT_HEADINGS.
Do not ask for confirmation.
Do not output text during execution - only make tool calls.
Your final message must be ONLY one of:
  synthesize: wrote ${BASE_NAME}_headings.json
  synthesize: FAIL - {what went wrong}
```

Then insert headings:

```bash
python3 ./scripts/35_insert_headings_from_json.py "<output_directory>/${BASE_NAME}_transcript_cleaned.md" "<output_directory>/${BASE_NAME}_headings.json" "<output_directory>/${BASE_NAME}_transcript.md"
```
