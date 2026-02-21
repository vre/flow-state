# DONE: Channel Browser: Cumulative Pagination + Batch Tracking

## Context

Channel browser v2.5.0 adds description enrichment, checkbox selection, and view growth detection. Three UX gaps remain:

1. "Show more" only available when no videos found — user cannot browse multiple pages before selecting
2. New videos and growth videos mixed in single multiSelect — max 4 options, no category routing
3. Batch extraction runs sequentially without progress visibility or recovery

## Goal

Add cumulative pagination, separate per-category selection, and TaskCreate-based batch tracking.

## Design

### Revised flow

```
C1: List page (--offset N)
C2: Enrich this page's new videos + check view growth for this page's existing
    Append results to accumulators: all_new_videos, all_growth_videos
C3: Cumulative summary + pagination prompt
    "Browsed 1–40 of 150 videos. 15 new, 4 with view growth."
    AskUserQuestion: "Select" / "Show more" (if has_more) / "Done"
    "Show more" → C1 with offset+20 (loop back)
C4: Selection UI — separate per category
    New videos: ≤4 → multiSelect, >4 → checkbox section in file
    Growth videos: ≤4 → multiSelect, >4 → checkbox section in file
    If either >4: both categories in single channel_selection.md
C5: Process selections
    New: ask output type A–E once
    TaskCreate per selected video (new: "Extract: {title}", growth: "Update: {title}")
    Run SKILL.md (new) / update_flow.md (growth) per task sequentially
    Mark each completed
```

### Accumulation

State lives in LLM conversation context:
- `all_new_videos: list[dict]` — enriched new videos across all pages
- `all_growth_videos: list[dict]` — growth-detected videos across all pages
- `current_offset: int` — increments by 20 per "Show more"

Each C1→C2 cycle processes only the current page, then appends to accumulators.

### Separate multiSelect per category

Two sequential AskUserQuestion dialogs when both ≤4:
1. "Select new videos to extract" (multiSelect, new videos only)
2. "Update comments for these?" (multiSelect, growth videos only)

Skip dialog if category is empty.

### TaskCreate batch tracking

Before starting extractions:
```
For each selected new video:
  TaskCreate: subject="Extract: {title}", activeForm="Extracting {title}"
For each selected growth video:
  TaskCreate: subject="Update comments: {title}", activeForm="Updating {title}"
```

Run sequentially. Mark completed after each. If session interrupts, task list shows remaining work.

## Files to Modify

- `subskills/channel_browse.md` — rewrite C3-C5 with cumulative pagination and batch tracking

## Constraints

- No code changes needed — all changes are in the skill markdown
- `parse_selection_checkboxes()` already returns `{video_id, section}` (v2.5.0)
- Accumulator state is conversation context only, not persisted

## Acceptance Criteria

- [ ] Videos accumulate across pages (not replaced)
- [ ] Summary shows cumulative totals after each "Show more"
- [ ] "Show more" available when `has_more=true`, regardless of selection count
- [ ] New videos and growth videos have separate multiSelect dialogs (≤4 each)
- [ ] If either category >4, single checkbox file with both sections
- [ ] Output type A–E asked once for all new videos
- [ ] TaskCreate per selected video before extraction loop
- [ ] Task marked completed per video as extraction finishes

## Dependency

Requires v2.5.0 channel browser (description enrich + checkbox selection + view growth).
