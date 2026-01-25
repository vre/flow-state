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

# YouTube to Markdown

Multiple videos: Process one video at a time, sequentially. Do not run parallel extractions. Do not create your own scripts.

## Step 0: Check if extracted before

```bash
python3 ./check_existing.py "<YOUTUBE_URL>" "<output_directory>"
```

Output JSON contains `video_id`. Set `BASE_NAME` = `youtube_{video_id}` for all subsequent steps.

If `exists: false`: Continue to Step 1.

If `exists: true`: Read and follow `./modules/update_flow.md`.

## Step 1: Choose output

AskUserQuestion:
- question: "What do you want to extract from the video?"
- header: "Output"
- multiSelect: false
- options:
  A. "Summary only" - Tight summary of video content
  B. "Transcript only" - Cleaned, formatted full transcript
  C. "Comments only" - Curated comments
  D. "Summary + Comments" - Summary with cross-analyzed comment insights
  E. "Full (Recommended)" - All: summary, transcript, comments

## Step 2: Execute modules

Based on user's choice, read and follow each module instruction in `./modules/{file}`. "|" marks possibility to run concurrently.

- A: transcript_extract.md → transcript_summarize.md
- B: transcript_extract.md → transcript_polish.md
- C: comment_extract.md
- D: transcript_extract.md → (transcript_summarize.md | comment_extract.md) → comment_summarize.md
- E: transcript_extract.md → (transcript_summarize.md | transcript_polish.md | comment_extract.md) → comment_summarize.md

## Step 3: Finalize

```bash
python3 finalize.py [flag] "${BASE_NAME}" "<output_directory>"
```

Flags: A=`--summary-only`, B=`--transcript-only`, C=`--comments-only`, D=`--summary-comments`, E=(none)

Use `--debug` to keep intermediate files.
