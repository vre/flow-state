---
name: youtube-to-markdown
description: Use when user asks YouTube video extraction, get, fetch, transcripts, subtitles, or captions, or channel browsing. Writes video details and transcription into structured markdown file.
allowed-tools:
  - Bash
  - Read
  - Write
  - Task
  - AskUserQuestion
  - Skill
---

# YouTube to Markdown

Multiple videos: Process one video at a time, sequentially. Do not run parallel extractions. Do not create your own scripts.

## Step -1: Detect input type

If input is a channel URL (contains `/@`, `/channel/`, `/c/`, `/user/`) or a bare channel ID (starts with `UC`, 24 chars), but NOT `watch?v=`:
  Read and follow `./subskills/channel_browse.md`.

Otherwise: Continue to Step 0.

## Step 0: Check if extracted before

```bash
python3 ./scripts/20_check_existing.py "<YOUTUBE_URL>" "<output_directory>"
```

Output JSON contains `video_id`. Set `BASE_NAME` = `youtube_{video_id}` for all subsequent steps.

Write `"# Processing {video_id}\n"` to `<output_directory>/${BASE_NAME}_warmup.tmp`. This ensures Write tool is approved before subagents need it.

If `exists: false`: Continue to Step 1.

If `exists: true`: Read and follow `./subskills/update_flow.md`.

## Step 1: Choose output

AskUserQuestion:
- question: "What do you want to extract from the video?"
- header: "Output"
- multiSelect: false
- options:
  A. "Summary + Comments (Recommended)" - Summary cross-analyzed with comments. Transcript stored if it should be processed.
  B. "Summary + Comments + Formatted Transcript" - Option A + cleaned and formatted full transcript → double tokens
  C. "Summary Only" - Summary of video content
  D. "Formatted Transcript Only" - Cleaned and formatted full transcript

## Step 2: Execute modules

Based on user's choice, read and follow each subskill instruction in `./subskills/{file}`. "|" marks possibility to run concurrently.

- A: transcript_extract.md → (transcript_summarize.md | comment_extract.md) → comment_summarize.md
- B: transcript_extract.md → (transcript_summarize.md | transcript_polish.md | comment_extract.md) → comment_summarize.md
- C: transcript_extract.md → transcript_summarize.md
- D: transcript_extract.md → transcript_polish.md

## Step 3: Finalize

```bash
python3 ./scripts/50_assemble.py [flag] "${BASE_NAME}" "<output_directory>"
```

Flags: A=`--summary-comments`, B=(none), C=`--summary-only`, D=`--transcript-only`

Use `--debug` to keep intermediate files.
