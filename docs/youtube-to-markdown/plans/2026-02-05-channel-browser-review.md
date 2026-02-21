# DONE: Channel Browser — Implementation Review

Per-file diff with rationale for each change. Branch `feature/channel-browser` vs `main` (8 commits, 10 files, +925/-5 lines).

---

## 1. `youtube-to-markdown/lib/channel_listing.py` (NEW, 254 lines)

Core library. All pure functions except `list_channel_videos` (subprocess call).

```diff
+"""
+Channel listing and video matching library.
+
+Lists channel videos via yt-dlp flat-playlist, matches against
+locally extracted files, and checks comment growth.
+"""
+
+import json
+import re
+import subprocess
+from pathlib import Path
+
+from lib.check_existing import extract_metadata_from_file
+from lib.prepare_update import parse_count
+from lib.shared_types import format_count
```

**Why:** Reuses three existing functions instead of reimplementing:
- `extract_metadata_from_file` — parses stored comments/views from markdown (already handles both old and new metadata formats)
- `parse_count` — converts "1.2K" → 1200 (needed for growth percentage math)
- `format_count` — converts 1946655 → "1.9M" (consistent with existing display format)

```diff
+def parse_channel_entry(entry: dict) -> dict:
+    """Parse a single yt-dlp flat-playlist JSON entry into normalized dict."""
+    view_count = entry.get("view_count")
+    if view_count is not None:
+        views = format_count(view_count)
+    else:
+        views = "N/A"
+
+    return {
+        "video_id": entry["id"],
+        "title": entry.get("title", "Untitled"),
+        "views": views,
+        "duration": entry.get("duration_string", "N/A"),
+        "url": entry.get("url") or entry.get("webpage_url", ""),
+    }
```

**Why:** Normalizes raw yt-dlp JSON into a stable structure the LLM presents to the user. Explicit `None` check on `view_count` because `0` is a valid count (new/unlisted videos) but `None` means the field wasn't returned at all. The `or` chain on url handles inconsistent yt-dlp output where sometimes `url` is None but `webpage_url` exists.

```diff
+def parse_channel_metadata(entry: dict) -> dict:
+    """Extract channel-level metadata from a flat-playlist entry."""
+    return {
+        "name": entry.get("playlist_channel"),
+        "id": entry.get("playlist_channel_id"),
+        "url": entry.get("playlist_webpage_url"),
+        "total_videos": entry.get("playlist_count") or entry.get("n_entries"),
+        "verified": entry.get("channel_is_verified", False),
+    }
```

**Why:** Channel metadata comes from `playlist_*` fields, which are identical on every entry in the flat-playlist output. Extracted from first entry only. The `or` fallback on `n_entries` exists because `playlist_count` is `None` when using `--playlist-items` pagination — discovered empirically during development.

```diff
+def _normalize_channel_url(url: str) -> str:
+    """Ensure channel URL points to /videos tab.
+
+    YouTube channel URLs without /videos return Videos + Shorts + Live
+    as separate playlists, breaking --playlist-items pagination.
+    """
+    url = url.rstrip("/")
+    if url.endswith("/videos"):
+        return url
+    for tab in ("/shorts", "/live", "/streams", "/playlists", "/community"):
+        if url.endswith(tab):
+            url = url[: -len(tab)]
+            break
+    return url + "/videos"
```

**Why:** Critical bug prevention. A bare channel URL like `youtube.com/@chan` causes yt-dlp to return Videos + Shorts + Live as three separate sub-playlists. With `--playlist-items 1:20`, you'd get items 1-20 from *each* sub-playlist (up to 60 entries), making pagination unpredictable. Appending `/videos` forces a single playlist. The tab stripping handles users pasting URLs from other channel tabs.

```diff
+def list_channel_videos(
+    channel_url: str, offset: int = 0, limit: int = 20,
+) -> list[dict]:
+    url = _normalize_channel_url(channel_url)
+    start = offset + 1
+    end = offset + limit
+    result = subprocess.run(
+        [
+            "yt-dlp",
+            "--flat-playlist",
+            "--dump-json",
+            "--sleep-requests", "0.5",
+            "--playlist-items", f"{start}:{end}",
+            url,
+        ],
+        capture_output=True, text=True, timeout=120,
+    )
+
+    if result.returncode != 0 and not result.stdout.strip():
+        raise RuntimeError(
+            f"yt-dlp failed: {result.stderr.strip() or 'unknown error'}"
+        )
+
+    entries = []
+    for line in result.stdout.strip().split("\n"):
+        line = line.strip()
+        if not line:
+            continue
+        try:
+            entries.append(json.loads(line))
+        except json.JSONDecodeError:
+            continue  # skip yt-dlp warning/error lines mixed with JSON
+
+    return entries
```

