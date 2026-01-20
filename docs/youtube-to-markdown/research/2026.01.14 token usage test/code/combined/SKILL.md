---
name: youtube-to-markdown
description: Use when user asks YouTube video extraction, get, fetch, transcripts, subtitles, or captions. Writes video details and transcription into structured markdown file.
allowed-tools:
  - Bash
  - Read
  - Write
  - Task
  - AskUserQuestion
---

# YouTube to Markdown (Combined Variant)

Test variant: Keeps all polish steps (4, 7, 8). Combines summary (5+6) and comments (10a+10b) into single subagents.

Execute all steps sequentially without asking for user approval.

## Step 0: Check extracted before

```bash
python3 ./check_existing.py "<YOUTUBE_URL>" "<output_directory>"
```

If returns `exists: true`: Skip to Step 10 (comments).

## Step 1: Extract data

```bash
python3 extract_data.py "<YOUTUBE_URL>" "<output_directory>"
```

## Step 2: Extract transcript

If video language is `en`, proceed directly. If non-English, ask user which language.

```bash
python3 extract_transcript.py "<YOUTUBE_URL>" "<output_directory>" "<LANG_CODE>"
```

### Fallback (only if transcript unavailable)

```bash
python3 extract_transcript_whisper.py "<YOUTUBE_URL>" "<output_directory>"
```

## Step 3: Deduplicate transcript

```bash
python3 ./deduplicate_vtt.py "<output_directory>/${BASE_NAME}_transcript.vtt" "<output_directory>/${BASE_NAME}_transcript_dedup.md" "<output_directory>/${BASE_NAME}_transcript_no_timestamps.txt"
```

## Step 4: Add natural paragraph breaks

task_tool:
- subagent_type: "general-purpose"
- model: "sonnet"
- prompt:
```
INPUT: <output_directory>/${BASE_NAME}_transcript_no_timestamps.txt
CHAPTERS: <output_directory>/${BASE_NAME}_chapters.json
OUTPUT: <output_directory>/${BASE_NAME}_transcript_paragraphs.txt

Analyze INPUT and identify natural paragraph break line numbers.
Read CHAPTERS. If contains chapters, use as primary break points.
Target ~500 chars per paragraph.

Write to OUTPUT: 15,42,78,103,...
```

```bash
python3 ./apply_paragraph_breaks.py "<output_directory>/${BASE_NAME}_transcript_dedup.md" "<output_directory>/${BASE_NAME}_transcript_paragraphs.txt" "<output_directory>/${BASE_NAME}_transcript_paragraphs.md"
```

## Step 5: Summarize transcript (combined summarize + tighten)

task_tool:
- subagent_type: "general-purpose"
- model: "sonnet"
- prompt:
```
INPUT: <output_directory>/${BASE_NAME}_transcript_no_timestamps.txt
OUTPUT: <output_directory>/${BASE_NAME}_summary_tight.md
FORMATS: ./summary_formats.md

1. Classify content type:
   - TIPS: gear reviews, rankings, practical advice
   - INTERVIEW: podcasts, conversations, Q&A
   - EDUCATIONAL: concept explanations, analysis
   - TUTORIAL: step-by-step instructions

2. Read FORMATS and create summary using format for detected type.

3. Self-review: Cut fluff, enforce <10% of transcript bytes, prefer lists over prose.

4. Save final tightened summary to OUTPUT.

Rules:
- Skip ads, sponsors, self-promotion
- Preserve original language

ACTION REQUIRED: Use Write tool NOW to save to OUTPUT file.
```

## Step 7: Clean speech artifacts

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
- Keep timestamps at end of paragraphs

ACTION REQUIRED: Write to <output_directory>/${BASE_NAME}_transcript_cleaned.md
```

## Step 8: Add topic headings

task_tool:
- subagent_type: "general-purpose"
- model: "sonnet"
- prompt:
```
INPUT: <output_directory>/${BASE_NAME}_transcript_cleaned.md
OUTPUT: <output_directory>/${BASE_NAME}_transcript.md
CHAPTERS: <output_directory>/${BASE_NAME}_chapters.json

Read INPUT. Add markdown headings.

If CHAPTERS has content: Use chapter names as ### headings
If empty: Add ### headings where major topics change

ACTION REQUIRED: Write to OUTPUT file.
```

## Step 9: Create output files

```bash
python3 finalize.py "${BASE_NAME}" "<output_directory>"
```

Use `--debug` flag to keep intermediate work files.

## Step 10: Extract and analyze comments (combined)

```bash
python3 ./extract_comments.py "<YOUTUBE_URL>" "<output_directory>"
python3 ./prefilter_comments.py "<output_directory>/${BASE_NAME}_comments.md" "<output_directory>/${BASE_NAME}_comments_prefiltered.md"
```

task_tool:
- subagent_type: "general-purpose"
- model: "sonnet"
- prompt:
```
SUMMARY_FILE: Find the main summary file "youtube - * (${VIDEO_ID}).md" in <output_directory>
COMMENTS: <output_directory>/${BASE_NAME}_comments_prefiltered.md

Read SUMMARY_FILE to understand video content and type.

Extract insights from COMMENTS that ADD VALUE beyond summary:
- Corrections/Extensions
- Alternative applications
- Debates/controversies

Format as:
## Comment Insights

**Key Takeaway**: [one sentence]

[Categories based on video type with @username attributions]

Rules:
- Only insights NOT already in summary
- Be ruthlessly concise

ACTION REQUIRED: Read the summary file, append Comment Insights section, and write back using Write tool.
```
