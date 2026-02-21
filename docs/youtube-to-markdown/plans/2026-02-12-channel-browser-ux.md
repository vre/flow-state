# DONE: Channel Browser UX: Description Enrich + Checkbox Selection

## Context

Channel browser v2.4.0 lists 20 videos per page with title/views/duration. Two problems:
1. Title alone is insufficient to decide what to extract — need description snippet
2. AskUserQuestion supports max 4 options — unusable for 20 videos

Additionally, comment growth check currently requires `yt-dlp --dump-single-json` per video (~1s each). View count from `--flat-playlist` is a free proxy: if views haven't grown >30%, comments likely haven't either.

## Goal

Improve channel browser video selection UX and replace per-video comment count fetching with view-growth proxy.

## Situational Context

### Current `parse_channel_entry()` (`lib/channel_listing.py:18-39`)

```python
def parse_channel_entry(entry: dict) -> dict:
    view_count = entry.get("view_count")
    views = format_count(view_count) if view_count is not None else "N/A"
    return {
        "video_id": entry["id"],
        "title": entry.get("title", "Untitled"),
        "views": views,           # formatted string: "2.3M"
        "duration": entry.get("duration_string", "N/A"),
        "url": entry.get("url") or entry.get("webpage_url", ""),
    }
```

Problem: `views` is formatted string only. Need raw `view_count` int for growth comparison.

### `extract_metadata_from_file()` (`lib/check_existing.py:152-201`)

Returns dict from stored summary file:
```python
{"title": str|None, "views": str|None, "likes": str|None,
 "comments": str|None, "published": str|None, "extracted": str|None}
```

`views` is formatted string ("2.3M" or "2,183,167"). Convert back with `parse_count()`.

### `parse_count()` (`lib/prepare_update.py:22-36`)

```python
def parse_count(value: str | None) -> int | None:
    # "2.3M" → 2300000, "71.2K" → 71200, "2,183,167" → 2183167, None → None
```

### `content_safety.wrap_untrusted_content()` (`lib/content_safety.py`)

```python
wrap_untrusted_content(text: str, content_type: str) -> str
# Wraps in <untrusted_{type}_content> XML tags with injection warning
```

Use for video descriptions: `wrap_untrusted_content(desc, "description")`

### Current `channel_browse.md` flow

```
C1: Run 22_list_channel.py → JSON with channel meta, new_videos, existing_videos, page
C2: Present tables (new videos | already extracted)
C3: AskUserQuestion → "Select new videos" | "Check comment growth" | "Show more" | "Done"
    - Select: ask for numbers + output type A-E → run extraction per video
    - Comment growth: run 23_check_comment_growth.py → table → offer re-extract
    - Show more: re-run with --offset
```

### `22_list_channel.py` output JSON

```json
{
  "channel": {"name": str, "id": str, "url": str, "total_videos": int, "verified": bool},
  "page": {"offset": int, "count": int, "has_more": bool},
  "new_videos": [{"video_id": str, "title": str, "views": str, "duration": str, "url": str}],
  "existing_videos": [{"video_id": str, "title": str, "views": str, "duration": str, "url": str, "stored_comments": str}]
}
```

## Design

### Flow

```
1. --flat-playlist → video list (existing, ~5s)
2. match_existing_videos() → new/existing split (existing)
3. NEW: For new videos → enrich description via yt-dlp --dump-json (~1-2s/video)
4. NEW: For existing videos → compare flat-playlist view_count vs stored views (free)
5. NEW: Build selection — both sections before presenting:
   a. New videos section (with description snippet)
   b. View growth section (>30% growth)
6. NEW: Present selection:
   ≤4 total items → AskUserQuestion multiSelect
   >4 total items → write markdown checkbox file, open in editor, wait for user
```

### Markdown Checkbox File Format

Written to `<output_dir>/channel_selection.md`, opened in user's editor:

```markdown
# Channel: {name} — {n} new videos

Select videos to extract, then tell Claude to proceed.

## New videos
- [ ] **{title}** ({views}, {duration}) ({video_id})
  {description_snippet_200chars}
- [ ] **{title}** ({views}, {duration}) ({video_id})
  {description_snippet_200chars}

## Videos with activity (>30% view growth)
- [ ] **{title}** — views: {stored} → {current} (+{pct}%) ({video_id})
```

Claude reads file back, matches `- [x]` lines by `({video_id})` suffix, processes checked items.

### Enrich Script

New script `24_enrich_metadata.py`:

```
Usage: 24_enrich_metadata.py <VIDEO_ID_1> [VIDEO_ID_2] ...
Output: JSON array of {video_id, description}
```

- `yt-dlp --dump-json --skip-download` per video
- 1s delay between requests (rate limit)
- Returns description (first 200 chars) — content for informed selection
- Description wrapped with `content_safety.wrap_untrusted_content(text, "description")`
- Used for new videos only

### View Growth Comparison

New function `check_view_growth()` in `lib/channel_listing.py`:

```python
def check_view_growth(existing_videos: list[dict], output_dir: Path, threshold: float = 0.3) -> list[dict]:
    """Compare flat-playlist view_count vs stored views. Return videos with >threshold growth."""
```

- Input: existing_videos (needs raw `view_count` from flat-playlist) + output_dir
- Load stored views via `extract_metadata_from_file()` → `parse_count()` to convert
- Compare: `(current - stored) / stored > threshold`
- Return list with `{video_id, title, stored_views, current_views, growth_pct}`
- No API calls needed

