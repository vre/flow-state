# Channel Browse

Browse a YouTube channel's videos, select new ones to extract, check comment growth on existing.

## Step C1: List channel videos

```bash
python3 ./scripts/22_list_channel.py "<CHANNEL_URL>" "<output_directory>"
```

If `output_dir_suggestion` is set and no `existing_videos`:
  AskUserQuestion: "Create channel directory '{suggestion}'?"
  If yes: use suggested directory as `<output_directory>` for all subsequent steps.

## Step C2: Present video list

Show to user:

### {channel.name} ({channel.total_videos or page.count + "+"} videos) {channel.verified ? "✓" : ""}

**New videos** (not yet extracted):
| # | Title | Views | Duration |
|---|-------|-------|----------|

**Already extracted** ({count}):
| # | Title | Views | Duration | Stored comments |
|---|-------|-------|----------|-----------------|

Page info: showing {page.offset + 1}–{page.offset + page.count}. {page.has_more ? "More available." : "End of list."}

Omit empty tables.

## Step C3: User selection

AskUserQuestion:
- question: "What would you like to do?"
- header: "Action"
- multiSelect: false
- options (show only applicable):
  - "Select new videos to extract" (if new_videos not empty)
  - "Check comment growth on existing" (if existing_videos not empty)
  - "Show more videos" (if page.has_more)
  - "Done"

### If "Select new videos to extract":

Ask user which videos by number. Accepts: "all", "1,3,5", "1-5".

AskUserQuestion: same as SKILL.md Step 1 (output type A–E, applied to all selected).

For each selected video, run standard SKILL.md flow (Step 0 → Step 3) sequentially.

### If "Check comment growth on existing":

```bash
python3 ./scripts/23_check_comment_growth.py "<output_directory>" {video_id_1} {video_id_2} ...
```

Show results:
| Title | Stored | Current | Growth |
|-------|--------|---------|--------|

Mark videos with >10% growth.

AskUserQuestion:
- question: "Re-extract comments for marked videos?"
- header: "Update"
- options:
  - "Yes, all marked"
  - "Let me choose"
  - "No, skip"

If yes: for each video, follow `./subskills/update_flow.md` "Re-extract comments" path.

### If "Show more videos":

```bash
python3 ./scripts/22_list_channel.py "<CHANNEL_URL>" "<output_directory>" --offset {current_offset + 20}
```

Return to Step C2.
