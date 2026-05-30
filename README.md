# Flow State - a Claude Plugin Marketplace

## **Youtube to Markdown Skill**

> **Skip the Video - Extract the Knowledge.**
> Transform streaming content into storagable knowledge as Markdown.
> Drop into Obsidian, Notion, or any note-taking system.

- ✨ **TL;DR + claim-bullets summary**: Bold claims with evidence — scannable, proportional to video length
- 💎 **Hidden Gems**: Tangents and details that normal summarization loses
- 🎛️ **Modular**: Choose output from Everything to Summary only, Transcript only, or Comments only
- 🧹 **Cleaned transcript**: Broken into chapters and paragraphs with topic headings into own file
- 🏷️ **Timestamp links**: Jump back to specific moments in the original video from the transcript
- 💬 **Comment analysis**: Curates and cross-analyzes comments against the summary
- 📐 **Adaptive formats**: Claim-bullets (default), themed-claims (long interviews), step-list (tutorials), flat-bullets (ultra-short)

## **IMAP Stream MCP Server**

> **Your Inbox, Minimal Context.**
> Lightweight IMAP email client. No destructive operations.

- 🪶 **~500 tokens** vs typical 15,000+ MCP servers - single tool with action dispatcher
- 📧 **Read & search**: List, read, and search IMAP folders
- ✍️ **Draft replies**: Markdown converted to HTML + plain text alternatives
- 📎 **Attachments**: Download for further processing
- 🔐 **Secure**: Credentials in OS keychain (or env variables for Docker/CI)
- 🛡️ **Content Safety**: Encapsulates email content to avoid context poisoning
- 🏢 **Multi-account**: Multiple account support with named switching

## **Chrome Control**

> **Your Browser, Your Agent's Eyes and Hands.**
> LLM agents can build deterministic shell scripts that drive your real browser — no Puppeteer, no Playwright, no separate profile. One CLI, your existing Chrome session, your cookies and logins.

- 🤖 **Scriptable by agents**: CLI commands compose into shell scripts — the LLM writes `chromectl` pipelines, not fragile browser automation code
- 🔗 **Auto-connect**: Connects to your running Chrome session (M144+) — all tabs, cookies, logins
- 🔌 **Daemon mode**: Single persistent WebSocket, Unix socket interface, no repeated permission dialogs
- 🧩 **DOM helpers**: get-text, get-html, exists, count, click, fill, scroll, wait — no boilerplate JS
- 📸 **Screenshots**: Viewport or full-page PNG capture
- 📋 **Console monitoring**: Stream live console output for a duration
- 🛠️ **Standalone CLI**: Works without an LLM too — `chromectl.py start` and go

## Latest Release Highlights

