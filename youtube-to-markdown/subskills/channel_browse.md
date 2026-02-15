# Channel Browse

Browse a YouTube channel's videos, select new ones to extract, check view growth on existing.

## Step 1: List channel videos

```bash
python3 ./scripts/22_list_channel.py "<CHANNEL_URL>" "<output_directory>"
```

If `output_dir_suggestion` is set and no `existing_videos`:
  AskUserQuestion: "Create channel directory '{suggestion}'?"
  If yes: use suggested directory as `<output_directory>` for all subsequent steps.

Track the effective `limit` used for listing (default 50 unless `--limit` is used).

## Step 2: Analyze descriptions and activity

### Summarize new video descriptions with Haiku

If `new_videos` is not empty:

task_tool:
- subagent_type: "general-purpose"
- model: "haiku"
- prompt:
```text
<instructions>
You summarize YouTube video descriptions into one-line snippets.
Goal: one line per video, max 200 chars, capturing what the video is about.
Skip URLs, separator lines, timestamps, affiliate links, subscribe prompts, and gear lists because they do not describe video content.
If nothing meaningful remains after skipping junk, summarize from the title and append "(from title)".
</instructions>

<output_format>
One line per video, exactly:
VIDEO_ID: summary text

Example:
NCgdpbEvNVA: Explores why $650B in AI spending may be insufficient due to agentic inference demands, and which human skills survive the shift.
</output_format>

<context>
{for each new_video:
"- ID: {video_id} | Title: {title} | Description: {wrap_untrusted_content(description, 'description')}"}
</context>
```

Parse response by splitting lines and matching `VIDEO_ID: summary text`. Attach summaries back to `new_videos` by `video_id`.

### Check view growth on existing

If `existing_videos` is not empty:
Call `check_view_growth(existing_videos, output_dir)` from `lib/channel_listing`.
Input: `existing_videos` list (has `view_count` from flat-playlist).
Returns: videos with `>30%` view growth.

## Step 3: Present selection

Combine `new_videos` + `growth_videos`. `total = len(new_videos) + len(growth_videos)`.

### IF total == 0

Show page info: showing `{page.offset + 1}–{page.offset + page.count}`.

AskUserQuestion:
- question: "What next?"
- header: "Action"
- options (show only applicable):
  - "Show more videos" (if `page.has_more`)
  - "Done"

If "Show more videos": go to Step 5.

### IF total <= 4

AskUserQuestion:
- question: "Select videos to extract"
- header: "Videos"
- multiSelect: true
- options:
  - New video label: `"NEW: {title} ({views}, {duration}) ({video_id})"`
    description: Haiku summary from Step 2
  - Growth video label: `"GROWTH: {title} — views: {stored} → {current} (+{pct}%) ({video_id})"`

### IF total > 4

Write `<output_directory>/channel_selection.md`:

```markdown
# Channel: {name} — {n} new videos

Select videos to extract, then tell Claude to proceed.

## New videos
- [ ] **{title}** ({views}, {duration}) ({video_id})

  {haiku_summary_200chars}


## Videos with activity (>30% view growth)
- [ ] **{title}** — views: {stored} → {current} (+{pct}%) ({video_id})
```

Open file in user's editor. Tell user:
"Selection file opened. Check the videos you want, then say 'proceed'."

`STOP` — wait for user.

## Step 4: Process selections

Parse video IDs from selections:
- Checkbox file: `parse_selection_checkboxes(content)` → `[{video_id, section}]`
- multiSelect: extract `(VIDEO_ID)` from selected labels

New videos → SKILL.md Step 1 (output type A–D), then Step 0 → Step 3.
Growth videos → `./subskills/update_flow.md` re-extract path.

## Step 5: Show more videos

```bash
python3 ./scripts/22_list_channel.py "<CHANNEL_URL>" "<output_directory>" --offset {current_offset + limit} [--limit {limit}]
```

Return to Step 2.
