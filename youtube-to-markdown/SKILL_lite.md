---
name: youtube-to-markdown-lite
description: Fast, token-efficient YouTube extraction. Produces summary + comment insights without cosmetic polish. Use when AI will consume the output or cost matters.
allowed-tools:
  - Bash
  - Read
  - Write
  - Task
---

# YouTube to Markdown (Lite)

Optimized for token efficiency. Skips human-readability polish (paragraph breaks, artifact cleaning, topic headings).

Output: Summary with comment insights in single file.

Execute all steps sequentially without asking for user approval.

## Step 0: Check extracted before

```bash
python3 ./check_existing.py "<YOUTUBE_URL>" "<output_directory>"
```

If `exists: true` and `summary_valid: true`: Skip to Step 4 (comments).

## Step 1: Extract data (metadata, description, chapters)

```bash
python3 ./extract_data.py "<YOUTUBE_URL>" "<output_directory>"
```

Creates: youtube_{VIDEO_ID}_metadata.md, youtube_{VIDEO_ID}_description.md, youtube_{VIDEO_ID}_chapters.json

## Step 2: Extract transcript

If video language is `en`, proceed directly. If non-English, ask user which language.

```bash
python3 ./extract_transcript.py "<YOUTUBE_URL>" "<output_directory>" "<LANG_CODE>"
```

Creates: youtube_{VIDEO_ID}_transcript.vtt

### Fallback (only if transcript unavailable)

Ask user: "No transcript available. Proceed with Whisper transcription?"

```bash
python3 ./extract_transcript_whisper.py "<YOUTUBE_URL>" "<output_directory>"
```

## Step 3: Deduplicate transcript

```bash
python3 ./deduplicate_vtt.py "<output_directory>/${BASE_NAME}_transcript.vtt" "<output_directory>/${BASE_NAME}_transcript_dedup.md" "<output_directory>/${BASE_NAME}_transcript_no_timestamps.txt"
```

## Step 4: Summarize transcript (combined summarize + tighten)

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

2. Read FORMATS file and create summary using format for detected content type.

3. Self-review: Cut fluff, enforce <10% of transcript bytes, prefer lists over prose.

4. Save final tightened summary to OUTPUT file.

Rules:
- Skip ads, sponsors, self-promotion
- Preserve original language - do not translate

ACTION REQUIRED: Use Write tool NOW to save to OUTPUT file.
```

## Step 5: Extract comments

```bash
python3 ./extract_comments.py "<YOUTUBE_URL>" "<output_directory>"
```

Creates: youtube_{VIDEO_ID}_comments.md

```bash
python3 ./prefilter_comments.py "<output_directory>/${BASE_NAME}_comments.md" "<output_directory>/${BASE_NAME}_comments_prefiltered.md"
```

## Step 6: Analyze comments (combined extract + tighten)

task_tool:
- subagent_type: "general-purpose"
- model: "sonnet"
- prompt:
```
SUMMARY: <output_directory>/${BASE_NAME}_summary.md
COMMENTS: <output_directory>/${BASE_NAME}_comments_prefiltered.md
OUTPUT: <output_directory>/${BASE_NAME}_comment_insights.md

Read SUMMARY to understand video content and type.

Detect video type:
- TIPS: gear reviews, rankings, practical advice
- INTERVIEW: podcasts, conversations, Q&A
- EDUCATIONAL: concept explanations, analysis
- TUTORIAL: step-by-step instructions

Extract insights from COMMENTS that ADD VALUE beyond summary:

TUTORIAL:
- **Common Failures**: what goes wrong, why, how to fix
- **Success Patterns**: what worked, time investment

TIPS:
- **What Worked/Didn't**: real-world validation
- **Alternatives Mentioned**: products, methods

INTERVIEW:
- **Points of Agreement/Debate**: where commenters align/clash
- **Related Stories**: personal experiences shared

EDUCATIONAL:
- **Corrections/Extensions**: where commenters add/fix content
- **Debates**: alternative viewpoints

Rules:
- Only insights NOT already in summary
- Prioritize actionable over opinions
- Be ruthlessly concise - cut fluff
- If comments add nothing, write "No significant insights beyond video content"

ACTION REQUIRED: Use Write tool NOW to save to OUTPUT file.
```

## Step 7: Finalize

```bash
python3 ./finalize_lite.py "${BASE_NAME}" "<output_directory>"
```

Creates single output file: `youtube - {title} ({video_id}).md`

Format:
```markdown
# {title}

## Summary
[content from summary.md]

## What Viewers Add
[content from comment_insights.md]

## Video Info
- Channel: {channel}
- Duration: {duration}
- Published: {date}
- URL: {url}
```

Use `--debug` flag to keep intermediate work files.
