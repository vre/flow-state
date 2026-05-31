# Flow State — LLM Plugin Marketplace

**Claude Code**: first enter `/plugin marketplace add vre/flow-state` and then

| Plugin | Type | Install |
|--------|------|---------|
| [Youtube to Markdown](#youtube-to-markdown) | skill | `/plugin install youtube-to-markdown@flow-state` |
| [IMAP Slim MCP](#imap-slim-mcp) | mcp | `/plugin install imap-slim-mcp@flow-state` |
| [Chrome Control](#chrome-control) | skill | `/plugin install chrome-control@flow-state` |
| [Firefox Control](#firefox-control) | skill | `/plugin install firefox-control@flow-state` |

**Other Agents**: say to llm to install from `https://github.com/vre/flow-state/<plugin-name>`

---

## Youtube to Markdown

> **Skip the Video, Extract the Knowledge.**
> Transform streaming content into storable knowledge as Markdown.

- ✨ **TL;DR + claim-bullets summary** — bold claims with evidence, proportional to video length
- 🎛️ **Modular** — choose from full extraction, summary only, transcript only, or comments only
- 🧹 **Cleaned transcript** — broken into chapters and paragraphs with topic headings
- 💬 **Comment analysis** — curates and cross-analyzes comments against the summary
- 📐 **Adaptive formats** — claim-bullets, themed-claims, step-list, or flat-bullets based on content type

[Full documentation →](youtube-to-markdown/README.md) · [Examples →](examples/README.md)

## IMAP Slim MCP

> **Your Inbox, Minimal Context.**
> Lightweight IMAP email client. No destructive operations.

- 🪶 **~500 tokens** vs typical 15,000+ MCP servers — single tool with action dispatcher
- 📧 **Read & search** — list, read, and search IMAP folders
- ✍️ **Draft replies** — markdown converted to HTML + plain text alternatives
- 🔐 **Secure** — credentials in OS keychain (or env variables for Docker/CI)
- 🏢 **Multi-account** — multiple account support with named switching

[Full documentation →](imap-slim-mcp/README.md)

## Chrome Control

> **Your Browser, Your Agent's Eyes and Hands.**
> One CLI, your existing Chrome session, your cookies and logins.

- 🔗 **Auto-connect** — connects to your running Chrome session (M144+), all tabs, cookies, logins
- 🔌 **Daemon mode** — single persistent WebSocket, Unix socket interface, no repeated permission dialogs
- 🧩 **DOM helpers** — get-text, get-html, exists, count, click, fill, scroll, wait
- 📸 **Screenshots** — viewport or full-page PNG capture
- 🛠️ **Standalone CLI** — works without an LLM too

[Full documentation →](chrome-control/README.md)

## Firefox Control

> **Firefox, handicapped Eyes and Hands for an LLM.**
> Control Firefox while it announces to the whole world that it is a bot.

- ⚠️ **Test tool** — `navigator.webdriver=true` on all remote debugging sessions, every anti-bot system detects it
- 🔌 **Direct BiDi** — native Firefox WebSocket, no geckodriver, no Selenium
- 🔧 **Same CLI surface** — commands mirror chromectl: list, eval, screenshot, DOM helpers
- 🏗️ **Daemon mode** — persistent BiDi session, stable context IDs, Unix socket

[Full documentation →](firefox-control/README.md)

---

## Release Highlights

- **NEW** `firefox-control v0.1.0` — WebDriver BiDi CLI for Firefox (test tool)
  - Direct BiDi WebSocket, daemon mode, DOM helpers
  - Proves that BiDi works and was quite easy actually to set up

- **NEW** `chrome-control v1.0.0` — Chrome DevTools Protocol CLI and skill
  - Auto-connect to your running Chrome (M144+), no separate profile needed
  - Daemon mode with persistent WebSocket and Unix socket interface
  - DOM helper commands: get-text, exists, count, click, fill, wait, and more
  - Forked base from [pengelbrecht/chrome-debug-skill](https://github.com/pengelbrecht/chrome-debug-skill)

- **UPDATE** `youtube-to-markdown v3.0.0` — Summary format overhaul: claim-bullets as default, themed-claims for long interviews, step-list for tutorials. Prompt injection defense hardened to three layers.

- **UPDATE** `imap-slim-mcp v1.0.0` — Multi-account fix, injection defense module with NFKC normalization and randomized nonce delimiters.

## The Backstory

How to extract YouTube transcripts as Markdown summaries to my Obsidian vault? I knew of yt-dlp, but I wanted something more that would clean, format, summarize, analyze etc. LocalLLM was one option but never got the time.. Finally as checking out Claude Code skills in wild I thought that maybe there would be something already Done for Me. Well there was not, only something to build upon.

Four months later I added MCP server for IMAP email access as well, as I wanted to have email reading and drafting capabilities in Claude Code in lightweight manner.

Not so long after that I was playing with playwrights etc. as an LLM occasionally needs eyes and hands on the web. Most existing browser automation solutions are fat (Puppeteer, Playwright, full MCP servers). I found [pengelbrecht's chrome-debug-skill](https://github.com/pengelbrecht/chrome-debug-skill), a clean single-file legacy CDP client, that I then modernized for more recent Chrome CDP.

## Development

See [DEVELOPMENT.md](DEVELOPMENT.md) and [TESTING.md](TESTING.md).

## License

MIT. See [LICENSE](LICENSE).