- **NEW** `chrome-control v1.0.0` — Chrome DevTools Protocol CLI and skill
  - Auto-connect to your running Chrome (M144+) — no separate profile needed
  - Daemon mode with persistent WebSocket and Unix socket interface
  - DOM helper commands: get-text, exists, count, click, fill, wait, and more
  - Forked from [pengelbrecht/chrome-debug-skill](https://github.com/pengelbrecht/chrome-debug-skill)

- `youtube-to-markdown v3.0.0` — Summary format overhaul: claim-bullets as default (TL;DR + claim list + Hidden Gems), themed-claims for long interviews, step-list for tutorials, flat-bullets for tips/short content. Prompt injection defense hardened to three layers. Bug fixes: channel dir prompt, N/A view counts hidden.

- `imap-stream-mcp v1.0.0` — Multi-account fix: `account` parameter now works across all actions. Injection defense module: NFKC normalization + invisible/BIDI strip, randomized nonce delimiters on all untrusted content reaching the LLM.

## Quick Start

### Installation

Add the marketplace and install:
```bash
/plugin marketplace add vre/flow-state

/plugin install youtube-to-markdown@flow-state
/plugin install imap-stream-mcp@flow-state
/plugin install chrome-control@flow-state
```

### Usage

**Youtube-to-Markdown:**
In your Claude Code:
```
extract https://www.youtube.com/watch?v=dQw4w9WgXcQ
```
('get', 'fetch', 'transcript', 'subtitles', 'captions', etc. works too)

**IMAP-Stream-MCP:**
In your Claude Code:
```
what email accounts I have?
```
As you don't have any configured yet, it will show you how to set up.

## Documentation

### Plugins
- [youtube-to-markdown](youtube-to-markdown/README.md) - Installation, usage, output options
- [imap-stream-mcp](imap-stream-mcp/README.md) - Configuration, actions, multi-account setup
- [chrome-control](chrome-control/README.md) - Chrome automation via CDP, CLI reference

## Examples of Youtube to Markdown Output

All examples are CC-licensed videos with summary and transcript.

| Format | Summary | Links |
| ----- | ------- | ----- |
| Flat bullets + comments | [Sourdough vs Normal Bread](examples/2022-04-07%20-%20Sourdough%20vs.%20%E2%80%9CNormal%E2%80%9D%20Bread.%20What%E2%80%99s%20the%20Difference%20(NieQHjCHnxg).md) | [comments](examples/2022-04-07%20-%20Sourdough%20vs.%20%E2%80%9CNormal%E2%80%9D%20Bread.%20What%E2%80%99s%20the%20Difference%20-%20comments%20(NieQHjCHnxg).md) · [transcript](examples/2022-04-07%20-%20Sourdough%20vs.%20%E2%80%9CNormal%E2%80%9D%20Bread.%20What%E2%80%99s%20the%20Difference%20-%20transcript%20(NieQHjCHnxg).md) · [video](https://www.youtube.com/watch?v=NieQHjCHnxg) |
| Flat bullets | [Interview with Senior JS Developer](examples/2022-01-31%20-%20Interview%20with%20Senior%20JS%20Developer%20(Uo3cL4nrGOk).md) | [transcript](examples/2022-01-31%20-%20Interview%20with%20Senior%20JS%20Developer%20-%20transcript%20(Uo3cL4nrGOk).md) · [video](https://www.youtube.com/watch?v=Uo3cL4nrGOk) |
| Step list + comments | [Faro Shuffle Tutorial!](examples/2017-08-17%20-%20Faro%20Shuffle%20Tutorial!%20(RXhNA0xLRgY).md) | [comments](examples/2017-08-17%20-%20Faro%20Shuffle%20Tutorial!%20-%20comments%20(RXhNA0xLRgY).md) · [transcript](examples/2017-08-17%20-%20Faro%20Shuffle%20Tutorial!%20-%20transcript%20(RXhNA0xLRgY).md) · [video](https://www.youtube.com/watch?v=RXhNA0xLRgY) |
| Claim bullets | [Brain: Parts & functions](examples/2019-09-13%20-%20Brain%20Parts%20%26%20functions%20Control%20%26%20Coordination%20Class%2010%20(DtkRGbTp1s8).md) | [transcript](examples/2019-09-13%20-%20Brain%20Parts%20%26%20functions%20Control%20%26%20Coordination%20Class%2010%20-%20transcript%20(DtkRGbTp1s8).md) · [video](https://www.youtube.com/watch?v=DtkRGbTp1s8) |
| Themed claims | [Blake Griffin — Blocks Podcast](examples/2025-04-03%20-%20Blake%20Griffin%20Blocks%20Podcast%20w%20Neal%20Brennan%20(0lYUIwLCuHs).md) | [transcript](examples/2025-04-03%20-%20Blake%20Griffin%20Blocks%20Podcast%20w%20Neal%20Brennan%20-%20transcript%20(0lYUIwLCuHs).md) · [video](https://www.youtube.com/watch?v=0lYUIwLCuHs) |
| Hybrid (claims + steps) | [Chef Eric Theiss — interview + cooking demo](examples/2020-09-29%20-%20Chief%20Chat%20Episode%2061%20Chef%20Eric%20Theiss%20(_qsUOPuX2FU).md) | [transcript](examples/2020-09-29%20-%20Chief%20Chat%20Episode%2061%20Chef%20Eric%20Theiss%20-%20transcript%20(_qsUOPuX2FU).md) · [video](https://www.youtube.com/watch?v=_qsUOPuX2FU) |

## The Backstory

I have been thinking a while to extract YouTube transcripts into Markdown format for my Obsidian vault. I knew of yt-dlp, but I wanted something more that would clean, format, summarize, analyze etc. LocalLlama was one option but never got the time.. Finally as checking out Claude Code skills in wild I thought that maybe there would be something already Done for Me. Well there was not, but I found one youtube skill to build upon. Four months later I added IMAP email access as well, as I wanted to have email reading and drafting capabilities in Claude Code in lightweight manner.

An LLM occasionally needs eyes and hands on the web — most existing browser automation solutions are fat (Puppeteer, Playwright, full MCP servers). After a bit of discovery I found [pengelbrecht's chrome-debug-skill](https://github.com/pengelbrecht/chrome-debug-skill), a clean single-file CDP client, and modernized it for Chrome M144+ auto-connect and daemon mode.

Many ideas for the future - maybe knowledge work, context management, and productivity tools for Claude Code and beyond. Let's see where this goes and is there time for it..

## Development
See [DEVELOPMENT.md](DEVELOPMENT.md).

## License

MIT, See [LICENSE](LICENSE) for more information.
