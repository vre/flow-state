# Comment Extract Module

Extracts, prefilters, and screens YouTube comments via two-tier filtering.

## Step 1: Extract comments

```bash
python3 ./scripts/run.py comments "<YOUTUBE_URL>" "<output_directory>"
```

Creates: youtube_{VIDEO_ID}_title.txt, youtube_{VIDEO_ID}_comments.md

## Step 2: Prefilter and split comments

```bash
python3 ./scripts/run.py filter-comments "<output_directory>/${BASE_NAME}_comments.md" "<output_directory>/${BASE_NAME}_comments_prefiltered.md" "<output_directory>/${BASE_NAME}_comments_candidates.md"
```

Creates: ${BASE_NAME}_comments_prefiltered.md (tier 1), optionally ${BASE_NAME}_comments_candidates.md (tier 2)

If output says "single tier" → skip to end, no candidates file created.

## Step 3: Screen tier-2 comments (if candidates file exists)

If `<output_directory>/${BASE_NAME}_comments_candidates.md` exists:

Use Task tool:
- subagent_type: "general-purpose"
- model: "haiku"
- prompt:

```
Read <output_directory>/${BASE_NAME}_comments_candidates.md

Each line is a comment: [N|@author|X likes] text

Output ONLY a comma-separated list of comment numbers (N) that contain
substantive content: personal experience, product names/models, technical
details, specific recommendations, failure reports, or meaningful stories.

Drop: generic praise, off-topic, pure jokes, vague opinions without specifics.

Do not use Bash. Read the candidate file and return only the KEEP line.
Format: KEEP: 17, 45, 51, ...

If no comments are substantive, output: KEEP:
```

Save the KEEP output string.

## Step 4: Merge and wrap comments

ALWAYS run when candidates file exists (even if KEEP list is empty — this adds safety wrapping):

```bash
python3 ./scripts/run.py merge-tier2 "<output_directory>/${BASE_NAME}_comments_candidates.md" "<output_directory>/${BASE_NAME}_comments_prefiltered.md" "<KEEP_STRING>"
```

Final output: ${BASE_NAME}_comments_prefiltered.md (merged, renumbered, safety-wrapped)
