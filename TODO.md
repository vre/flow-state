# TODO

## Cooking
- [x] Timestamps linking to original video
- [x] Move the comment analysis to summary section

- [ ] What about really long videos? Should do Multiple parts or what? Longer video, longer summary? Or squeeze based on information content ratio?
- [ ] Test with different video types - lectures, talks, vlogs, tutorials, reviews
- [ ] What if the video has 1000+ comments - prefiltering via thumbs up/down?

- [ ] Highlighting notable content to browseability
- [ ] Keyword/topic list section with links to transcript parts
- [ ] Analysis linking to transcript/commentary
- [ ] Keyword/topic list linking to transcript parts

- [ ] Make analysis, summary, highlighting optional - ask the user before running

- [ ] Try modding skill to run on github copilot, openai codex, ...
- [ ] Check alternative extraction methods via browser, playwright, ... maybe extraction also when user signed in.


## Maybe later
- [ ] Annoying Write tool asks for "Create a File?" and opens editor
  - Investigated alternatives (bash/python/env vars) but command line spam is worse 
- [ ] What is comments are in multiple languages? Now hardcoded do not translate.
  - Comments are mostly in the language of the video, that most probably is the language user wants. Claude is not that good translating all the languages, especially towards smaller ones.

## Noted limitations
- Claude does not want to make chapters for copyrighted content, such as music videos.