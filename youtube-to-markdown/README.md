# YouTube to Markdown

Transform YouTube videos into storable knowledge as Markdown.

- **TL;DR + structured summary** - Core insights with content-specific summarization
- **Hidden Gems** - Insights that normal summarization loses
- **Modular output** - Choose from summary, transcript, comments, or all

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

## Install

### Claude Code

```bash
claude plugin marketplace add vre/flow-state
claude plugin install youtube-to-markdown@flow-state
```

### Other Coding Agents

Tell your LLM to install the skill from `https://github.com/vre/flow-state/youtube-to-markdown`

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

## Security

Defends against prompt injection in YouTube content (descriptions, comments, transcripts). Three layers: NFKC normalization + Unicode format-character strip, iterative stripping of chat-template tokens (`<|im_start|>`, `[INST]`, `<<SYS>>`, role tags), and per-call randomized spotlight delimiters with 64-bit nonce. Content is wrapped and labeled as untrusted so the model treats it as data, not instructions.

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

## Release Highlights

- **v3.0.0** — Summary format overhaul: claim-bullets as default, themed-claims for long interviews, step-list for tutorials. Prompt injection defense hardened to three layers.
- **v2.15.0** — Paragraph break detection moved to script (eliminates 100K+ token improvised Python); deterministic transcript structure. Watch guide with WATCH/SKIM/READ-ONLY gate.

## Attribution

Youtube transcription skill is based on [tapestry-skills-for-claude-code](https://github.com/michalparkola/tapestry-skills-for-claude-code/blob/main/youtube-transcript/SKILL.md) youtube-transcript skill by Michał Parkoła.

## License

MIT, See [LICENSE](LICENSE) for more information.
