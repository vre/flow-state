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

Execute all steps sequentially without asking for user approval. Use TodoWrite to track progress.

## Step 0: Ask about comment analysis

If not clear from user's request, ask:

```
AskUserQuestion:
- question: "Would you like to analyze comments after extracting the video transcript?"
- header: "Comments"
- options:
  1. label: "Yes, analyze comments"
     description: "After video extraction, run youtube-comment-analysis for cross-analysis with video summary"
  2. label: "No, video only"
     description: "Extract only video transcript and metadata"
```

Note user's choice for Step 9.

## Step 1: Extract data (metadata, description, chapters)

```bash
python3 extract_data.py "<YOUTUBE_URL>" "<output_directory>"
```

Script extracts video ID from URL and creates: youtube_{VIDEO_ID}_metadata.md, youtube_{VIDEO_ID}_description.md, youtube_{VIDEO_ID}_chapters.json

**IMPORTANT**: If you ask which language transcript to extract then do not translate that language to english and require that subagent do not translate either. Only if the user requests another language that the original then translate.

## Step 2: Extract transcript

### Primary method (if transcript available)

If video language is `en`, proceed directly. If non-English, ask user which language to download.

```bash
python3 extract_transcript.py "<YOUTUBE_URL>" "<output_directory>" "<LANG_CODE>"
```

Script creates: youtube_{VIDEO_ID}_transcript.vtt

**IMPORTANT**: All file output must be in the same language as discovered in Step 2. If language is not English, explicitly instruct all subagents to preserve the original language.

The download may fail if a video is private, age-restricted, or geo-blocked.

### Fallback (only if transcript unavailable)

Ask user: "No transcript available. Proceed with Whisper transcription?
- Mac/Apple Silicon: Uses MLX Whisper if installed (faster, see SETUP_MLX_WHISPER.md)
- All platforms: Falls back to OpenAI Whisper (requires: brew install openai-whisper OR pip3 install openai-whisper)"

```bash
python3 extract_transcript_whisper.py "<YOUTUBE_URL>" "<output_directory>"
```

Script auto-detects MLX Whisper on Mac and uses it if available, otherwise uses OpenAI Whisper.

## Step 3: Deduplicate transcript

Set BASE_NAME from Step 1 output (youtube_{VIDEO_ID})

```bash
python3 deduplicate_vtt.py "<output_directory>/${BASE_NAME}_transcript.vtt" "<output_directory>/${BASE_NAME}_transcript_dedup.md"
cut -c 16- <output_directory>/${BASE_NAME}_transcript_dedup.md > <output_directory>/${BASE_NAME}_transcript_no_timestamps.txt
```

## Step 4: Add natural paragraph breaks

Parallel with Step 5.

task_tool:
- subagent_type: "general-purpose"
- prompt:
```
Analyze <output_directory>/${BASE_NAME}_transcript_no_timestamps.txt and identify natural paragraph break line numbers.

Read <output_directory>/${BASE_NAME}_chapters.json. If it contains chapters, use chapter timestamps as primary break points.

Target ~500 chars per paragraph. Find natural break points at topic shifts or sentence endings.

Return format:
BREAKS: 15,42,78,103,...
```

```bash
python3 ./apply_paragraph_breaks.py "<output_directory>/${BASE_NAME}_transcript_dedup.md" "<output_directory>/${BASE_NAME}_transcript_paragraphs.md" "<BREAKS from task_tool>"
```

## Step 5: Summarize transcript

Parallel with Step 4.

task_tool:
- subagent_type: "general-purpose"
- prompt:
```
Summarize <output_directory>/${BASE_NAME}_transcript_no_timestamps.txt. No fluff, it is NOT a document. Aim to 10% xor max 1500 letters. Write to <output_directory>/${BASE_NAME}_summary.md:
**TL;DR**: [1 sentence core insight, do not repeat later]

[skip the question if repeating or non essential content]
**What**:
**Where**:
**When**:
**Why**:
**How**:
**What Then**:

**Hidden Gems**:
- [any insights hiding under the main story]
```

## Step 6: Clean speech artifacts

task_tool:
- subagent_type: "general-purpose"
- model: "haiku"
- prompt:
```
Read <output_directory>/${BASE_NAME}_transcript_paragraphs.md and clean speech artifacts. Write to <output_directory>/${BASE_NAME}_transcript_cleaned.md.

Tasks:
- Remove fillers (um, uh, like, you know)
- Fix transcription errors
- Add proper punctuation
- Reduce or add implicit words to improve flow
- Preserve natural voice and tone
- Keep timestamps at end of paragraphs
```

## Step 7: Add topic headings

task_tool:
- subagent_type: "general-purpose"
- prompt:
```
Read <output_directory>/${BASE_NAME}_transcript_cleaned.md and add markdown headings. Write to <output_directory>/${BASE_NAME}_transcript.md.

Read <output_directory>/${BASE_NAME}_chapters.json:
- If contains chapters: Use chapter names as ### headings at chapter timestamps, add #### headings for subtopics
- If empty: Add ### headings where major topics change
```

## Step 8: Finalize and cleanup

```bash
python3 finalize.py "${BASE_NAME}" "<output_directory>"
```

Script uses template.md to create final file by merging all component files (metadata, summary, description, transcript) and removes intermediate work files. Final output: `youtube - {title} ({video_id}).md`

Use `--debug` flag to keep intermediate work files for inspection.

## Step 9: Chain to comment analysis (optional)

If user chose "Yes, analyze comments" in Step 0 run youtube-comment-analysis Skill with the same YouTube URL.
