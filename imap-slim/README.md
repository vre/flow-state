# IMAP Slim

Lightweight IMAP email client for Claude Desktop/Code/Cowork, available two ways from one package:

- **`imap-slim-mcp`** — an MCP server. Its tool schema loads into every session that has it enabled.
- **`imap-slim-cli`** — the same actions as a skill-backed CLI. Costs a session nothing until a
  command runs, which is the difference between ~41 and ~814 tokens for a session that never
  touches mail.

Both dispatch through the same `run_action`, so they cannot drift apart.

Inspired by [Jesse Vincent's MCP design philosophy](https://blog.fsck.com/2025/10/19/mcps-are-not-like-other-apis/):
- **~500 tokens** vs typical 15,000+ token MCP servers
- Single `use_mail` tool with action dispatcher
- Self-documenting via `help` action
- Credentials stored securely in OS keychain

## Features

- **list** - List messages in any folder (`[att:N]` attachment count, `preview` for body snippet)
- **read** - Read message content with attachments
- **search** - Search by sender, subject, date, or text (`[att:N]` attachment count, `preview` for body snippet)
- **create** - Write a new draft (an IMAP `APPEND`), with file attachments. With `quote` it is a
  reply: the client quotes the original, HTML included, and sets the threading
- **replace** - Supersede an existing draft. IMAP messages are immutable, so this appends the new
  version and expunges the one it replaces; **the draft gets a new id**
- **flag** - Add/remove flags and labels (Seen, Flagged, Deleted, $label1, etc.)
- **folders** - List available folders
- **accounts** - List configured email accounts
- **attachment** - Download attachments to temp directory (`{tempdir}/streammail/`)
- **cleanup** - Remove downloaded attachments (auto-cleared on reboot on macOS/Linux, persists on Windows until user cleans)
- **help** - Built-in documentation

## Install

### Claude Code

```bash
claude plugin marketplace add vre/flow-state
claude plugin install imap-slim-mcp@flow-state
```

Or install the CLI instead, as a skill:

```bash
claude plugin install imap-slim-cli@flow-state
```

Then configure credentials (see below).

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "imap-slim": {
      "command": "uv",
      "args": ["--directory", "/path/to/imap-slim", "run", "imap-slim"]
    }
  }
}
```

### Other Coding Agents

Tell your LLM to install the MCP server from `https://github.com/vre/flow-state/imap-slim`

### Manual

