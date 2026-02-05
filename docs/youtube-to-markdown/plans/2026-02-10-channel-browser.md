# Channel Browser Feature

## Intent

Enable browsing a YouTube channel's videos, selecting new ones to extract, and identifying existing videos with significant comment growth for re-extraction. Single entry point: user provides a channel URL instead of a video URL.

## Goal

New subskill `channel_browse.md` + scripts `22_list_channel.py`, `23_check_comment_growth.py` + library `lib/channel_listing.py` that:
1. Lists channel videos with metadata (paginated, 20 per page)
2. Matches against locally extracted videos
3. On demand: checks existing videos for >10% comment growth
4. User selects videos for batch processing (same output mode for all)

## Constraints

### YouTube API / yt-dlp

- `--flat-playlist` returns per video: `id`, `title`, `view_count`, `duration`, `duration_string`, `description`, `channel_is_verified`
- `--flat-playlist` also returns per entry: `playlist_channel`, `playlist_channel_id`, `playlist_uploader_id`, `playlist_count` — these are the source of channel name/id/total
- **Does NOT return**: `comment_count`, `like_count`, `upload_date` in flat mode
- Comment count comparison requires per-video `--dump-single-json --skip-download` call (one per existing video)
- Rate limiting policy:
  - `--sleep-requests 0.5` for flat-playlist (lightweight, single JSON stream, entries arrive from one request)
  - `--sleep-requests 1` for individual video metadata fetches (each is a separate YouTube page load)
  - `-t sleep` for heavy operations (comments, transcripts) — yt-dlp builtin preset
- YouTube rate limit response: "rate-limited by YouTube for up to an hour" — no retry, wait
- Aggressive behavior risks: HTTP 429, or IP ban (up to a week observed)

### Current Architecture

- Videos stored flat: `youtube - {title} ({VIDEO_ID}).md`
- Video ID in filename enables matching: glob `youtube - * ({VIDEO_ID}).md`
- `check_existing.py` / `lib/check_existing.py` already handles single-video existence check
- `lib/check_existing.py:extract_metadata_from_file()` parses stored comment count from markdown
- `lib/prepare_update.py:parse_count()` converts formatted counts (1.2K, 2.2M) back to integers
- `lib/shared_types.py:format_count()` formats integers to compact form
- Numbered script convention: 10-19 extraction, 20-29 check/prepare, 30-39 processing, 40-49 management, 50-59 assembly

### Pagination

- yt-dlp `--flat-playlist` returns `playlist_count` (total videos) and `playlist_autonumber` per entry
- `--playlist-items 1:20` limits to first 20, `--playlist-items 21:40` for next page
- Channel videos ordered newest-first by default

### Output Directory Logic

- `22_list_channel.py` takes a concrete `OUTPUT_DIR` parameter
- Script searches for existing videos in OUTPUT_DIR and one level of subdirectories (depth 1 glob: `OUTPUT_DIR/*/youtube - * ({video_id}).md`)
- If videos found in a subdirectory, that subdirectory becomes the effective output dir
- If no existing videos found anywhere: script includes `output_dir_suggestion` field with `{channel_name} ({channel_id})/` — LLM asks user whether to create it
- Once output dir is resolved, all subsequent operations use that concrete path

## Design

### New Files

#### `scripts/22_list_channel.py`

CLI script. Single responsibility: list channel videos and match against local files.

```
Usage: 22_list_channel.py <CHANNEL_URL> <OUTPUT_DIR> [--offset N]
```

Behavior:
1. Run `yt-dlp --flat-playlist --dump-json --playlist-items {offset+1}:{offset+20} <CHANNEL_URL>` with `--sleep-requests 0.5`
2. Collect video entries (id, title, view_count, duration_string)
3. For each video, check if `youtube - * ({video_id}).md` exists in output_dir (or subdirs)
4. For existing videos, read stored comment count from markdown via `extract_metadata_from_file()`
5. Output JSON:

