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

If you don't know from conversation context whether a video summary exists for this URL, extract video ID from URL and check if file matching `<output_directory>/youtube - * ({video_id}).md` exists.

If no summary file exists OR you don't know from context, ask user:

```
AskUserQuestion:
- question: "No video summary found. How would you like to proceed with comment analysis?"
- header: "Mode"
- options:
  1. label: "Create transcript first"
     description: "Run youtube-to-markdown skill to create video summary, then cross-analyze comments against it"
  2. label: "Standalone analysis"
     description: "Analyze comments without video context (faster, less informed)"
```

If user chooses "Create transcript first": Run youtube-to-markdown skill with the URL first, then proceed with youtube-comment-analysis skill.

If summary exists OR user chooses "Standalone analysis": Proceed directly to Step 1.

## Step 1: Extract comments

```bash
python3 ./extract_comments.py "<YOUTUBE_URL>" "<output_directory>"
```

Creates: youtube_{VIDEO_ID}_name.txt, youtube_{VIDEO_ID}_comments.md

## Step 2: Clean comments

task_tool:
- subagent_type: "general-purpose"
- model: "haiku"
- prompt:
```
Read Summary section from "<output_directory>/youtube - * ({video_id}).md" file to understand main points.

Read <output_directory>/${BASE_NAME}_comments.md to clean/curate comments. 

Tasks:
- Remove low-value: "+1", "thanks", "great video", spam, duplicates
- Remove comments that are off-topic (use summary to identify if available)
- Remove comments that repeat content from the summary or other comments

Write as is to <output_directory>/${BASE_NAME}_comments_cleaned.md. Do not translate.
```

## Step 3: Extract Insightful Comments

task_tool:
- subagent_type: "general-purpose"
- prompt:
```
Read Summary section from "<output_directory>/youtube - * ({video_id}).md" file if available.

Read <output_directory>/${BASE_NAME}_comments_cleaned.md. Extract, condense, combine and summarize ruthlessly for the MOST exceptional true insights NOT already covered by the summary. No fluff, NOT a document.

Write to <output_directory>/${BASE_NAME}_comment_insights.md in format:

## Comment Insights ([Analyze the insights and determine their primary theme/direction in 2-7 words])

Key Takeaway from Comments: [One paragraph summary - ONLY if it adds value beyond just repeating the bullet points below]

**[title per detected comment insight theme, if any detectable]**:
- [any true insights hiding in the comments, NOT in summary, **highlight keywords**]
- [insight 2]
- [insight N]
```

## Step 3.5: Generate Quick Summary

Write a finalizing short summary to <output_directory>/${BASE_NAME}_quick_summary.md synthesizing video + comment insights.

## Step 4: Finalize

```bash
python3 ./finalize_comments.py "${BASE_NAME}" "<output_directory>"
```

Output: `youtube - {title} - comments ({video_id}).md`

Use `--debug` flag to keep intermediate work files for inspection.
