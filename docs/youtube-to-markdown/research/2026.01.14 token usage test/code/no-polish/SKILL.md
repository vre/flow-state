---
name: youtube-to-markdown
description: Use when user asks YouTube video extraction, get, fetch, transcripts, subtitles, or captions. Writes video details and transcription into structured markdown file.
allowed-tools:
  - Bash
  - Read
  - Write
  - Task
  - AskUserQuestion
  - Skill
---

# YouTube to Markdown (No-Polish Variant)

Test variant: Removes transcript polish steps (4, 7, 8). Keeps separate summary steps (5, 6) and comment steps (10a, 10b).

Execute all steps sequentially without asking for user approval.

## Step 0: Check extracted before

```bash
python3 ./check_existing.py "<YOUTUBE_URL>" "<output_directory>"
```

If returns `exists: true`: Skip to Step 10 (comments).

## Step 1: Extract data (metadata, description, chapters)

```bash
python3 extract_data.py "<YOUTUBE_URL>" "<output_directory>"
```

Creates: youtube_{VIDEO_ID}_metadata.md, youtube_{VIDEO_ID}_description.md, youtube_{VIDEO_ID}_chapters.json

## Step 2: Extract transcript

If video language is `en`, proceed directly. If non-English, ask user which language.

```bash
python3 extract_transcript.py "<YOUTUBE_URL>" "<output_directory>" "<LANG_CODE>"
```

Creates: youtube_{VIDEO_ID}_transcript.vtt

### Fallback (only if transcript unavailable)

Ask user: "No transcript available. Proceed with Whisper transcription?"

```bash
python3 extract_transcript_whisper.py "<YOUTUBE_URL>" "<output_directory>"
```

## Step 3: Deduplicate transcript

Set BASE_NAME from Step 1 output (youtube_{VIDEO_ID})

```bash
python3 ./deduplicate_vtt.py "<output_directory>/${BASE_NAME}_transcript.vtt" "<output_directory>/${BASE_NAME}_transcript_dedup.md" "<output_directory>/${BASE_NAME}_transcript_no_timestamps.txt"
```

Copy dedup as final transcript (no polish steps):
```bash
cp "<output_directory>/${BASE_NAME}_transcript_dedup.md" "<output_directory>/${BASE_NAME}_transcript.md"
```

## Step 5: Summarize transcript

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
   - Skip ads, sponsors, self-promotion

3. Read FORMATS file and use format for detected content type. Target <10% of transcript bytes.

ACTION REQUIRED: Use the Write tool NOW to save output to OUTPUT file.
```

## Step 6: Review and tighten summary

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
- Read FORMATS - preserve format
- Byte budget: <10% of transcript bytes
- Hidden Gems: Remove if duplicates main content
- Tightness: Cut filler words, compress verbose explanations, prefer lists over prose

Preserve original language - do not translate.

ACTION REQUIRED: Use the Write tool NOW to save output to OUTPUT file.
```

## Step 9: Create output files

```bash
python3 finalize.py "${BASE_NAME}" "<output_directory>"
```

Outputs:
- `youtube - {title} ({video_id}).md` - Main summary
- `youtube - {title} - transcript ({video_id}).md` - Description and transcript

Use `--debug` flag to keep intermediate work files.

## Step 10a: Extract comments

```bash
python3 ./extract_comments.py "<YOUTUBE_URL>" "<output_directory>"
```

Creates: youtube_{VIDEO_ID}_comments.md

```bash
python3 ./prefilter_comments.py "<output_directory>/${BASE_NAME}_comments.md" "<output_directory>/${BASE_NAME}_comments_prefiltered.md"
```

## Step 10b: Analyze comments

task_tool:
- subagent_type: "general-purpose"
- model: "sonnet"
- prompt:
```
SUMMARY: <output_directory>/${BASE_NAME}_summary_tight.md
COMMENTS: <output_directory>/${BASE_NAME}_comments_prefiltered.md
OUTPUT: Append to summary file

Read SUMMARY to understand video content.

Detect video type:
- TIPS: gear reviews, rankings, practical advice
- INTERVIEW: podcasts, conversations, Q&A
- EDUCATIONAL: concept explanations, analysis
- TUTORIAL: step-by-step instructions

Extract insights from COMMENTS that ADD VALUE beyond summary.

Format output as:
## Comment Insights

**Key Takeaway**: [one sentence]

[Category based on video type]:
- **[Insight type]**: [insight with @username attribution]

Rules:
- Only insights NOT already in summary
- Prioritize actionable over opinions
- Be ruthlessly concise

ACTION REQUIRED: Read the summary file and append Comment Insights section using Write tool.
```
