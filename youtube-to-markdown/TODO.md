# TODO

## Ideas for further improvements

- [x] Pull list of videos on a youtube channel and propose to fetch the new ones and update comments for older (v2.4.0)
- [x] Channel browser UX: description enrich + secure checkbox parsing + view-growth lookup for date-prefixed files (v2.6.0)
- [x] Channel browse cleanup: remove per-video enrich script, use Haiku batch summaries, add `--limit` pagination control (v2.7.0)
- [x] Two-tier comment filter: split by p75 likes, Haiku screens tier-2, merge back substantive comments (v2.10.0)
- [ ] Providing yt-dlp logged in cookie signed to download restricted/member/etc transcripts
- [ ] Try modding skill to run on opencode, github copilot, openai codex, ...

- [x] ~~Comment evolution~~ — already handled by comment_summarize.md re-extract delta logic (new/updated/dropped markers)
- [x] ~~Highlighting notable content to browseability~~ — covered by Hidden Gems feature
- [ ] Analysis keywords linking to transcript/commentary
- [ ] Check for alternative extraction methods

## Planned

- [ ] Watch guide manual testing and future items
  - [ ] Manual test: Bas Rutten demo (expect WATCH) + Nate B Jones talking head (expect SKIM/READ-ONLY)
  - [ ] Obsidian video embed syntax in watch guide
  - [ ] Chatter/banter summary section in watch guide
  - [ ] Language preservation test (non-English watch guide)
  - [ ] 150 KB guard test with real long transcript
  - [ ] Gate evidence expansion (more signal types)
- [ ] Long transcript chunking for polish pipeline — `docs/youtube-to-markdown/plans/2026-02-24-long-transcript-chunking.md`
- [ ] IMAP attachment indicator — `docs/imap-stream-mcp/plans/2026-02-24-attachment-indicator.md`
- [ ] IMAP snippet preview — `docs/imap-stream-mcp/plans/2026-02-24-list-search-snippet.md`

## Maybe later

- [ ] Watch guide: validate language preservation (guide matches transcript language) — needs test strategy
- [ ] Watch guide: test 150 KB transcript skip guard with real long transcript
- [ ] Watch guide: expand gate evidence beyond 2 PoC videos — test with lectures, interviews, music, tutorials
- [ ] Watch guide: embed YouTube video in Obsidian watch guide file (Obsidian media plugin)
- [ ] Watch guide: summarize chatter/banter between substantive segments for WATCH/SKIM videos
- [ ] What is comments are in multiple languages? Now hardcoded do not translate.
  - Comments are mostly in the language of the video, that most probably is the language user wants.
- [ ] Annoying Write tool asks for "Create a File?" and opens editor
  - Since 12/2025 some release claude gives opportunity to shift-tab to auto approve all edits during session
  - Investigated alternatives (bash/python/env vars) but command line spam is worse

## Noted limitations
- Claude does not want to make transcript chapters for copyrighted content, such as music videos.
