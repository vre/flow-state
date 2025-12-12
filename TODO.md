# TODO

## Implemented 2.0

- [x] Timestamps linking to original video
- [x] Move the comment analysis to summary section
- [x] Retitle the comment analysis and add tiny heading summary
- [x] Add key takeaways from comments
- [x] Move the transcription to own file
  - It took too much space from summary file, and I think it is better use to separate them
- [x] What about really long videos? Should do Multiple parts or what? Longer video, longer summary? Or squeeze based on information content ratio? 
  - Create more summaries based on the sections of content in the video
- [x] How to handle videos with promotion blocks? 
  - Skip them during the analysis as part of the section identification
- [x] Test with different video types - lectures, talks, vlogs, tutorials, reviews
  - Why/what/how/when format does definitely work with list style videos -> 4 types of summaries
- [x] Fix bloated summaries 
  - AI always need a verification step added adversial editor step
- [x] What if the video has 1000+ comments - prefiltering via thumbs up/down?
  - There is actually no sense of not analyzing comments. Only ask how if many comments to analyze.
- [x] Study better ways to summarize comments
  - There is variance based on video content, so let the LLM analysse and decide.
- [x] More metadata - amount of comments, license.
- [x] Check if already extracted - maybe then update summary structure if old version or less comments analyzed.

## Ideas for further improvements


- [ ] Highlighting notable content to browseability
- [ ] Keyword/topic list section with links to transcript parts
- [ ] Analysis linking to transcript/commentary
- [ ] Keyword/topic list linking to transcript parts

- [ ] Try modding skill to run on github copilot, openai codex, ...
- [ ] Optional minimization of transcript cleanup token usage, make own plugin/optional/step
- [ ] Check alternative extraction methods
- [ ] Providing yt-dlp logged in cookie signed to download restricted/member/etc transcripts

## Maybe later

- [ ] Annoying Write tool asks for "Create a File?" and opens editor
  - Investigated alternatives (bash/python/env vars) but command line spam is worse
  - Since 12/2025 some release claude gives opportunity to shift-tab to auto approve
- [ ] What is comments are in multiple languages? Now hardcoded do not translate.
  - Comments are mostly in the language of the video, that most probably is the language user wants. Claude is not that good translating all the languages, especially towards smaller ones.
- [ ] Make analysis, summary, highlighting optional - ask the user before running
  - All extra questions stop the flow.. make a good summary as possible with what you got. There is no additional highlighting defined - LLM does what it does.


## Noted limitations
- Claude does not want to make chapters for copyrighted content, such as music videos.