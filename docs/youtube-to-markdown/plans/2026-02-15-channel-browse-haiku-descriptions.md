# Channel Browse: Haiku Descriptions & Skill Cleanup

## Context

Channel browser enriches new videos with description snippets via `24_enrich_metadata.py` — a per-video `yt-dlp --dump-json` call (~1-2s each). Testing revealed:
1. `--flat-playlist` already returns full `description` field — the enrichment script is redundant
2. Raw descriptions are often link spam, affiliate lists, chapter timestamps — the 200-char truncation hits junk
3. Haiku can clean and summarize descriptions in one batch call for all videos (~2s total)
4. Listing is capped at 20 videos — could fetch 50 in similar time

Additionally, `channel_browse.md` has verbose pseudocode in Step C4 (selection routing) and unnecessary "C" prefix on step names.

## Goal

Replace per-video enrichment with Haiku batch summarization using flat-playlist descriptions. Increase default listing size. Simplify skill flow.

## Design

### 1. `parse_channel_entry()` adds `description` field

Flat-playlist entry has `description` (full text). Add to return dict:

```python
return {
    "video_id": entry["id"],
    "title": entry.get("title", "Untitled"),
    "views": views,
    "view_count": view_count,
    "description": (entry.get("description") or "")[:500],  # NEW: capped for context budget
    "duration": entry.get("duration_string", "N/A"),
    "url": entry.get("url") or entry.get("webpage_url", ""),
}
```

### 2. `22_list_channel.py` adds `--limit N`

New optional argument, default 50:

```
Usage: 22_list_channel.py <CHANNEL_URL> <OUTPUT_DIR> [--offset N] [--limit N]
```

Default limit changes from 20 → 50. `has_more` logic uses the effective limit.

### 3. Description summarization via Haiku subagent

In `channel_browse.md` Step 2, instead of calling `24_enrich_metadata.py`:

```
task_tool:
- subagent_type: "general-purpose"
- model: "haiku"
- prompt:
  <instructions>
  You summarize YouTube video descriptions into one-line snippets.
  Goal: one line per video, max 200 chars, capturing what the video is about.
  Skip URLs, separator lines, timestamps, affiliate links, subscribe prompts, gear lists — these don't describe video content.
  If nothing meaningful remains after skipping junk, summarize from the title and append "(from title)".
  </instructions>

  <output_format>
  One line per video, exactly:
  VIDEO_ID: summary text

  Example:
  NCgdpbEvNVA: Explores why $650B in AI spending may be insufficient due to agentic inference demands, and which human skills survive the shift.
  </output_format>

  <context>
  {for each new_video, wrapped with content_safety:
  "- ID: {video_id} | Title: {title} | Description: {wrapped_description}"}
  </context>
```

Prompt follows `docs/writing-model-specific-prompts.md` guidance:
- XML tags separate instructions, output format, and context — prevents Haiku mixing them up
- Instructions in first section — attention decays fast in small models
- One concrete example — Haiku needs 1-2, diminishing returns past that
- Positive phrasing ("Skip X because Y") not negative ("Don't include X")
- Strict output schema, not "format nicely"
- Batch all videos in one call

Parse response: split by newline, match `VIDEO_ID: summary` lines, attach to video dicts.

Content safety: descriptions are untrusted user content — wrap each with `content_safety.wrap_untrusted_content(desc, "description")` before inserting into the prompt's `<context>` block.

### 4. Remove `24_enrich_metadata.py`

Delete:
- `scripts/24_enrich_metadata.py`
- `tests/test_enrich_metadata.py`

Update references in:
- `CHANGELOG.md`
- `README.md`

### 5. Rewrite `channel_browse.md`

Rename steps: C1→1, C2→2, C3→3, C4→4, C5→5.

**Step 2** (was C2): Remove `24_enrich_metadata.py` call. Add Haiku subagent call for new video descriptions. `check_view_growth()` stays unchanged.

**Step 4** (was C4): Simplify to:

```markdown
## Step 4: Process selections

Parse video IDs from selections:
- Checkbox file: `parse_selection_checkboxes(content)` → `[{video_id, section}]`
- multiSelect: extract `(VIDEO_ID)` from selected labels

New videos → SKILL.md Step 1 (output type), then Step 0 → Step 3.
Growth videos → `./subskills/update_flow.md` re-extract path.
```

**Step 5** (was C5): Offset increment uses effective limit, not hardcoded value. Pass `--limit` through if non-default:

```bash
python3 ./scripts/22_list_channel.py "<CHANNEL_URL>" "<output_directory>" --offset {current_offset + limit} [--limit {limit}]
```

### 6. `channel_browse.md` Step 3: Update checkbox file description snippet

Currently uses raw 200-char truncation. Replace with Haiku-summarized snippet from Step 2.

## Files to Modify

- `lib/channel_listing.py` — add `description` to `parse_channel_entry()`
- `scripts/22_list_channel.py` — add `--limit N` parameter, default 50
- `subskills/channel_browse.md` — rewrite Steps 1-5, remove enrich script call, add Haiku subagent

## Files to Delete

- `scripts/24_enrich_metadata.py`
- `tests/test_enrich_metadata.py`

## Files to Update (references)

- `CHANGELOG.md`
- `README.md`

## Constraints

