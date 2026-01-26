# TODO

## Ideas for further improvements

- [ ] Providing yt-dlp logged in cookie signed to download restricted/member/etc transcripts
- [ ] Try modding skill to run on opencode, github copilot, openai codex, ...

- [ ] Highlighting notable content to browseability
- [ ] Analysis keywords linking to transcript/commentary
- [ ] Check for alternative extraction methods

## Maybe later

- [ ] Annoying Write tool asks for "Create a File?" and opens editor
  - Investigated alternatives (bash/python/env vars) but command line spam is worse
  - Since 12/2025 some release claude gives opportunity to shift-tab to auto approve all edits during session
- [ ] What is comments are in multiple languages? Now hardcoded do not translate.
  - Comments are mostly in the language of the video, that most probably is the language user wants. Claude is not that good translating all the languages, especially towards smaller ones.
- [ ] Make analysis, summary, highlighting optional - ask the user before running
  - All extra questions stop the flow.. make a good summary as possible with what you got. There is no additional highlighting defined - LLM does what it does.


## Noted limitations
- Claude does not want to make chapters for copyrighted content, such as music videos.