```json
{
  "channel": {
    "name": "3Blue1Brown",
    "id": "UCYO_jab_esuFRV4b17AJtAw",
    "url": "https://www.youtube.com/@3blue1brown/videos",
    "total_videos": 147,
    "verified": true
  },
  "page": {
    "offset": 0,
    "count": 20,
    "has_more": true
  },
  "new_videos": [
    {
      "video_id": "BHdbsHFs2P0",
      "title": "The Hairy Ball Theorem",
      "views": "1.9M",
      "duration": "29:40",
      "url": "https://www.youtube.com/watch?v=BHdbsHFs2P0"
    }
  ],
  "existing_videos": [
    {
      "video_id": "abc123",
      "title": "Some Older Video",
      "views": "500K",
      "duration": "15:22",
      "url": "https://www.youtube.com/watch?v=abc123",
      "stored_comments": "1.2K",
      "needs_comment_refresh": false
    }
  ],
  "output_dir_suggestion": "3Blue1Brown (UCYO_jab_esuFRV4b17AJtAw)"
}
```

Note: `needs_comment_refresh` is `false` at this stage — flat-playlist doesn't have comment_count. See step 2 below.

#### `scripts/23_check_comment_growth.py`

CLI script. Fetches current comment count for specific videos and compares to stored values.

```
Usage: 23_check_comment_growth.py <OUTPUT_DIR> <VIDEO_ID_1> [VIDEO_ID_2] ...
```

Behavior:
1. For each video ID, run `yt-dlp --dump-single-json --skip-download --sleep-requests 1 <url>` to get current `comment_count`
2. Read stored comment count from local markdown file
3. Calculate growth percentage
4. Output JSON:

```json
{
  "results": [
    {
      "video_id": "abc123",
      "title": "Some Video",
      "stored_comments": 1200,
      "current_comments": 1500,
      "growth_pct": 25.0,
      "needs_refresh": true
    }
  ],
  "rate_limit_note": "Checked 3 videos with 1s delay between requests"
}
```

Threshold: `needs_refresh = true` when `growth_pct > 10`.

#### `lib/channel_listing.py`

Library module with pure functions:

- `parse_channel_entry(entry: dict) -> dict` — extracts id, title, view_count, duration_string, url from a single yt-dlp flat-playlist JSON entry
- `parse_channel_metadata(entry: dict) -> dict` — extracts channel name, id, url, total_videos, verified from `playlist_*` fields of first entry
- `list_channel_videos(channel_url, offset, limit, cmd_runner)` → raw video list from yt-dlp
- `match_existing_videos(video_list, output_dir, search_depth=1)` → splits into new/existing, reads stored metadata for existing; searches output_dir and one level of subdirs
- `check_comment_growth(video_ids, output_dir, cmd_runner)` → fetches current counts, compares
- `find_output_dir(base_dir, channel_id)` → finds existing subdir with channel_id in name (depth 1), returns path or None
- `suggest_output_dir(base_dir, channel_name, channel_id)` → returns suggested subdir path string

#### `subskills/channel_browse.md`

LLM instructions for the channel browsing flow. Referenced from SKILL.md.

### Modified Files

#### `SKILL.md`

Add channel URL detection before Step 0:

```markdown
## Step -1: Detect input type

If URL is a channel URL (contains `/@`, `/channel/`, `/c/`, or `/user/`):
  Read and follow `./subskills/channel_browse.md`.

Otherwise: Continue to Step 0.
```

#### `subskills/channel_browse.md` (flow detail)

