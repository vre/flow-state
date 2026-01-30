# Changelog

## [2.3.4] - 2026-01-29

### Bug Fixes
- Fixed comment state detection: distinguishes "curated_only" (no insights), "v1", "v2"
- Files with only curated comments no longer incorrectly flagged as "v1 outdated"

## [2.3.3] - 2026-01-29

### Update Flow Improvements
- Added metadata comparison table (Views/Likes/Comments: Stored vs Current)
- Added "Re-extract comments" option for refreshing comments without full reload
- Added "Re-extract transcript" option for different language or refresh
- Re-ordered options: most common use cases (re-extract) shown first

## [2.3.2] - 2026-01-26

### Security
- Prompt injection defense: user-generated content (descriptions, comments, transcripts) wrapped in `<untrusted_xxx_content>` XML tags with warnings
- Injection patterns escaped (tag closing attempts, legacy delimiters)
- New lib/content_safety.py module

### Bug Fixes
- check_existing.py now detects intermediate files from incomplete extractions
- Returns `has_intermediate: true` when partial extraction files exist

## [2.3.1] - 2026-01-26

### Project Structure Reorganization
- `scripts/` - CLI wrappers with numbered prefixes (10-59) indicating pipeline order
- `lib/` - Library modules (importable code)
- `templates/` - Markdown templates with cleaner names
- `subskills/` - LLM instructions (formerly modules/)

### Naming Convention
- 10-19: Data extraction (extract)
- 20-29: Existing file check/update analysis (check/prepare)
- 30-39: Data processing (clean/format/filter)
- 40-49: File management (backup/update)
- 50-59: Final assembly (assemble)

## [2.3.0] - 2026-01-26

### Update Mode Redesign
- Replaced update_mode.md module with prepare_update.py script
- prepare_update.py analyzes existing files and generates update recommendations
- Handles 11 use cases: v1 format upgrade, metadata refresh, failed extraction, extending outputs, comment refresh, full refresh, video changes, language change, deleted video, interrupted extraction, chapter additions
- New update_metadata.py for metadata-only updates without re-processing
- New modules/update_flow.md for update logic (loaded only when needed)

### Technical
- prepare_update.py returns JSON with: existing file status, metadata changes, issues, recommendation
- Recommendation includes action type, reason, suggested output, files to backup
- Action types: metadata_only, update_summary, update_comments, update_transcript, extend, full_refresh, none
- New intermediate_files.py: single source of truth for work file patterns (removes duplication between finalize.py and file_ops.py)
- Interrupted extraction detection: identifies incomplete extractions from intermediate files
- Backup timestamps now include seconds (YYYYMMDD_HHMMSS) to prevent same-day overwrites
- Title extraction from summary files for accurate change detection
- SKILL.md Step 0 simplified - references modules/update_flow.md
- Removed modules/update_mode.md

### Testing
- 28 new tests for prepare_update.py (parse_count, compare_counts, detect_issues, generate_recommendation)
- 7 new tests for update_metadata.py (replace_metadata_section, update_extraction_date)

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