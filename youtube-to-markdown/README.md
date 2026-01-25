# YouTube to Markdown

Transform YouTube videos into storable knowledge as Markdown.

## Features

- **TL;DR + structured summary** - Core insights with content-specific summarization
- **Hidden Gems** - Insights that normal summarization loses
- **Cleaned transcript** - Chapters and paragraphs with topic headings
- **Timestamp links** - Jump back to specific moments in the video
- **Comment analysis** - Curated comments cross-analyzed against summary

## Installation

```bash
/plugin marketplace add vre/flow-state
/plugin install youtube-to-markdown@flow-state
```

### Dependencies

- Python 3
- yt-dlp (`brew install yt-dlp` or `pip install yt-dlp`)

## Usage

```
extract https://www.youtube.com/watch?v=VIDEO_ID
```

Also works: `get`, `fetch`, `transcript`, `subtitles`, `captions`

## Output Options

When invoked, you choose what to extract:

| Option | Output |
|--------|--------|
| Summary only | Summary with TL;DR and key insights |
| Transcript only | Cleaned, formatted full transcript |
| Comments only | Curated top comments |
| Summary + Comments | Summary with cross-analyzed comment insights |
| Full | All: summary, transcript, comments |

## Output Files

- `youtube_{video_id}.md` - Summary with metadata
- `youtube_{video_id}_transcript.md` - Cleaned transcript with timestamps
- `youtube_{video_id}_comments.md` - Curated comments

## License

MIT
