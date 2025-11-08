# Changelog

## [Unreleased]

### Initial Version Creation Story
- Found and tried https://github.com/michalparkola/tapestry-skills-for-claude-code/blob/main/youtube-transcript/SKILL.md - the skill did the extraction but output was just plain text. The script was a part of skill-set for "5-rep action plans with timelines", I didn't need any of that for my use case. Contributing directly back did not make much sense. Read the source. Transcript extraction with Whisper and deduplication that seemed useful. Created first version of youtube-to-markdown skill based on the original skill.
- Added transcript to markdown, breakout to paragraphs, cleanup and section titling. Added metadata extraction and comments extraction.
- Decided to use journalistic style summary. I just described it to my daughter who was creating a school presentation on "ILO" https://www.ilo.org as simple method to discover the key points.
- Thought that compression often loses some of the sweetness, so added "Hidden Gems" part to capture notable small parts that are interesting.
- Researched for alternative ways to do a summary, and decided to stay in journalistic style was the way, but added TL;DR.
- Converted everything to python3. Better error handling and programmability.
- Separated comment extraction into standalone youtube-comment-analysis skill for modularity as comments are often plentiful and user should be able to decide if they want to include them or not. Also token and time consuming. Initial release will support two modes: standalone comment analysis or cross-analysis with video summary.
- youtube-to-markdown asks at beginning if user wants comment analysis too, and chains to youtube-comment-analysis after completion if requested. youtube-comment-analysis checks for existing summary and offers to create one first if missing.
- Output files use human-readable filenames: `youtube - {title} ({video_id}).md` and `youtube - {title} - comments ({video_id}).md`
- Works also with videos that are not in english, keeps the transcript, summary etc. in the langauge of the video. Hardcoded comments to not to translate for now.
- Speedboost on transcribing videos without transcript with mlx-whisper on mac. Playing with pipx and uv is a bit messy. Python3.14 and mlx-whisper no go at the moment at least on my machine, but via uv it works.
- Decided that why not make skills public for others to use for sake of Father's day in Finland on 8th of November 2025. Thought of additional features to be added later.