```bash
cd flow-state/imap-slim
uv sync
claude mcp add imap-slim -- uv --directory $(pwd) run imap-slim
```
(you can define the [installation scope](https://code.claude.com/docs/en/mcp#mcp-installation-scopes) with "claude mcp add --scope local|user|project ...")

## Configuration

### OS Keychain (Recommended)

`python setup.py` with no arguments offers add, update, remove and set-default. Updating shows each
current value in brackets — Enter keeps it, typing replaces it — including the account name, so
renaming moves the stored keys with it. An empty password keeps the stored one. Each account also
has a From address, since an IMAP login is not always one.

```bash
uv run python setup.py                 # Interactive setup
uv run python setup.py --add work      # Add named account
uv run python setup.py --list          # Show accounts
uv run python setup.py --default work  # Set default
uv run python setup.py --remove work   # Remove account
```

### Environment Variables (Automation/Docker)

Add to your MCP config:

```json
"env": {
  "IMAP_SLIM_SERVER": "imap.example.com",
  "IMAP_SLIM_USERNAME": "you@example.com",
  "IMAP_SLIM_PASSWORD": "app-password"
}
```

> `IMAP_STREAM_*` env vars still work for backward compatibility.

## Workflow: Reply to Email

1. **List today's messages from INBOX** to find the one you want
2. **Read it** to load the content into context
3. **Answer it** — Claude writes only the new text; `create` with `quote` fetches the original and
   builds the quote, attribution, `Re:` subject, recipient and threading headers
4. **Review and send** from your mail client's Drafts

An HTML message is quoted by its own markup, with its inline images, in the shape Thunderbird uses
— write above it. To answer point by point, plain text only: `read` with `:quote` gives a block to
write between, and every quoted line is checked against the original before the draft is written.

## Limitations

- **`replace` does not keep inline images.** One without a filename is dropped; one with a filename
  becomes an ordinary attachment, detached from the markup. Quoting in `create` does carry them.
- **Point-by-point replies are plain text only.** Splicing between the lines of someone else's HTML
  is not something this client does.
- **There is no edit.** IMAP messages are immutable. Nothing stores the markdown you wrote — only
  its two renderings — so keep your source and send the whole body again to change a draft.
- **A replaced draft gets a new id.** Any id held across a `replace` is stale.
- **Fenced code blocks must start at the left margin**, matching python-markdown's `fenced_code`.
  A fence indented, or inside a list or blockquote, is not a fence.

## Security

- **One deletion, and only one, scoped to one message.** `replace` expunges the draft it
  supersedes, using `uid_expunge` so that only that message is removed. A bare `EXPUNGE` would take
  every `\Deleted` message in the mailbox with it. `replace` is refused outside the Drafts folder,
  and on a server without UIDPLUS nothing is expunged at all — the superseded draft is left marked.
  No `expunge` action is exposed. `flag ... +Deleted` marks a message and stops there; your mail
  client does the deleting.
- **Content safety** - Email content encapsulated to prevent prompt injection / context poisoning
- **Keychain storage** - Credentials in system keychain (macOS Keychain, Windows Credential Manager, Linux Secret Service)
- **No credential leaks** - Password fetched by script only when IMAP connection opens, LLM never sees the password
- **Encrypted connection** - SSL/TLS required

## For maintainers

Decisions with tradeoffs are in [docs/imap-slim/adrs/](../docs/imap-slim/adrs/); what is not
verified is in [TODO.md](TODO.md).

## Project Structure

```
actions.py           # the eleven actions, defined once; both front-ends dispatch here
imap_stream_mcp.py   # MCP front-end: the FastMCP wrapper (legacy module name)
imapctl.py           # CLI front-end: stateless, connects and exits
SKILL.md             # what the skill loads when invoked
render.py            # shared rendering and error classification
imap_client.py       # IMAP operations (list, read, search, create, replace)
bodystructure.py     # BODYSTRUCTURE parsing (attachments, snippets)
session.py           # connection lease, caching, message fetch
markdown_utils.py    # markdown → HTML + plain alternative
setup.py             # credential configuration utility
debug_imap.py        # connection troubleshooting utility
mcp-server.json      # MCP config, named explicitly by the marketplace entry.
                     # NOT .mcp.json: that is auto-discovered at a plugin root
                     # and would start the server for the CLI install too
```

## API Reference

```
# List messages (preview: true for body snippets, false for headers only)
{action: "list", folder: "INBOX", preview: true}
{action: "list", folder: "INBOX", preview: false, limit: 50}

# Read message
{action: "read", folder: "INBOX", payload: "12345"}
{action: "read", folder: "INBOX", payload: "12345:full"}  # include full quoted tail
{action: "read", folder: "INBOX", payload: "12345:quote"} # quote block for a point-by-point reply

# Search (preview: true for body snippets)
{action: "search", folder: "INBOX", payload: "from:boss@company.com", preview: true}
{action: "search", folder: "INBOX", payload: "subject:urgent", preview: false}
{action: "search", folder: "INBOX", payload: "since:2024-01-01", preview: true}

# Create draft
{action: "create", format: "markdown", payload: '{"to":"x@y.com","subject":"Hi","body":"**Hello**"}'}

# Reply: only the body; the client quotes INBOX:12345 and sets recipient, subject and threading
{action: "create", format: "markdown", quote: "INBOX:12345", payload: '{"body":"Thanks!"}'}

# Replace a draft (appends a new version, expunges the old; the id changes)
{action: "replace", folder: "Drafts", format: "markdown", payload: '{"id": 1444, "body": "12 ducks"}'}

# Flag messages
{action: "flag", folder: "INBOX", payload: "123:+Flagged"}
{action: "flag", folder: "INBOX", payload: "123:-Seen"}
{action: "flag", folder: "INBOX", payload: "123,124,125:+Deleted"}
{action: "flag", folder: "INBOX", payload: "123:+$label1"}

# List folders
{action: "folders"}

# List accounts
{action: "accounts"}

# Download attachment (first attachment from message 1253)
{action: "attachment", folder: "INBOX", payload: "1253:0"}

# Clean up downloaded attachments
{action: "cleanup"}

# Help
{action: "help"}
{action: "help", payload: "create"}
```

### Multi-Account

```
# Use default account
{action: "list", folder: "INBOX", preview: true}

# Use specific account
{action: "list", folder: "INBOX", account: "work", preview: false}
```

## Release Highlights

- **v2.1.0** — Replies: the client quotes the original, HTML and inline images included, with
  point-by-point replies for plain text.
- **v2.0.0** — Skill-backed CLI alongside the MCP; `create`/`replace` named after IMAP; draft
  format required; connection recovery in ~0.2 s.
- **v1.0.0** — Multi-account fix, injection defense module with NFKC normalization and randomized nonce delimiters.

## License

MIT, See [LICENSE](LICENSE) for more information.