**Why:**
- `--sleep-requests 0.5` — flat-playlist is lightweight (metadata only, no page loads), but 0s would be aggressive. 0.5s is a balance between speed and YouTube tolerance.
- `offset + 1` — yt-dlp uses 1-indexed playlist items, API uses 0-indexed offset.
- `timeout=120` — channels with restricted videos can stall; 2 minutes is generous but bounded.
- Error handling: `returncode != 0 AND not stdout` — yt-dlp sometimes returns partial stdout with non-zero exit (e.g., geo-restricted videos mixed in). We keep whatever it gave us.
- `json.JSONDecodeError` catch — yt-dlp intermixes warning lines like `[youtube:tab] Extracting...` with JSON output on stdout.

```diff
+def _is_summary_file(path: Path) -> bool:
+    """Check if file is a main summary (not backup, comments, or transcript)."""
+    name = path.name
+    return "_backup_" not in name and " - comments " not in name and " - transcript " not in name
```

**Why:** Extracted helper to deduplicate filter logic. The glob `youtube - * ({video_id}).md` also matches backup files (`_backup_20250601`), comment files (`- comments`), and transcript files (`- transcript`). Without this filter, a single video could match 3-4 files. Extracted as a named function during review — originally the condition was inlined in two places.

```diff
+def _find_summary_for_video_id(video_id: str, output_dir: Path) -> Path | None:
+    """Find summary file for a video ID in output_dir and one level of subdirs."""
+    dirs = [output_dir] + [d for d in output_dir.iterdir() if d.is_dir()]
+    for d in dirs:
+        for f in d.glob(f"youtube - * ({video_id}).md"):
+            if _is_summary_file(f):
+                return f
+    return None
```

**Why:** Depth-1 search: output_dir itself plus immediate subdirectories. The convention is `output_dir/ChannelName (UCXXX)/youtube - Title (videoID).md`. Deeper recursion would be wasteful and risk false matches. Returns first match — there should only be one summary per video ID.

```diff
+def match_existing_videos(
+    video_list: list[dict], output_dir: Path,
+) -> tuple[list[dict], list[dict]]:
+    new_videos = []
+    existing_videos = []
+    for video in video_list:
+        video_id = video["video_id"]
+        summary_file = _find_summary_for_video_id(video_id, output_dir)
+        if summary_file is None:
+            new_videos.append(video)
+        else:
+            metadata = extract_metadata_from_file(summary_file.read_text())
+            existing_video = {**video, "stored_comments": metadata.get("comments")}
+            existing_videos.append(existing_video)
+    return new_videos, existing_videos
```

**Why:** Clean split into two lists — the LLM displays them in separate tables. `stored_comments` is attached to existing videos so the LLM can show it without re-reading files. Uses `extract_metadata_from_file` which handles both the old format (`Views: 5,000 | Likes: 200`) and new format (`Engagement: 5K views · 200 likes · 50 comments`).

```diff
+def check_comment_growth(
+    current_counts: dict[str, int], output_dir: Path,
+) -> list[dict]:
+    results = []
+    for video_id, current in current_counts.items():
+        summary_file = _find_summary_for_video_id(video_id, output_dir)
+        if summary_file is None:
+            continue
+        metadata = extract_metadata_from_file(summary_file.read_text())
+        stored = parse_count(metadata.get("comments"))
+        if stored is None or stored == 0:
+            results.append({
+                "video_id": video_id,
+                "title": metadata.get("title", "Unknown"),
+                "stored_comments": stored,
+                "current_comments": current,
+                "growth_pct": 0.0,
+                "needs_refresh": False,
+            })
+            continue
+        growth_pct = ((current - stored) / stored) * 100
+        results.append({
+            "video_id": video_id,
+            "title": metadata.get("title", "Unknown"),
+            "stored_comments": stored,
+            "current_comments": current,
+            "growth_pct": round(growth_pct, 1),
+            "needs_refresh": growth_pct > 10,
+        })
+    return results
```