```
# Channel Browse

## Step C1: List channel videos

Run:
  python3 ./scripts/22_list_channel.py "<CHANNEL_URL>" "<output_directory>"

If output_dir_suggestion is set and no existing videos found:
  AskUserQuestion: "Create channel directory '{suggestion}'?"
  If yes: use suggested directory as output_directory for all subsequent steps.

## Step C2: Present video list

Show to user:

### {channel_name} ({total_videos} videos)

**New videos** (not yet extracted):
| # | Title | Views | Duration |
|---|-------|-------|----------|
| 1 | Title | 1.9M | 29:40 |
...

**Already extracted** ({count}):
| # | Title | Views | Duration | Stored comments |
|---|-------|-------|----------|-----------------|
| 1 | Title | 500K | 15:22 | 1.2K |
...

Page {N} of {total}. {has_more ? "More videos available." : ""}

## Step C3: User selection

AskUserQuestion:
- question: "What would you like to do?"
- header: "Action"
- multiSelect: false
- options (show only applicable):
  - "Select new videos to extract" (if new_videos not empty)
  - "Check comment growth on existing" (if existing_videos not empty)
  - "Show more videos" (if has_more)
  - "Done"

### If "Select new videos to extract":

Ask user which videos (by number). User can say "all", "1,3,5", or "1-5".

AskUserQuestion:
- question: "What do you want to extract from selected videos?"
- header: "Output"
- options: same as SKILL.md Step 1 (A-E)

For each selected video, run the standard SKILL.md flow (Step 0 → Step 3) with:
- `-t sleep` rate limiting on yt-dlp calls
- Sequential processing (one video at a time, as per existing SKILL.md rule)

### If "Check comment growth on existing":

Run:
  python3 ./scripts/23_check_comment_growth.py "<output_directory>" video_id_1 video_id_2 ...

Show results:
| Title | Stored | Current | Growth |
|-------|--------|---------|--------|
| Video | 1.2K | 1.5K | +25% ⬆ |
| Video | 800 | 820 | +2.5% |

Videos with >10% growth are marked.

AskUserQuestion:
- question: "Re-extract comments for marked videos?"
- header: "Update"
- options:
  - "Yes, all marked"
  - "Let me choose"
  - "No, skip"

If yes: for each video, run update_flow.md "Re-extract comments" path.

### If "Show more videos":

Run 22_list_channel.py with --offset {current_offset + 20}
Return to Step C2.
```

## Acceptance Criteria

1. `22_list_channel.py` correctly lists channel videos with pagination (--playlist-items)
2. Existing videos matched by VIDEO_ID in filenames (any subdirectory depth 1)
3. `23_check_comment_growth.py` correctly identifies >10% comment growth
4. Rate limiting: `--sleep-requests 0.5` for flat-playlist, `--sleep-requests 1` for individual metadata
5. Channel subdirectory suggested when no existing videos found
6. Selected new videos processed sequentially using existing SKILL.md flow
7. Comment re-extraction uses existing update_flow.md path
8. Pagination works: offset 0→20→40 etc.

## Validation Approach

1. **Unit tests** for `lib/channel_listing.py`:
   - `match_existing_videos` with mock directory contents
   - `check_comment_growth` with mock stored/current values (threshold boundary: 9%, 10%, 11%)
   - `find_output_dir` with/without existing subdirectories
   - `parse_channel_entry` field extraction from yt-dlp JSON
   - `parse_channel_metadata` extracts channel info from playlist_* fields

2. **Integration test** with `claude -p`:
   - Run `22_list_channel.py` against a known small channel
   - Verify JSON output structure and field completeness
   - Verify pagination with --offset

3. **Manual test** with `claude -p`:
   - Full channel browse flow on a channel with some already-extracted videos
   - Verify comment growth detection end-to-end

## Implementation Order

1. `lib/channel_listing.py` + unit tests
2. `scripts/22_list_channel.py` + integration test
3. `scripts/23_check_comment_growth.py` + unit tests
4. `subskills/channel_browse.md`
5. `SKILL.md` modification (channel URL detection)
6. Manual end-to-end test
7. Update: CHANGELOG.md, TODO.md, README.md, marketplace.json version, pyproject.toml version

## Worktree

```
git worktree add .worktrees/channel-browser -b feature/channel-browser
```
