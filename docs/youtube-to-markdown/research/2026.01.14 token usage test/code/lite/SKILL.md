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

# YouTube to Markdown (Lite Variant)

Optimized variant: No polish steps (4, 7, 8) + combined workflows (5+6, 10a+10b).
Result: 2 subagents for minimum cost.

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

Copy dedup as final transcript (no polish steps):
```bash
cp "<output_directory>/${BASE_NAME}_transcript_dedup.md" "<output_directory>/${BASE_NAME}_transcript.md"
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
SUMMARY: <output_directory>/${BASE_NAME}_summary_tight.md
COMMENTS: <output_directory>/${BASE_NAME}_comments_prefiltered.md

Read SUMMARY to understand video content and type.

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

ACTION REQUIRED: Read SUMMARY, append Comment Insights section, and write back using Write tool.
```

## Step 9: Create output files

```bash
python3 finalize.py "${BASE_NAME}" "<output_directory>"
```

Outputs:
- `youtube - {title} ({video_id}).md` - Main summary with comment insights
- `youtube - {title} - transcript ({video_id}).md` - Description and transcript
