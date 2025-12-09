---
name: youtube-comment-analysis
description: Use when user requests YouTube comments. Run standalone for comment analysis or sequential with youtube-to-markdown for cross-analysis with video summary.
allowed-tools:
  - Bash
  - Read
  - Write
  - Task
  - AskUserQuestion
  - Skill
---

# YouTube Comment Analysis

Execute all steps sequentially without asking for user approval. Use TodoWrite to track progress.

## Step 0: Check for video summary

Extract video ID from URL and check if file matching `<output_directory>/youtube - *  ({video_id}).md` exists. If found, use it for context in later steps.

## Step 1: Extract comments

```bash
python3 ./extract_comments.py "<YOUTUBE_URL>" "<output_directory>"
```

Creates: youtube_{VIDEO_ID}_name.txt, youtube_{VIDEO_ID}_comments.md

## Step 2: Prefilter comments

```bash
python3 ./prefilter_comments.py "<output_directory>/${BASE_NAME}_comments.md" "<output_directory>/${BASE_NAME}_comments_prefiltered.md"
```

Creates: youtube_{VIDEO_ID}_comments_prefiltered.md

## Step 3: Extract Insightful Comments

task_tool:
- subagent_type: "general-purpose"
- model: "sonnet"
- prompt:
```
SUMMARY: "<output_directory>/youtube - * ({video_id}).md" if exists
INPUT: <output_directory>/${BASE_NAME}_comments_prefiltered.md
OUTPUT: <output_directory>/${BASE_NAME}_comment_insights.md

Extract, condense, combine and summarize ruthlessly for the MOST exceptional true insights NOT already covered by the summary. No fluff, NOT a document.

Write to OUTPUT in format:

## Comment Insights ([Analyze the insights and determine their primary theme/direction in 2-7 words])

Key Takeaway from Comments: [One paragraph summary - ONLY if it adds value beyond just repeating the bullet points below]

**[title per detected comment insight theme, if any detectable]**:
- [any true insights hiding in the comments, NOT in summary, **highlight keywords**]
```

## Step 4: Review and tighten comment insights

task_tool:
- subagent_type: "general-purpose"
- model: "sonnet"
- prompt:
```
SUMMARY: "<output_directory>/youtube - * ({video_id}).md" if exists
INPUT: <output_directory>/${BASE_NAME}_comment_insights.md
OUTPUT: <output_directory>/${BASE_NAME}_comment_insights_tight.md

You are an adversarial copy editor. Your job is to ruthlessly cut fluff and enforce quality standards.

Rules:
- Remove insights already in summary file
- Cut filler, prefer lists over prose
- Keep only exceptional value-add insights

ACTION REQUIRED: Use the Write tool NOW to save output to OUTPUT file. Do not ask for confirmation.
```

## Step 5: Finalize

```bash
python3 ./finalize_comments.py "${BASE_NAME}" "<output_directory>"
```

Output: `youtube - {title} - comments ({video_id}).md`

Use `--debug` flag to keep intermediate work files for inspection.
