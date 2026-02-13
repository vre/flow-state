# Comment Extract Module

Extracts and prefilters YouTube comments.

## Step 1: Extract comments

```bash
python3 ./scripts/13_extract_comments.py "<YOUTUBE_URL>" "<output_directory>"
```

Creates: youtube_{VIDEO_ID}_title.txt, youtube_{VIDEO_ID}_comments.md

## Step 2: Prefilter comments

```bash
python3 ./scripts/32_filter_comments.py "<output_directory>/${BASE_NAME}_comments.md" "<output_directory>/${BASE_NAME}_comments_prefiltered.md"
```

Creates: youtube_{VIDEO_ID}_comments_prefiltered.md
