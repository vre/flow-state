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

- [ ] AC1: Generated filenames no longer contain " - youtube"
- [ ] AC2: Existing tests updated for new filename format
- [ ] AC3: Assembled transcript contains ▶ video links under headings that have watch moments
- [ ] AC4: Headings without watch moments unchanged
- [ ] AC5: Works when watch guide doesn't exist (option C/D)
- [ ] AC6: Watch guide 📖 links use new filename format (already done in prompt)

## Tasks

- [ ] 1. Update `build_filename` — remove " - youtube"
- [ ] 2. Fix all tests expecting old filename format
- [ ] 3. Implement `inject_watch_links` in assembler
- [ ] 4. Tests for inject_watch_links: matching headings, no match, no watch guide, multiple ▶ per section
- [ ] 5. Wire inject_watch_links into assembly flow
- [ ] 6. Verify: option A, B, C, D produce correct output

## Reflection

<!-- Written post-implementation by IMP -->
