# Changelog

## [2.2.0] - 2026-01-23

### Architecture
- Merged youtube-comment-analysis into youtube-to-markdown as modular plugin
- User selects output: Summary only, Transcript only, Comments only, Summary+Comments, or Full
- Dependency graph enables parallel execution of independent modules
- 5 modules: transcript_extract, transcript_summarize, transcript_polish, comment_extract, comment_summarize

### Technical
- finalize.py supports output flags: --summary-only, --transcript-only, --comments-only, --summary-comments
- shared_types.py extended with Comment and CommentVideoData types
- extract_comments.py updated to use shared_types
- Added template_comments.md and template_comments_standalone.md

### Removed
- youtube-comment-analysis plugin (merged into youtube-to-markdown)

## [2.1.1] - 2026-01-13

### Bug fixes
- Detect incomplete extractions (empty summary/transcript sections)
- check_existing.py returns summary_valid, transcript_valid, comments_valid flags
- SKILL.md asks user before re-processing broken files

## [2.1.0] - 2025-01-13

### Technical
- Scripts runnable from any directory (sys.path fix for imports)
- Replaced shell commands (cut, mv, rm) with Python for Claude Code permission compatibility
- Added file_ops.py for backup/cleanup operations
- deduplicate_vtt.py: optional third param for timestamp-stripped output

### Testing
- 9 new tests for file_ops.py

## [2.0.1] - 2025-01-07

### Improvements
- More metadata in summary output
- Old format analysis update script added

## [2.0] - 2024-12-08

### New features
- Content-type detection to use the 1 out of 4 summarization methods based on the content
  - TIPS, INTERVIEW, EDUCATIONAL, TUTORIAL
  - Previously only did what/why/how/when then structure that is now the EDUCATIONAL
- Adversarial editor step enforces <10% byte budget and cuts fluff
- YouTube time-links: paragraph timestamps link back to video position
- Transcript moved to separate file (summary was getting too long)
- Promotion blocks skipped during section identification

### Improvements
- Comment sort: default (new) → top (by likes)
- Comment filtering: haiku LLM step → 60-line prefilter script
- Comment limit: 50 from unsorted → 200 after junk removal
- Standalone comment analysis mode (no transcript required)
- Defined what hidden gems really are: "valuable tangents/side narratives that don't fit main structure but deserve preservation"

### Testing
- 2,305 lines of tests added (was: 0)

### Technical
- Python: 1,215 → 2,606 lines
- SKILL.md: 275 → 288 lines

## [1.0] - 2024-11-09

### Origin
- Found and tried https://github.com/michalparkola/tapestry-skills-for-claude-code/blob/main/youtube-transcript/SKILL.md - the skill did the extraction but output was just plain text. The script was a part of skill-set for "5-rep action plans with timelines", I didn't need any of that for my use case. Contributing directly back did not make much sense. Read the source. Transcript extraction with Whisper and deduplication that seemed useful. Created first version of youtube-to-markdown skill based on the original skill.

### Features
- Added transcript to markdown, breakout to paragraphs, cleanup and section titling. Added metadata extraction and comments extraction.
- Decided to use journalistic style summary. I just described it to my daughter who was creating a school presentation on "ILO" https://www.ilo.org as simple method to discover the key points.
- Thought that compression often loses some of the sweetness, so added "Hidden Gems" part to capture notable small parts that are interesting.
- Researched for alternative ways to do a summary, and decided to stay in journalistic style was the way, but added TL;DR.

### Architecture
- Converted everything to python3. Better error handling and programmability.
- Separated comment extraction into standalone youtube-comment-analysis skill for modularity as comments are often plentiful and user should be able to decide if they want to include them or not. Also token and time consuming. Initial release will support two modes: standalone comment analysis or cross-analysis with video summary.
- youtube-to-markdown asks at beginning if user wants comment analysis too, and chains to youtube-comment-analysis after completion if requested. youtube-comment-analysis checks for existing summary and offers to create one first if missing.
- Output files use human-readable filenames: `youtube - {title} ({video_id}).md` and `youtube - {title} - comments ({video_id}).md`

### i18n
- Works also with videos that are not in english, keeps the transcript, summary etc. in the langauge of the video. Hardcoded comments to not to translate for now.

### Performance
- Speedboost on transcribing videos without transcript with mlx-whisper on mac. Playing with pipx and uv is a bit messy. Python3.14 and mlx-whisper no go at the moment at least on my machine, but via uv it works.

### Release
- Decided that why not make skills public for others to use for sake of Father's day in Finland on 8th of November 2025. Thought of additional features to be added later.