**Why:** Design deviation from plan: the plan had `check_comment_growth(video_ids, output_dir, cmd_runner)` doing IO internally. Instead, it takes pre-fetched `current_counts: dict[str, int]` — separating IO from logic. This makes the function pure (testable without mocking subprocess) and pushes the IO responsibility to the script layer where it belongs.

`parse_count()` normalizes stored comments to int (handles "1.2K" → 1200, "50" → 50, None → None). This was a review fix — originally raw strings were compared to ints, which would fail on formatted counts.

`stored == 0` guard prevents division by zero. `growth_pct > 10` (strict) means exactly 10% is NOT flagged — the requirement was ">10% growth".

```diff
+def find_output_dir(base_dir: Path, channel_id: str) -> Path | None:
+    if not base_dir.exists():
+        return None
+    for item in base_dir.iterdir():
+        if item.is_dir() and channel_id in item.name:
+            return item
+    return None
```

**Why:** `base_dir.exists()` check added after discovering that `iterdir()` raises `FileNotFoundError` on non-existent paths. The user might point to a directory they haven't created yet. Simple substring match on channel_id — channel IDs are globally unique (UC + 22 chars).

```diff
+def suggest_output_dir(base_dir: Path, channel_name: str, channel_id: str) -> Path:
+    clean_name = re.sub(r'[<>:"/\\|?*]', '', channel_name)
+    clean_name = clean_name.replace("..", "")
+    return base_dir / f"{clean_name} ({channel_id})"
```

**Why:** Sanitizes filesystem-unsafe characters from channel names (Windows + POSIX union set). The `..` removal prevents path traversal — a channel named `../../etc` would otherwise escape the base directory. Code review finding.

---

## 2. `youtube-to-markdown/scripts/22_list_channel.py` (NEW, 105 lines)

```diff
+#!/usr/bin/env python3
+"""
+Lists YouTube channel videos and matches against local extractions.
+
+Usage: 22_list_channel.py <CHANNEL_URL> <OUTPUT_DIR> [--offset N]
+Output: JSON with channel metadata, new/existing videos, pagination info.
+
+Rate limiting: uses --sleep-requests 0.5 for flat-playlist listing.
+"""
```

**Why:** Self-documenting header per CLAUDE.md guidelines. The rate limit note tells the LLM what to expect without reading lib internals.

```diff
+def main() -> None:
+    offset = 0
+    positional = []
+    i = 1
+    while i < len(sys.argv):
+        if sys.argv[i] == "--offset" and i + 1 < len(sys.argv):
+            offset = int(sys.argv[i + 1])
+            i += 2
+        else:
+            positional.append(sys.argv[i])
+            i += 1
+    args = positional
```

**Why:** Custom arg parsing because `--offset` can appear anywhere between positional args (the LLM might generate it before or after OUTPUT_DIR). `argparse` would work but adds overhead for two positional + one optional flag. Keeps the script thin per CLAUDE.md "thin main() glue".

```diff
+    channel_url = args[0]
+    output_dir = Path(args[1])
+    offset = max(0, offset)
+    limit = 20
```

**Why:** `max(0, offset)` clamps negative offsets to 0 — defensive input validation. The LLM might pass `--offset -1` by mistake. Review finding.

```diff
+    # Resolve output directory
+    effective_dir = output_dir
+    if output_dir.exists() and channel_meta["id"]:
+        found_dir = find_output_dir(output_dir, channel_meta["id"])
+        if found_dir:
+            effective_dir = found_dir
+
+    # Match against existing files
+    if effective_dir.exists():
+        new_videos, existing_videos = match_existing_videos(videos, effective_dir)
+    else:
+        new_videos, existing_videos = videos, []
```

**Why:** Two-level directory resolution: first check if output_dir contains a channel subdirectory (e.g., `output/3Blue1Brown (UCYO_jab)/`), then match videos there. The `exists()` guard on `effective_dir` handles the case where the user points to a not-yet-created directory — all videos are "new" by definition.

```diff
+    # Build suggestion if no existing videos found anywhere
+    suggestion = None
+    if not existing_videos and channel_meta["name"] and channel_meta["id"]:
+        suggestion = str(suggest_output_dir(output_dir, channel_meta["name"], channel_meta["id"]))
+
+    # has_more: if we got exactly limit entries, there's likely more
+    has_more = len(videos) == limit
```

