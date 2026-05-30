# YouTube to Markdown

Transform YouTube videos into storable knowledge as Markdown.

- **TL;DR + structured summary** - Core insights with content-specific summarization
- **Hidden Gems** - Insights that normal summarization loses
- **Modular output** - Choose from summary, transcript, comments, or all

## Latest Release Highlights

**v3.0.0** — Summary format overhaul: claim-bullets as default (TL;DR + claim list + Hidden Gems), themed-claims for long multi-theme interviews, step-list for tutorials, flat-bullets for tips. Each format defines its complete output structure — no cross-referencing. Prompt injection defense hardened to three layers: NFKC normalization + Unicode Cf-strip, iterative role-token stripping, randomized 64-bit nonce delimiters. Channel browser: fixed spurious "create directory?" prompt on existing folders; view counts hidden when unavailable (yt-dlp regression [#13879](https://github.com/yt-dlp/yt-dlp/issues/13879)).

**v2.15.0** — Paragraph break detection moved to script (eliminates 100K+ token improvised Python); deterministic transcript structure. Watch guide: HH:MM:SS timestamps, WATCH/SKIM/READ-ONLY gate, clickable summary table, cross-links to transcript.

## Features

- **Summary** - TL;DR + structured summary with four content-specific formats (Tips, Interview, Educational, Tutorial)
- **Transcript** - Cleaned and formatted with chapters, paragraphs, and topic headings
- **Timestamp links** - Jump back to specific moments in the original video
- **Watch guide** - WATCH/SKIM/READ-ONLY gate with timestamped highlights and cross-links to transcript
- **Comment analysis** - Curated comments cross-analyzed against video content
- **Channel browser** - Browse channel videos, batch-extract new ones, detect comment growth on existing
  - Uses flat-playlist descriptions + Haiku batch one-liners for cleaner selection context
  - Default channel page size is 50 (override with `--limit`)
- **Context-efficient subagents** - Task subagents return one-line final status messages to keep coordinator context growth low
- **Update mode** - Refresh existing extractions when video metadata changes

## Security

Defends against prompt injection in YouTube content (descriptions, comments, transcripts). Three layers: NFKC normalization + Unicode format-character strip, iterative stripping of chat-template tokens (`<|im_start|>`, `[INST]`, `<<SYS>>`, role tags), and per-call randomized spotlight delimiters with 64-bit nonce. Content is wrapped and labeled as untrusted so the model treats it as data, not instructions.

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

Or browse a channel:
```
extract https://www.youtube.com/@channelname
```

Also works: `get`, `fetch`, `transcript`, `subtitles`, `captions`

## Workflow: Extract Video

1. **Provide YouTube URL** - paste the video link
2. **Choose output** - Summary only, Transcript only, Comments only, Summary+Comments, or Full
3. **Wait for extraction** - Claude processes video data and generates markdown
4. **Get files** - Drop into Obsidian, Notion, or any note-taking system

## Output Options

| Option | Output |
| ------ | ------ |
| Summary only | Summary with TL;DR and key insights |
| Transcript only | Cleaned, formatted full transcript |
| Comments only | Curated top comments |
| Summary + Comments | Summary with cross-analyzed comment insights. Timestamped transcript stored for reference. |
| Full | All: summary, transcript, comments, watch guide |

## Output Files

- `{date} - youtube - {title} ({video_id}).md` - Summary with metadata
- `{date} - youtube - {title} - transcript ({video_id}).md` - Cleaned transcript with timestamps
- `{date} - youtube - {title} - comments ({video_id}).md` - Curated comments
- `{date} - youtube - {title} - watch guide ({video_id}).md` - Watch guide with highlights (Full mode, WATCH/SKIM only)

Date is the video's upload date (YYYY-MM-DD). Falls back to no prefix if unavailable.

## Project Structure

```
scripts/             # CLI entry points (numbered by pipeline order)
  10_extract_metadata.py
  11_extract_transcript.py
  13_extract_comments.py
  20_check_existing.py
  21_prepare_update.py
  22_list_channel.py
  23_check_comment_growth.py
  30_clean_vtt.py
  31_format_transcript.py
  32_filter_comments.py
  33_merge_tier2.py
  40_backup.py
  41_update_metadata.py
  50_assemble.py
  templates/         # Markdown assembly templates (used by 50_assemble.py)
lib/                 # Importable library modules
formats/             # Summary format definitions (claim-bullets, step-list, ...)
subskills/           # LLM pipeline module instructions
SKILL.md             # Main skill definition
```

## Attribution

Youtube transcription skill is based on [tapestry-skills-for-claude-code](https://github.com/michalparkola/tapestry-skills-for-claude-code/blob/main/youtube-transcript/SKILL.md) youtube-transcript skill by Michał Parkoła.

## License

MIT, See [LICENSE](LICENSE) for more information.
