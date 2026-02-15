# Channel Browse

Browse a YouTube channel's videos, select new ones to extract, check view growth on existing.

## Step C1: List channel videos

```bash
python3 ./scripts/22_list_channel.py "<CHANNEL_URL>" "<output_directory>"
```

If `output_dir_suggestion` is set and no `existing_videos`:
  AskUserQuestion: "Create channel directory '{suggestion}'?"
  If yes: use suggested directory as `<output_directory>` for all subsequent steps.

## Step C2: Enrich and analyze

### Enrich new videos with descriptions

If `new_videos` not empty:

```bash
python3 ./scripts/24_enrich_metadata.py {video_id_1} {video_id_2} ...
```

Returns JSON array of `{video_id, description}` — single-line text ≤200 chars.
Match descriptions to new_videos by video_id.
Use raw text in checkbox file (user-facing). Wrap with `content_safety.wrap_untrusted_content(desc, "description")` only when passing to LLM context.

### Check view growth on existing

If `existing_videos` not empty:

Call `check_view_growth(existing_videos, output_dir)` from `lib/channel_listing`.
Input: existing_videos list (has `view_count` raw int from flat-playlist).
Returns: list of videos with >30% view growth.

No API calls needed — compares flat-playlist view_count vs stored views.

## Step C3: Present selection

Combine new videos + growth videos into total selection list.

Count total = len(new_videos) + len(growth_videos).

### IF total == 0

Show page info: showing {page.offset + 1}–{page.offset + page.count}.

AskUserQuestion:
- question: "What next?"
- header: "Action"
- options (show only applicable):
  - "Show more videos" (if page.has_more)
  - "Done"

If "Show more videos": go to Step C5.

### IF total <= 4

AskUserQuestion:
- question: "Select videos to extract"
- header: "Videos"
- multiSelect: true
- options: build `selection_items` first; each item has `{label, description, video_id, section}`:
  - New video label: "NEW: {title} ({views}, {duration}) ({video_id})"
  - Growth video label: "GROWTH: {title} — views: {stored} → {current} (+{pct}%) ({video_id})"
  - Use description snippets only in option description field, not in label.

### IF total > 4

Write `<output_directory>/channel_selection.md`:

```markdown
# Channel: {name} — {n} new videos

Select videos to extract, then tell Claude to proceed.

## New videos
- [ ] **{title}** ({views}, {duration}) ({video_id})
  {description_snippet_200chars}

## Videos with activity (>30% view growth)
- [ ] **{title}** — views: {stored} → {current} (+{pct}%) ({video_id})
```

Open file in user's editor. Tell user:
"Selection file opened. Check the videos you want, then say 'proceed'."

`STOP` — wait for user.

## Step C4: Process selections

### Parse selections

If checkbox file was used:
  Read `<output_directory>/channel_selection.md`.
  Call `parse_selection_checkboxes(content)` from `lib/channel_listing` → list of `{video_id, section}`.
  Split by section: items where `section=="new"` → new_ids, `section=="growth"` → growth_ids.

If multiSelect was used:
  Build `selection_map` from exact option label to `{video_id, section}` using C3 `selection_items`.
  For each selected label from AskUserQuestion, resolve via `selection_map` and route to new_ids or growth_ids.

### Extract new videos (new_ids)

AskUserQuestion: same as SKILL.md Step 1 (output type A–E, applied to all selected).
For each video, run standard SKILL.md flow (Step 0 → Step 3) sequentially.

### Re-extract growth videos (growth_ids)

For each video, follow `./subskills/update_flow.md` "Re-extract comments" path.

## Step C5: Show more videos

```bash
python3 ./scripts/22_list_channel.py "<CHANNEL_URL>" "<output_directory>" --offset {current_offset + 20}
```

Return to Step C2.