**Why:** `output_dir_suggestion` only appears when zero existing videos found — if any exist, we already know where they live. `has_more` heuristic: if we got exactly 20 entries, there are probably more. If fewer, we hit the end. This avoids a separate count query since `playlist_count` is unreliable with `--playlist-items`.

---

## 3. `youtube-to-markdown/scripts/23_check_comment_growth.py` (NEW, 88 lines)

```diff
+"""
+Checks comment growth for existing videos by comparing stored vs current counts.
+
+Usage: 23_check_comment_growth.py <OUTPUT_DIR> <VIDEO_ID_1> [VIDEO_ID_2] ...
+Output: JSON with per-video growth analysis.
+
+Rate limiting: 1s Python-level delay between individual video metadata fetches.
+"""
```

**Why:** Docstring explicitly says "Python-level delay" not "yt-dlp sleep flag". This was a review fix — the original said `--sleep-requests 1` which was misleading since the actual implementation uses `time.sleep(1)`. The difference matters: `time.sleep` is between separate yt-dlp invocations, `--sleep-requests` is within a single invocation.

```diff
+def fetch_comment_counts(video_ids: list[str]) -> dict[str, int]:
+    counts: dict[str, int] = {}
+    for i, vid in enumerate(video_ids):
+        if i > 0:
+            time.sleep(1)
+        url = f"https://www.youtube.com/watch?v={vid}"
+        result = subprocess.run(
+            [
+                "yt-dlp",
+                "--dump-single-json",
+                "--skip-download",
+                "--no-write-comments",
+                url,
+            ],
+            capture_output=True, text=True, timeout=60,
+        )
+        if result.returncode == 0:
+            try:
+                data = json.loads(result.stdout)
+                count = data.get("comment_count")
+                if count is not None:
+                    counts[vid] = count
+            except json.JSONDecodeError:
+                print(f"WARNING: Failed to parse metadata for {vid}", file=sys.stderr)
+    return counts
```