- Haiku batch call: 50 videos × ~1500 chars avg description = ~75K chars ≈ ~20K tokens + prompt. Well within Haiku's 200K context.
- Full descriptions in `22_list_channel.py` JSON output increase its size significantly. The skill reads this JSON into context — cap `description` at 500 chars in `parse_channel_entry()` to limit context cost. Haiku gets enough signal from 500 chars.
- Flat-playlist 50 videos takes ~8-12s (vs ~5s for 20). Acceptable — one-time listing.
- `parse_count()` precision unchanged — 30% threshold absorbs lossy parsing.
- Description content from YouTube is untrusted — wrap before passing to any LLM.

## Testing

- Unit test: `parse_channel_entry()` returns `description` field
- Unit test: `22_list_channel.py` respects `--limit` parameter
- Manual test: channel listing with 50 videos, Haiku summarization quality
- Existing tests: `test_check_view_growth.py`, `test_checkbox_parsing.py`, `test_parse_channel_entry.py` must still pass

## Tasks

- [x] Add `description` passthrough to `parse_channel_entry()` with 500-char cap
- [x] Add `--limit N` support to `22_list_channel.py` and use effective limit in pagination
- [x] Replace per-video enrich flow in `channel_browse.md` with one Haiku batch summarization step
- [x] Remove `24_enrich_metadata.py` and `tests/test_enrich_metadata.py`
- [x] Update references in `youtube-to-markdown/README.md` and `youtube-to-markdown/CHANGELOG.md`
- [x] Merge-phase docs updated in root and plugin scope (`README.md`, `DEVELOPMENT.md`, `TESTING.md`, `TODO.md`, `CHANGELOG.md` where present)
- [x] Version numbers bumped consistently (`.claude-plugin/marketplace.json`, `youtube-to-markdown/pyproject.toml`, `youtube-to-markdown/CHANGELOG.md`)
- [x] Rebased branch with `git pull --rebase origin main` (no conflicts)
- [x] Post-rebase validation run (`pytest` pass, targeted `ruff check` pass, markdownlint pass)
- [+] Discovered and fixed: Step 5 pagination text implied page size comes from output instead of invocation context
- [+] Discovered and fixed: checkbox snippet spacing needed explicit blank lines for readability in editor flow
- [>] Deferred: squash merge into `main` until local `main` workspace cleanliness decision (`core/TODO.md` has separate local edits)

## Acceptance Criteria

- [x] `parse_channel_entry()` includes `description` field from flat-playlist
- [x] `22_list_channel.py` accepts `--limit N`, defaults to 50
- [x] New videos have Haiku-generated description summaries (≤200 chars) in selection UI
- [x] `24_enrich_metadata.py` and its tests deleted
- [x] Step names use plain numbers (1-5), no "C" prefix
- [x] Step 4 is concise — no `selection_map`/`selection_items` pseudocode
- [x] All existing tests pass
- [x] References in CHANGELOG.md and README.md updated

## Dependency

Builds on `2026-02-12-channel-browser-ux.md` (merged to main).

## Implementation Notes

- `22_list_channel.py` now supports `--limit N` and computes pagination with effective limit.
- `parse_channel_entry()` includes capped `description` (`max 500 chars`) from flat-playlist data.
- `channel_browse.md` now uses a single Haiku batch call for summaries and routes selections by `(VIDEO_ID)` parsing.
- Selection markdown snippet spacing was updated for readability:
  - blank line between checkbox row and summary text
  - blank line after summary text
- `24_enrich_metadata.py` and its tests were removed.

## Validation Results

- Automated tests: `pytest -q` in `youtube-to-markdown` passed (`28 passed`).
- Lint: `ruff check` passed for changed Python files.
- Manual smoke test with channel `https://www.youtube.com/channel/UCPjNBjflYl0-HQtUvOx0Ibw`:
  - listing succeeded (`count=50`, `has_more=true`)
  - descriptions present in listing JSON
  - selection markdown generation works with 4-item sample

## Surprises and Decisions

- Surprise: `--flat-playlist` already returns useful `description` data for this channel shape.
  Decision: remove `24_enrich_metadata.py` flow entirely instead of keeping dual paths.
- Surprise: batching descriptions into one Haiku call stayed within context budget with a 500-char cap.
  Decision: keep cap in `parse_channel_entry()` to bound prompt size deterministically.
- Surprise: pagination wording in skill text caused ambiguity around where `limit` comes from.
  Decision: treat effective `--limit` as invocation-state and use it explicitly when advancing `--offset`.
- Surprise: readability of checkbox files impacted selection confidence in manual use.
  Decision: keep blank-line spacing between checkbox row and summary snippet.

## Reflection

What worked:
- Removing per-video enrich calls cut listing complexity and reduced runtime variance.
- Flat-playlist description passthrough plus Haiku batch summarization gave cleaner selection snippets with simpler control flow.

What changed from initial plan:
- Pagination handling was tightened to explicitly use effective limit when computing next offset.
- Selection markdown spacing was adjusted after manual UX review.

Lessons:
- For selection routing, embedding canonical IDs in labels (`(VIDEO_ID)`) is the most robust contract when UI returns strings.
- Plan text should avoid wording that suggests values are read from output when they are known from invocation context (effective `--limit`).
- Merge readiness: implementation and plan updates are complete in the worktree branch; squash merge to `main` was intentionally deferred until explicit approval.