### Changes to `parse_channel_entry()`

Add `view_count` raw int alongside formatted `views`:

```python
return {
    "video_id": entry["id"],
    "title": entry.get("title", "Untitled"),
    "views": views,
    "view_count": view_count,  # NEW: raw int for comparison
    "duration": entry.get("duration_string", "N/A"),
    "url": entry.get("url") or entry.get("webpage_url", ""),
}
```

### Changes to `channel_browse.md`

Replace Steps C2-C3:

```
C2: Enrich + analyze
  Run 24_enrich_metadata.py with new video IDs → descriptions
  Run check_view_growth() on existing videos → growth list

C3: Present selection
  Combine new videos + growth videos into total selection list

  IF total <= 4:
    AskUserQuestion multiSelect with video titles + snippet/growth info
  ELSE:
    Write channel_selection.md to output_dir (both sections)
    Open file in user's editor
    Tell user: "Selection file opened. Check the videos you want, then say 'proceed'."
    STOP — wait for user

C4: Process selections
  Read channel_selection.md (if used), parse [x] lines by (video_id)
  For new videos: ask output type A-E, run standard extraction (Step 0 → Step 3)
  For growth videos: run comment re-extraction via update_flow.md
```

## Files to Create

- `scripts/24_enrich_metadata.py` — description fetcher per video

## Files to Modify

- `subskills/channel_browse.md` — new C2-C4 flow
- `lib/channel_listing.py` — add `check_view_growth()`, add `view_count` int to `parse_channel_entry()`
- `scripts/22_list_channel.py` — include raw `view_count` in output JSON

## Constraints

- Enrichment cost: ~20 new videos × 1-2s = 20-40s. Acceptable as one-time cost for informed selection.
- Description from yt-dlp is untrusted user content — must wrap with content_safety
- Rate limit: 1s between yt-dlp calls (existing pattern in `23_check_comment_growth.py`)
- `parse_count()` is lossy: "2.3M" → 2300000 (actual could be 2,347,891). View growth threshold of 30% absorbs this imprecision.

## Validation

- Manual test with channel that has mix of new + already-extracted videos
- Verify existing extractions with old view counts trigger view-growth detection
- Verify checkbox file opens in editor and parsed correctly after user edits

## Acceptance Criteria

- [x] New videos show description snippet (≤200 chars) in selection UI
- [x] ≤4 total items → AskUserQuestion multiSelect dialog
- [x] >4 total items → markdown checkbox file written, opened in editor, Claude waits
- [x] Video IDs in parentheses on each checkbox line for reliable parsing
- [x] Existing videos with >30% view growth shown as refresh candidates
- [x] No per-video API call for comment counts in listing phase
- [x] Checked items parsed correctly from markdown file by video_id
- [x] Tests for: check_view_growth(), enrich output parsing, checkbox parsing
- [+] Added regression test for `22_list_channel.py` JSON passthrough of `view_count` for both new and existing videos
- [+] Added boundary tests for lossy stored view formats (`1.5M` exact 30% and `2,183,167` comma format)
- [+] Added `None` description handling test for `24_enrich_metadata.py`
- [>] Manual test: channel with existing extractions that have grown — deferred to merge phase

## Bugs fixed post-review

- `parse_selection_checkboxes()` now returns `list[dict]` with `{video_id, section}` — enables routing new vs growth videos in C5
- `24_enrich_metadata.py` returns raw description text — content_safety wrapping is caller's responsibility (user-facing file vs LLM context)
- `parse_selection_checkboxes()` now parses only top-level checkbox rows and top-level section headers (prevents description-line checkbox/header injection)
- `_find_summary_for_video_id()` now matches date-prefixed summary filenames (`*youtube - * (VIDEO_ID).md`)
- `CHECKED_SELECTION_RE` switched to non-greedy capture around title/body text for deterministic matching
- `24_enrich_metadata.py` now normalizes `\\r`/`\\n` to spaces before truncation to keep snippets single-line in selection files
- `subskills/channel_browse.md` now specifies label→`{video_id, section}` mapping for multiSelect routing (AskUserQuestion returns labels, not structured objects)
- `scripts/22_list_channel.py` now documents raw `view_count` passthrough in output contract

## Follow-up

Cumulative pagination, separate per-category multiSelect, and TaskCreate batch tracking → separate plan: `2026-02-13-channel-browser-pagination.md`

## Dependency

None — builds on existing v2.4.0 channel browser.

## Reflection

What went well: External-review findings were converted directly into reproducible tests first, then fixed. Parser and lookup hardening were small, local changes in `lib/channel_listing.py` with no cross-module side effects. Test suite now covers the previously ambiguous contracts (`view_count` passthrough, threshold boundary behavior, `description=None` handling). All 31 tests pass.

What changed from plan: No structural flow changes. Post-review hardening added: top-level-only checkbox parsing, date-prefixed summary matching, single-line description normalization, and explicit multiSelect label mapping guidance in `channel_browse.md`.

Lessons: Treat skill markdown as executable contract and test the contract edges in Python where possible. For parser/security-sensitive paths, prefer tests that replicate attacker-controlled formatting (indentation, fake headers, checkbox-like text) before adjusting regex logic.