**Why:** IO function in the script, not the library — keeps lib pure and testable. `time.sleep(1)` between requests (not on first) because each `--dump-single-json` makes a full YouTube page load. `--no-write-comments` avoids downloading comment data (we only need the count from page metadata). `json.JSONDecodeError` catch was a review finding — yt-dlp can produce garbled output on network issues. Failed fetches are silently skipped (the video just won't appear in results, which is correct — no data means no growth comparison).

---

## 4. `youtube-to-markdown/subskills/channel_browse.md` (NEW, 81 lines)

```diff
+# Channel Browse
+
+Browse a YouTube channel's videos, select new ones to extract, check comment growth on existing.
+
+## Step C1: List channel videos
+
+```bash
+python3 ./scripts/22_list_channel.py "<CHANNEL_URL>" "<output_directory>"
+```
+
+If `output_dir_suggestion` is set and no `existing_videos`:
+  AskUserQuestion: "Create channel directory '{suggestion}'?"
+  If yes: use suggested directory as `<output_directory>` for all subsequent steps.
```

**Why:** The LLM subskill follows CLAUDE.md guidelines: direct instructions, no fluff, placeholders for runtime values. Scripts are referenced by relative path. The directory suggestion flow prevents creating orphan directories — only asked if this is a genuinely new channel.

```diff
+## Step C2: Present video list
+
+### {channel.name} ({channel.total_videos or page.count + "+"} videos) {channel.verified ? "✓" : ""}
+
+**New videos** (not yet extracted):
+| # | Title | Views | Duration |
+
+**Already extracted** ({count}):
+| # | Title | Views | Duration | Stored comments |
+
+Page info: showing {page.offset + 1}–{page.offset + page.count}. {page.has_more ? "More available." : "End of list."}
+
+Omit empty tables.
```

**Why:** Markdown table template — the LLM substitutes actual values. "Omit empty tables" prevents showing an empty "Already extracted" section for new channels. Two separate tables because they serve different purposes: new videos for extraction selection, existing for comment growth monitoring.

```diff
+## Step C3: User selection
+
+AskUserQuestion:
+- options (show only applicable):
+  - "Select new videos to extract" (if new_videos not empty)
+  - "Check comment growth on existing" (if existing_videos not empty)
+  - "Show more videos" (if page.has_more)
+  - "Done"
```

**Why:** Dynamic options — only show what's relevant. A channel with all videos already extracted shouldn't offer "Select new videos". This reduces cognitive load. The option structure maps 1:1 to the three actions in the plan.

```diff
+### If "Check comment growth on existing":
+
+```bash
+python3 ./scripts/23_check_comment_growth.py "<output_directory>" {video_id_1} {video_id_2} ...
+```
+
+If yes: for each video, follow `./subskills/update_flow.md` "Re-extract comments" path.
```

**Why:** Delegates to existing `update_flow.md` for comment re-extraction instead of reimplementing. DRY across subskills. The growth check is on-demand (Step C3 option) rather than automatic because it requires individual yt-dlp calls — potentially slow for channels with many existing videos.

---

## 5. `youtube-to-markdown/SKILL.md` (MODIFIED)

```diff
-description: Use when user asks YouTube video extraction, get, fetch, transcripts, subtitles, or captions. Writes video details and transcription into structured markdown file.
+description: Use when user asks YouTube video extraction, get, fetch, transcripts, subtitles, or captions, or channel browsing. Writes video details and transcription into structured markdown file.
```

**Why:** Adds "channel browsing" as a trigger phrase so the Claude Code skill matcher routes channel URLs to this skill.

```diff
+## Step -1: Detect input type
+
+If URL is a channel URL (contains `/@`, `/channel/`, `/c/`, or `/user/`, but NOT `watch?v=`):
+  Read and follow `./subskills/channel_browse.md`.
+
+Otherwise: Continue to Step 0.
```

**Why:** Step -1 (before 0) because detection must happen before any video-specific logic. The `NOT watch?v=` exclusion handles edge cases like `youtube.com/@chan` which is a channel but `youtube.com/watch?v=X` with a channel in the referrer is a video. The four URL patterns cover all YouTube channel URL formats: `/@handle`, `/channel/UCXXX`, `/c/customname`, `/user/oldformat`.

---

## 6. `tests/youtube-to-markdown/test_channel_listing.py` (NEW, 356 lines, 33 tests)

```diff
+SAMPLE_FLAT_ENTRY = {
+    "id": "BHdbsHFs2P0",
+    "title": "The Hairy Ball Theorem",
+    "view_count": 1946655,
+    "duration": 1780.0,
+    "duration_string": "29:40",
+    "url": "https://www.youtube.com/watch?v=BHdbsHFs2P0",
+    ...
+    "playlist_channel": "3Blue1Brown",
+    "playlist_channel_id": "UCYO_jab_esuFRV4b17AJtAw",
+    "playlist_count": 147,
+    "playlist_webpage_url": "https://www.youtube.com/@3blue1brown/videos",
+    ...
+}
```

**Why:** Based on real yt-dlp output from 3Blue1Brown channel (captured during research). Using real data catches field name mismatches that synthetic fixtures would miss.

Key test design decisions:

- **`TestNormalizeChannelUrl` (9 tests):** Covers bare, trailing slash, each known tab (/shorts, /live, /streams, /playlists, /community), /channel/UC format, and already-correct /videos. The /community, /playlists, /streams tests were added during review — the initial implementation only tested /shorts and /live.

- **`TestCheckCommentGrowth` boundary tests:** `test_exactly_10_percent` verifies that exactly 10% is NOT flagged (strict >10%), while `test_11_percent_growth` verifies 11% IS flagged. These boundary tests catch off-by-one errors in the threshold comparison (`>` vs `>=`).

- **`TestMatchExistingVideos.test_old_metadata_format`:** Old markdown format (`Views: 5,000 | Likes: 200`) doesn't have a comments field — verifies `stored_comments` is `None` rather than crashing.

- **`TestMatchExistingVideos.test_ignores_backup_files`:** Backup files match the glob pattern but shouldn't be treated as summaries. Tests the `_is_summary_file` filter.

- **`TestFindOutputDir.test_files_ignored`:** A file named `UC_some_id.txt` shouldn't match — only directories count.

---

## 7. `youtube-to-markdown/CHANGELOG.md` (MODIFIED)

```diff
+## [2.4.0] - 2026-02-10
+
+### New Feature: Channel Browser
+- Browse YouTube channel videos by providing a channel URL
+- Paginated listing (20 videos per page) with title, views, duration
+- Matches against locally extracted videos in output directory and subdirectories (depth 1)
+- Check comment growth on existing videos (>10% triggers refresh suggestion)
+- Batch extraction: select multiple new videos with same output mode
+- Channel subdirectory suggestion for new channels
+- URL normalization: any channel tab redirects to /videos
+- Rate limiting: --sleep-requests 0.5 for listing, 1s delay for individual metadata
+
+### New Files
+- `lib/channel_listing.py` - Channel listing and video matching library
+- `scripts/22_list_channel.py` - Channel video listing CLI
+- `scripts/23_check_comment_growth.py` - Comment growth detection CLI
+- `subskills/channel_browse.md` - LLM instructions for channel browsing flow
+
+### Testing
+- 30 new tests for channel_listing (parse, match, growth threshold, output dir)
```

**Why:** Minor version bump (2.3.4 → 2.4.0) — new feature, not a breaking change. Lists all new files and test count. Rate limiting documented because it's a key operational constraint users should know about. Note: test count says 30 in changelog (written earlier), actual final count is 33 after review additions.

---

## 8. `youtube-to-markdown/README.md` (MODIFIED)

```diff
+- **Channel browser** - Browse channel videos, batch-extract new ones, detect comment growth on existing
```

```diff
+Or browse a channel:
+```
+extract https://www.youtube.com/@channelname
+```
```

```diff
+  22_list_channel.py
+  23_check_comment_growth.py
```

**Why:** Three additions: feature list entry, usage example, project structure update. Minimal — follows CLAUDE.md "not writing a book". The usage example shows the simplest invocation (`@channelname`) rather than all four URL formats.

---

## 9. `youtube-to-markdown/pyproject.toml` (MODIFIED)

```diff
-version = "2.3.4"
+version = "2.4.0"
```

**Why:** Version bump synchronized with CHANGELOG.md and marketplace.json.

---

## 10. `.claude-plugin/marketplace.json` (MODIFIED)

```diff
-      "description": "Transform YouTube video to storagable knowledge. Choose from summary only, transcript only, comments only, or full extraction. Get tight summary, cleaned transcript, and curated comment insights cross-analyzed against video content. Modular architecture runs independent steps in parallel.",
-      "version": "2.3.4",
+      "description": "Transform YouTube video to storagable knowledge. Choose from summary only, transcript only, comments only, or full extraction. Get tight summary, cleaned transcript, and curated comment insights cross-analyzed against video content. Browse channels to batch-extract or refresh comments. Modular architecture runs independent steps in parallel.",
+      "version": "2.4.0",
       "category": "media-extraction",
-      "keywords": ["youtube", "transcript", "captions", "markdown", "summary", "chapters", "comments"],
+      "keywords": ["youtube", "transcript", "captions", "markdown", "summary", "chapters", "comments", "channel"],
```

**Why:** Marketplace description gains one sentence about channel browsing. "channel" keyword added for discoverability. Version synchronized.

---

## Deviations from Plan

| Plan | Implementation | Reason |
|------|---------------|--------|
| `check_comment_growth(video_ids, output_dir, cmd_runner)` | `check_comment_growth(current_counts: dict[str, int], output_dir)` | Separates IO from logic — function is pure and directly testable |
| `needs_comment_refresh` field in 22_list_channel output | Removed | Flat-playlist doesn't have comment_count — field would always be false, misleading |
| `search_depth=1` parameter | Hardcoded depth 1 | YAGNI — no use case for depth > 1 |
| `--sleep-requests 1` in 23_check_comment_growth | `time.sleep(1)` in Python | Each video is a separate subprocess call — yt-dlp's sleep flag only works within a single invocation |
| 30 tests in changelog | 33 tests actual | Three URL normalization tests added during review |

## Review Fixes (post-implementation)

| Finding | Fix | Commit |
|---------|-----|--------|
| Unused imports (`find_existing_files`, `format_count_compact`) | Removed | 9a4ef41 |
| Misleading docstring in 23 ("--sleep-requests 1") | Changed to "1s Python-level delay" | 9a4ef41 |
| Missing `json.JSONDecodeError` handling in `list_channel_videos` | Added try/except per JSON line | 9a4ef41 |
| Path traversal via `..` in channel name | `clean_name.replace("..", "")` | 9a4ef41 |
| Duplicated filter logic in `_find_summary_for_video_id` | Extracted `_is_summary_file()` helper | 2168851 |
| Inconsistent `stored_comments` type (str vs int) | Unified via `parse_count()` → always int or None | 2168851 |
| Negative offset not validated | `offset = max(0, offset)` | 2168851 |
| Missing /community, /playlists, /streams URL tests | Added 3 tests | 2168851 |
