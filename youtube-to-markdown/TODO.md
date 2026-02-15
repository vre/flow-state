# TODO

## Ideas for further improvements

- [x] Pull list of videos on a youtube channel and propose to fetch the new ones and update comments for older (v2.4.0)
- [x] Channel browser UX: description enrich + secure checkbox parsing + view-growth lookup for date-prefixed files (v2.6.0)
- [x] Channel browse cleanup: remove per-video enrich script, use Haiku batch summaries, add `--limit` pagination control (v2.7.0)
- [ ] Providing yt-dlp logged in cookie signed to download restricted/member/etc transcripts
- [ ] Try modding skill to run on opencode, github copilot, openai codex, ...

- [ ] Comment evolution — cross-compare old and new comments on re-extract, surface deltas (plan: `docs/youtube-to-markdown/plans/2026-02-12-comment-evolution.md`)
- [ ] Highlighting notable content to browseability
- [ ] Analysis keywords linking to transcript/commentary
- [ ] Check for alternative extraction methods

## Maybe later

- [ ] What is comments are in multiple languages? Now hardcoded do not translate.
  - Comments are mostly in the language of the video, that most probably is the language user wants.
- [ ] Annoying Write tool asks for "Create a File?" and opens editor
  - Since 12/2025 some release claude gives opportunity to shift-tab to auto approve all edits during session
  - Investigated alternatives (bash/python/env vars) but command line spam is worse

## Noted limitations
- Claude does not want to make transcript chapters for copyrighted content, such as music videos.
