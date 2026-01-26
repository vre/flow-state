# Transcript Extract Module

Extracts metadata, description, transcript from YouTube video.

## Step 1: Extract data (metadata, description, chapters)

```bash
python3 ./scripts/10_extract_metadata.py "<YOUTUBE_URL>" "<output_directory>"
```

Creates: youtube_{VIDEO_ID}_metadata.md, youtube_{VIDEO_ID}_description.md, youtube_{VIDEO_ID}_chapters.json

Language policy: Prefer original language. Instruct subagents to preserve the original language - never translate unless user explicitly requests it.

## Step 2: Extract transcript

### Primary method (if transcript available)

If video language is `en`, proceed directly. If non-English, ask user which language to download.

```bash
python3 ./scripts/11_extract_transcript.py "<YOUTUBE_URL>" "<output_directory>" "<LANG_CODE>"
```

Creates: youtube_{VIDEO_ID}_transcript.vtt

IMPORTANT: All file output must be in the same language as discovered in Step 2. If language is not English, explicitly instruct all subagents to preserve the original language.

The download may fail if a video is private, age-restricted, or geo-blocked.

### Fallback (only if transcript unavailable)

Ask user: "No transcript available. Proceed with Whisper transcription?
- Mac/Apple Silicon: Uses MLX Whisper if installed (faster, see SETUP_MLX_WHISPER.md)
- All platforms: Falls back to OpenAI Whisper (requires: brew install openai-whisper OR pip3 install openai-whisper)"

```bash
python3 ./scripts/12_extract_transcript_whisper.py "<YOUTUBE_URL>" "<output_directory>"
```

Script auto-detects MLX Whisper on Mac and uses it if available, otherwise uses OpenAI Whisper.

## Step 3: Deduplicate transcript

```bash
python3 ./scripts/30_clean_vtt.py "<output_directory>/${BASE_NAME}_transcript.vtt" "<output_directory>/${BASE_NAME}_transcript_dedup.md" "<output_directory>/${BASE_NAME}_transcript_no_timestamps.txt"
```
