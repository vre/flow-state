# Flow State - a Claude Plugin Marketplace

YouTube extraction and email integration.

## Skills

**Youtube to Markdown** - Transform streaming content into storagable knowledge as Markdown.
- ✨ **TL;DR + structured summary**: Core insights with four content spesific summarization formats
- 💎 **Hidden Gems**: Collects insights that normal summarization loses
- 🧹 **Cleaned transcript**: Broken into chapters and paragraphs with topic headings into own file
- 🏷️ **Timestamp links**: Jump back to specific moments in the original video from the transcript
- 💬 **Comment analysis**: Curates and cross-analyzes comments against the summary

**Youtube Comment Analysis** - Filter out the content from the cesspool.
- 🥇 **Comment insights**: Curates top voted comments and discussion threads
- 🗑️ **Spam-free**: Filters low-value comments, duplicates, and off-topic noise
- ⚔️ **Solo-analysis**: Optional standalone comment analysis without transcript

**Skip the Video - Get the Knowledge.**

**Markdown ready**: Drop into Obsidian, Notion, or any note-taking system

## MCP Servers

**IMAP Stream MCP** - Lightweight email client.
- 🪶 **~500 tokens** vs typical 15,000+ MCP servers - single tool with action dispatcher
- 📧 **Read & search**: List, read, and search IMAP folders
- ✍️ **Draft replies**: Markdown converted to HTML + plain text alternatives
- 📎 **Attachments**: Download for further processing
- 🔐 **Secure**: Credentials in OS keychain (or env variables for Docker/CI)
- 🏢 **Multi-account**: Multiple email account support with named switching

## Quick Start

**Installation:**

Add the marketplace and install skills:
```bash
/plugin marketplace add vre/flow-state

/plugin install youtube-to-markdown@flow-state
/plugin install youtube-comment-analysis@flow-state
/plugin install imap-stream-mcp@flow-state
```

Configure IMAP (first use will show setup instructions).

**Usage:**

```
extract https://www.youtube.com/watch?v=dQw4w9WgXcQ

('get', 'fetch', 'transcript', 'subtitles', 'captions', etc. works too)
```

Or for comments only
```
comments https://www.youtube.com/watch?v=dQw4w9WgXcQ
```

## Examples

All examples are CC-licensed videos with full summary and comment analysis.

| Type | Summary | Links |
|------|---------|-------|
| Tutorial | [Faro Shuffle Tutorial!](examples/youtube%20-%20Faro%20Shuffle%20Tutorial!%20(RXhNA0xLRgY).md) | [transcript](examples/youtube%20-%20Faro%20Shuffle%20Tutorial!%20-%20transcript%20(RXhNA0xLRgY).md) · [video](https://www.youtube.com/watch?v=RXhNA0xLRgY) |
| Educational | [Brain: Parts & functions](examples/youtube%20-%20Brain%20Parts%20%26%20functions%20(Fore,%20mid%20%26%20hind)%20Control%20%26%20(DtkRGbTp1s8).md) | [transcript](examples/youtube%20-%20Brain%20Parts%20%26%20functions%20(Fore,%20mid%20%26%20hind)%20Control%20%26%20-%20transcript%20(DtkRGbTp1s8).md) · [video](https://www.youtube.com/watch?v=DtkRGbTp1s8) |
| Educational | [Happiness is all in your mind](examples/youtube%20-%20Happiness%20is%20all%20in%20your%20mind%20Gen%20Kelsang%20Nyema%20at%20(xnLoToJVQH4).md) | [transcript](examples/youtube%20-%20Happiness%20is%20all%20in%20your%20mind%20Gen%20Kelsang%20Nyema%20at%20-%20transcript%20(xnLoToJVQH4).md) · [video](https://www.youtube.com/watch?v=xnLoToJVQH4) |
| Tips | [How to Become a Great Software Developer](examples/youtube%20-%20How%20to%20Become%20a%20Great%20Software%20Developer%20—%20Best%20Advice%20from%20(suATPK45sjk).md) | [transcript](examples/youtube%20-%20How%20to%20Become%20a%20Great%20Software%20Developer%20—%20Best%20Advice%20from%20-%20transcript%20(suATPK45sjk).md) · [video](https://www.youtube.com/watch?v=suATPK45sjk) |
| Tips | [Sourdough vs Normal Bread](examples/youtube%20-%20Sourdough%20vs%20Normal%20Bread%20-%20Whats%20the%20Difference%20(NieQHjCHnxg).md) | [transcript](examples/youtube%20-%20Sourdough%20vs%20Normal%20Bread%20-%20Whats%20the%20Difference%20-%20transcript%20(NieQHjCHnxg).md) · [video](https://www.youtube.com/watch?v=NieQHjCHnxg) |
| Interview | [Chris Rock on starting standup](examples/youtube%20-%20Chris%20Rock%20on%20starting%20standup%20How%20Neal%20Feel%20podcast%20(Ep%2077)%20(M6rBiCnntng).md) | [transcript](examples/youtube%20-%20Chris%20Rock%20on%20starting%20standup%20How%20Neal%20Feel%20podcast%20(Ep%2077)%20-%20transcript%20(M6rBiCnntng).md) · [video](https://www.youtube.com/watch?v=M6rBiCnntng) |
| Interview | [Interview with Senior JS Developer](examples/youtube%20-%20Interview%20with%20Senior%20JS%20Developer%20(Uo3cL4nrGOk).md) | [transcript](examples/youtube%20-%20Interview%20with%20Senior%20JS%20Developer%20-%20transcript%20(Uo3cL4nrGOk).md) · [comments](examples/youtube%20-%20Interview%20with%20Senior%20JS%20Developer%20-%20comments%20(Uo3cL4nrGOk).md) · [video](https://www.youtube.com/watch?v=Uo3cL4nrGOk) |

## Available Skills

### youtube-to-markdown

Transform YouTube videos into storagable knowledge. Get TL;DR, content-specific summary, separate file with cleaned transcript broken into paragraphs with topic headings and timestamp links. Continues analyzing comments to bring the audience view to the content.

- **Category**: Media Extraction
- **Dependencies**: yt-dlp, Python 3
- **Output**: Markdown file with metadata, summary, description, and formatted transcript

### youtube-comment-analysis

Extract and analyze YouTube comments. Supports standalone or sequential workflows.

- **Category**: Media Extraction
- **Dependencies**: yt-dlp, Python 3
- **Output**: Markdown file with comment insights and curated comments
- **Modes**:
  - Sequential: Adds viewpoints from comments to video summary
  - Standalone: Analyzes comments only

## The Backstory

I have been thinking a while to extract YouTube transcripts into Markdown format for my Obsidian vault. I knew of yt-dlp, but I wanted something more that would clean, format, summarize, analyze etc. LocalLlama was one option but never got the time.. Finally as checking out Claude Code skills in wild I thought that maybe there would be something already Done for Me. Well there was not, but I found a youtube extractor skill to build upon.

Many ideas for the future - maybe knowledge work, context management, and productivity tools for Claude Code and beyond. Let's see where this goes and is there time for it..

## Development

See [Development](docs/Development.md)

## Attribution

Youtube transcript download based on [tapestry-skills-for-claude-code](https://github.com/michalparkola/tapestry-skills-for-claude-code) youtube-transcript skill by Michał Parkoła.

## License

MIT, See [LICENSE](LICENSE) for more information.
