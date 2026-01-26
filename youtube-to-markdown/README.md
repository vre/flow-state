# YouTube to Markdown

Transform YouTube videos into storable knowledge as Markdown.

- **TL;DR + structured summary** - Core insights with content-specific summarization
- **Hidden Gems** - Insights that normal summarization loses
- **Modular output** - Choose from summary, transcript, comments, or all

## Features

- **Summary** - TL;DR + structured summary with four content-specific formats (Tips, Interview, Educational, Tutorial)
- **Transcript** - Cleaned and formatted with chapters, paragraphs, and topic headings
- **Timestamp links** - Jump back to specific moments in the original video
- **Comment analysis** - Curated comments cross-analyzed against video content
- **Update mode** - Refresh existing extractions when video metadata changes

## Security

Defends against prompt injection in YouTube content. User-generated content (descriptions, comments, transcripts) is wrapped in `<untrusted_xxx_content>` XML tags with warnings, and injection patterns are escaped.

## Installation for Claude Code

### As a Plugin

```bash
/plugin marketplace add vre/flow-state
/plugin install youtube-to-markdown@flow-state
```

### Dependencies

- Python 3.10+
- yt-dlp (`brew install yt-dlp` or `pip install yt-dlp`)

## Usage

```
extract https://www.youtube.com/watch?v=VIDEO_ID
```

Also works: `get`, `fetch`, `transcript`, `subtitles`, `captions`

## Workflow: Extract Video

1. **Provide YouTube URL** - paste the video link
2. **Choose output** - Summary only, Transcript only, Comments only, Summary+Comments, or Full
3. **Wait for extraction** - Claude processes video data and generates markdown
4. **Get files** - Drop into Obsidian, Notion, or any note-taking system

## Output Options

| Option | Output |
|--------|--------|
| Summary only | Summary with TL;DR and key insights |
| Transcript only | Cleaned, formatted full transcript |
| Comments only | Curated top comments |
| Summary + Comments | Summary with cross-analyzed comment insights |
| Full | All: summary, transcript, comments |

## Output Files

- `youtube - {title} ({video_id}).md` - Summary with metadata
- `youtube - {title} - transcript ({video_id}).md` - Cleaned transcript with timestamps
- `youtube - {title} - comments ({video_id}).md` - Curated comments

## Project Structure

```
scripts/             # CLI entry points (numbered by pipeline order)
  10_extract_metadata.py
  11_extract_transcript.py
  13_extract_comments.py
  20_check_existing.py
  21_prepare_update.py
  30_clean_vtt.py
  31_format_transcript.py
  32_filter_comments.py
  40_backup.py
  41_update_metadata.py
  50_assemble.py
lib/                 # Importable library modules
templates/           # Markdown output templates
subskills/           # LLM instructions for Claude
SKILL.md             # Main skill definition
```

## License

MIT, See [LICENSE](LICENSE) for more information.
