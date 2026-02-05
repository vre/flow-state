# Comment Evolution Analysis

## Context

When a video's comments grow significantly, users currently can only "re-extract comments" which replaces old comments entirely. There's no analysis of what changed — which new perspectives appeared, how the conversation developed.

This builds on channel-browser-ux (2026-02-12) which identifies videos with >30% view growth as candidates for comment refresh.

## Goal

When refreshing comments on existing videos, produce a delta analysis: what's new, what dropped off, and how the conversation has evolved.

## Situational Context

### Stored Comment File Format

File: `youtube - {title} - comments ({video_id}).md`

Actual format (from recent extraction):

```markdown
## Curated Comments

### 1. @CraigHollabaugh (7 likes)

10 min update, nice work on this cold Saturday morning. Thanks and stay warm.

### 2. @sinistermephisto65 (5 likes)

5 engineers shipped in 3 days of development
How many days of prototyping and planning?

### 3. @TreeLuvBurdpu (5 likes)

We will NEVER run out of work...
```

Structure per comment:
- `### {n}. @{author} ({likes} likes)` — header line
- Empty line
- Comment text (one or more lines, may include replies as `#### @{author}`)
- Empty line before next comment

Top-level comments use `###`, replies use `####`.

### Comment Extraction Pipeline

```
13_extract_comments.py → raw JSON (all comments from YouTube)
32_filter_comments.py → prefiltered (top N by likes, max 200)
LLM curation via subskills/comment_summarize.md → curated markdown
50_assemble.py → final comments file
```

Intermediate file: `youtube_{video_id}_comments_prefiltered.md` (filtered but not curated).

### `extract_metadata_from_file()` Return

```python
{"title": str|None, "views": str|None, "likes": str|None,
 "comments": str|None, "published": str|None, "extracted": str|None}
```

`extracted` field gives previous extraction date for "since" reference.

### Summary File Engagement Line

```markdown
- **Engagement:** 23.2K views · 451 likes · 27 comments
- **Published:** 2020-10-28 | Extracted: 2025-12-13
```

## Design

### Flow

```
1. User selects video for comment refresh (from channel browser or manually)
2. Fetch current comments (existing 13_extract_comments.py)
3. Prefilter current comments (existing 32_filter_comments.py)
4. Parse stored comments from " - comments.md" file into structured list
5. NEW: Mechanical diff — match by author + text prefix:
   - New comments: in current but not in stored
   - Dropped comments: in stored but not in current (fell off top-voted)
   - Retained comments: in both (may have different like counts)
6. NEW: LLM analysis of the delta:
   - What new themes/perspectives appeared?
   - Any notable high-engagement new comments?
   - How has the conversation shifted?
7. Produce evolution report + updated comments file
```

### Stored Comment Parsing

Parse `- comments.md` file into list of dicts:

```python
def parse_stored_comments(content: str) -> list[dict]:
    """Parse curated comments markdown into structured list.

    Returns:
        List of {"author": str, "likes": int, "text": str, "is_reply": bool}
    """
```

Regex for header: `^###\s+\d+\.\s+@(\S+)\s+\((\d+)\s+likes?\)` (top-level)
Regex for reply: `^####\s+@(\S+)\s+\((\d+)\s+likes?\)` (reply)
Text: lines between current header and next header.

### Mechanical Diff

Match comments between stored and current (prefiltered) sets:

```python
def diff_comments(stored: list[dict], current: list[dict]) -> dict:
    """Mechanical diff between two comment sets.

    Match key: normalize(author) + first 50 chars of text.
    Returns: {"new": [...], "dropped": [...], "retained": [...],
              "stats": {"new_count": int, "dropped_count": int, "retained_count": int}}
    """
```

- `new`: in current but not in stored → fresh perspectives
- `dropped`: in stored but not in current → fell off top-voted list
- `retained`: in both → may have different like counts (track delta)
- Author normalization: lowercase, strip @

### Current Comments Parsing

Prefiltered comments (`32_filter_comments.py` output) are in same markdown format as curated. Same parser works.

If prefiltered intermediate file unavailable: parse raw `youtube_{video_id}_comments.json` instead.

### LLM Analysis

Feed mechanical diff to LLM via subskill `comment_evolution.md`:

```
INPUT: {new_comments, dropped_comments, retained_with_like_changes, video_summary_context}
OUTPUT: evolution report markdown
```

Token budget: mechanical diff pre-filters. LLM only sees structured delta, not all comments.

### Output Format

New section appended to comments file:

```markdown
## Comment Evolution (since {previous_extraction_date})

**Growth:** {stored_count} → {current_count} comments (+{pct}%)
**New:** {new_count} | **Dropped:** {dropped_count} | **Retained:** {retained_count}

### New Themes
- {theme}: {summary of new comments on this topic}

### Notable New Comments
- **@{author}** ({likes} likes): "{excerpt}" — {why notable}

### Conversation Shift
{how discussion has evolved since last extraction}
```

## Files to Create

- `lib/comment_evolution.py` — `parse_stored_comments()`, `diff_comments()`
- `scripts/33_diff_comments.py` — CLI: takes stored + current comment files, outputs JSON diff
- `subskills/comment_evolution.md` — LLM analysis instructions for delta

## Files to Modify

- `subskills/update_flow.md` — add "Refresh comments with evolution analysis" option
- `subskills/channel_browse.md` — wire view-growth refresh to evolution analysis

## Constraints

- Stored comments are curated (top-voted, filtered) — diff is between curated sets
- Author name matching is imprecise (name changes, Unicode). Text prefix as fallback.
- `parse_count()` precision: "2.3M" round-trips as 2300000. Acceptable for diff stats.
- Must handle v1 comment format (older extractions without numbered headers) — graceful degradation: log warning, skip diff, proceed with plain re-extract
- LLM analysis is per-video, not batch — acceptable cost for targeted refresh

## Validation

- Use existing extraction with comments file, re-fetch comments, verify diff detects new/dropped
- Test parser against actual comment files (example: `2026-01-24 - youtube - Apple Took Years...`)
- Verify evolution report integrates cleanly into existing comments file format

## Acceptance Criteria

- [ ] `parse_stored_comments()` correctly parses `### N. @author (N likes)` format including replies
- [ ] Mechanical diff correctly identifies new/dropped/retained comments
- [ ] LLM evolution report generated with themes, notable comments, shift
- [ ] Integrates into update_flow.md as option alongside plain re-extract
- [ ] Tests for: comment parsing, diff matching, stats calculation
- [ ] Manual test: video with known comment changes

## Dependency

Requires: `2026-02-12-channel-browser-ux.md` — view growth detection identifies candidates.
Comment evolution can also be triggered manually (without channel browser) via update_flow.md.
