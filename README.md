# Flow State - a Claude Plugin Marketplace

For now Youtube extraction.

## Skills

**Youtube to Markdown** - Transform streaming content into storagable knowledge.
- ✨ **TL;DR + structured summary**: Core insights, What/Why/How analysis, Hidden Gems
- 🧹 **Cleaned transcript**: Broken into chapters and paragraphs with topic headings
- 🏷️ **Timestamp links**: Jump back to specific moments in the original video
- 🎁 **Markdown ready**: Drop into Obsidian, Notion, or any note-taking system

**Youtube Comment Analysis** - Filter out the content from the cesspool.
- 🥇 **Golden insights**: Curated exceptional comments
- ⚔️ **Cross-analysis**: Optional integration with youtube-to-markdown for summary comparison
- 🗑️ **Spam-free**: Filters low-value comments, duplicates, and off-topic noise

**Skip the Video - Get the Knowledge.**

## Quick Start

**Installation:**

Add the marketplace and install skills:
```
/plugin marketplace add vre/flow-state
/plugin install youtube-to-markdown@flow-state
/plugin install youtube-comment-analysis@flow-state
```

**Usage:**

```
Hello, would you be kind and help me by running the a skill so that I could read the
transcription of the video and add it to my ever growing Obsidian vault? Oh, and could
you also dive in the cesspool for meee.. I mean the comments section and get me
something I can read without burning eyes?

or..

extract https://www.youtube.com/watch?v=dQw4w9WgXcQ

('get', 'fetch', 'transcript', 'subtitles', 'captions', etc. works too)
```

Or for comments only
```
get comments https://www.youtube.com/watch?v=dQw4w9WgXcQ
```

See an example output in [docs/Example Output.md](docs/Example%20Output.md)

## Available Skills

### youtube-to-markdown

Transform YouTube videos into storagable knowledge. Get TL;DR summaries, cleaned transcripts with chapters, and timestamp links.

- **Category**: Media Extraction
- **Dependencies**: yt-dlp, Python 3
- **Output**: Markdown file with metadata, summary, description, and formatted transcript

### youtube-comment-analysis

Extract and analyze YouTube comments. Supports standalone or sequential workflows.

- **Category**: Media Extraction
- **Dependencies**: yt-dlp, Python 3
- **Output**: Markdown file with golden insights and curated comments
- **Modes**:
  - Standalone: Comment analysis
  - Sequential: Cross-analysis with video summary from youtube-to-markdown

## The Backstory

I have been thinking a while to extract YouTube transcripts into Markdown format for my Obsidian vault. I knew of yt-dlp, but I wanted something more that would clean, format, summarize, analyze etc. LocalLlama was one option but never got the time.. Finally as checking out Claude Code skills in wild I thought that maybe there would be something already Done for Me. Well there was not, but I found a youtube extractor skill to build upon.

Many ideas for the future - maybe knowledge work, context management, and productivity tools for Claude Code and beyond. Let's see where this goes and is there time for it..

## Development

See [Development](docs/Development.md)

## Attribution

Youtube transcript download based on [tapestry-skills-for-claude-code](https://github.com/michalparkola/tapestry-skills-for-claude-code) youtube-transcript skill by Michał Parkoła.

## License

MIT, See [LICENSE](LICENSE) for more information.
