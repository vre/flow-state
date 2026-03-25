# youtube-to-markdown: shorter filenames + transcript ← watch guide crosslinks

## Problem

1. **Filenames contain redundant "- youtube"** — `2026-02-20 - youtube - Woltin tarina - transcript (N5lxgolOt8E).md` is unnecessarily long. "youtube" is obvious from context (folder, video_id).
2. **Transcript has no watch links** — watch guide links to transcript sections, but transcript doesn't link back to video moments worth watching. The data exists (watch guide ▶ links) but isn't surfaced in the transcript.

## Goal

1. Remove " - youtube" from all generated filenames: `{date} - {title}{suffix} ({video_id}).md`
2. Assembler post-processes transcript to inject ▶ video links from watch guide under matching headings.

## Design

### Filename change

`assembler.py` `build_filename`:
- Before: `f"{upload_date} - youtube - {cleaned_title}{suffix} ({video_id}).md"`
- After: `f"{upload_date} - {cleaned_title}{suffix} ({video_id}).md"`
- Without date: `f"{cleaned_title}{suffix} ({video_id}).md"`

This affects: summary, transcript, comments, watch guide filenames. Existing files are not renamed.

Watch guide prompt in `transcript_polish.md` already uses `{date} - {title} - transcript ({video_id})` (without "youtube") — matches the new pattern.

### Transcript ← watch guide crosslinks

Assembler already reads both transcript and watch guide during assembly. New post-processing step:

1. Parse watch guide: extract ▶ lines and their section headings
2. Parse assembled transcript: find matching ### headings
3. After each matching heading in transcript, insert the ▶ line(s) from watch guide as a callout or inline note

Format in transcript under heading:
```
### Topic Heading

▶ [Watch: Title](https://youtube.com/watch?v=...&t=SECONDS) HH:MM:SS–HH:MM:SS — reason

Paragraph text...
```

Only inject ▶ lines that exist in watch guide — headings without watch moments get nothing added. This is pure string matching on heading text.

Implementation: new method `Finalizer.inject_watch_links(transcript_content, watch_guide_content) -> str` called during assembly after transcript is assembled but before writing.

## Acceptance Criteria

- [x] AC1: Generated filenames no longer contain " - youtube"
- [x] AC2: Existing tests updated for new filename format
- [x] AC3: Assembled transcript contains ▶ video links under headings that have watch moments
- [x] AC4: Headings without watch moments unchanged
- [x] AC5: Works when watch guide doesn't exist (option C/D)
- [x] AC6: Watch guide 📖 links use new filename format (already done in prompt)

## Tasks

- [x] 1. Update `build_filename` — remove " - youtube"
- [x] 2. Fix all tests expecting old filename format
- [x] 3. Implement `inject_watch_links` in assembler
- [x] 4. Tests for inject_watch_links: matching headings, no match, no watch guide, multiple ▶ per section
- [x] 5. Wire inject_watch_links into assembly flow
- [x] 6. Verify: option A, B, C, D produce correct output

## Reflection

- Current and legacy filename shapes both resolve because summary lookup now matches `* ({video_id}).md` and filters by suffix instead of assuming `"youtube - "`.
- Transcript injection uses raw watch-guide `→ Heading` references and only inserts lines that already contain a deep link, so `Read Instead` notes do not create false watch markers.
- Verification passed with:
  - `env UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/youtube-to-markdown/test_assembler.py tests/youtube-to-markdown/test_watch_guide.py tests/youtube-to-markdown/test_check_existing.py tests/youtube-to-markdown/test_channel_listing.py tests/youtube-to-markdown/test_file_ops.py -q`
  - `env UV_CACHE_DIR=/tmp/uv-cache PYTHONPATH=youtube-to-markdown uv run pytest youtube-to-markdown/tests/test_check_view_growth.py -q`
  - `env UV_CACHE_DIR=/tmp/uv-cache uv run ruff check youtube-to-markdown/lib/assembler.py youtube-to-markdown/lib/check_existing.py youtube-to-markdown/lib/channel_listing.py tests/youtube-to-markdown/test_assembler.py tests/youtube-to-markdown/test_watch_guide.py tests/youtube-to-markdown/test_check_existing.py tests/youtube-to-markdown/test_channel_listing.py tests/youtube-to-markdown/test_file_ops.py youtube-to-markdown/tests/test_check_view_growth.py`
- Git commit remains blocked in this Codex sandbox even with `GIT_DIR=.git-codex-sandbox-workaround`: `index.lock` creation under `/Users/vre/work/flow-state/.git/worktrees/ytm-filenames/` is denied. Manual commit outside this sandbox is still required.
