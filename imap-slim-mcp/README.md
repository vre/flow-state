# IMAP Slim MCP

Lightweight IMAP email client for Claude Desktop/Code/Cowork.

Inspired by [Jesse Vincent's MCP design philosophy](https://blog.fsck.com/2025/10/19/mcps-are-not-like-other-apis/):
- **~500 tokens** vs typical 15,000+ token MCP servers
- Single `use_mail` tool with action dispatcher
- Self-documenting via `help` action
- Credentials stored securely in OS keychain

## Features

- **list** - List messages in any folder (`[att:N]` attachment count, `preview` for body snippet)
- **read** - Read message content with attachments
- **search** - Search by sender, subject, date, or text (`[att:N]` attachment count, `preview` for body snippet)
- **draft** - Create/modify draft replies with file attachments
- **edit** - Surgical draft text replacement (old→new) without full body rewrite
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

Then configure credentials (see below).

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "imap-slim": {
      "command": "uv",
      "args": ["--directory", "/path/to/imap-slim-mcp", "run", "imap-slim"]
    }
  }
}
```

### Other Coding Agents

Clone the repo and add the MCP server:

```bash
git clone https://github.com/vre/flow-state.git
cd flow-state/imap-slim-mcp
uv sync
```

The MCP server config is in `imap-slim-mcp/.mcp.json`. How to load it depends on the agent:

- **GitHub Copilot** — add to `.github/copilot-mcp.json`
- **OpenAI Codex** — add to MCP config or pass via `--mcp-config`
- **Cursor / Windsurf** — add to MCP settings

### Manual

```bash
git clone https://github.com/vre/flow-state.git
cd flow-state/imap-slim-mcp
uv sync
claude mcp add imap-slim -- uv --directory $(pwd) run imap-slim
```
(you can define the [installation scope](https://code.claude.com/docs/en/mcp#mcp-installation-scopes) with "claude mcp add --scope local|user|project ...")

## Configuration

### OS Keychain (Recommended)

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

1. **List todays messages from INBOX** to find the email one you want
2. **Read the message from XXX** to load the content into context
3. **I would like to answer...** create reply with Claude's help
4. **Send via email client** → Drafts → Review and send

## Limitations

- **Draft operations are for user-composed content.** Editing drafts originally created in rich email clients (Outlook, Gmail) may lose inline images and complex formatting. The `edit` and `draft` actions reconstruct MIME structure from plain text/HTML — embedded `cid:` image references are not preserved.

## Security

- **No destructive operations** - No EXPUNGE, no permanent deletion. `\Deleted` flag only marks messages (recoverable). Creates/modifies drafts in Drafts folder only.
- **Content safety** - Email content encapsulated to prevent prompt injection / context poisoning
- **Keychain storage** - Credentials in system keychain (macOS Keychain, Windows Credential Manager, Linux Secret Service)
- **No credential leaks** - Password fetched by script only when IMAP connection opens, LLM never sees the password
- **Encrypted connection** - SSL/TLS required

## Project Structure

```
imap_stream_mcp.py   # MCP server (legacy module name, kept for compatibility)
imap_client.py       # IMAP operations (list, read, search, draft)
bodystructure.py     # BODYSTRUCTURE parsing (attachments, snippets)
session.py           # Connection management, caching, message fetch
markdown_utils.py    # Markdown → HTML conversion for drafts
setup.py             # Credential configuration utility
debug_imap.py        # Connection troubleshooting utility
.mcp.json            # MCP server configuration for plugin install
```

## API Reference

```
# List messages (preview: true for body snippets, false for headers only)
{action: "list", folder: "INBOX", preview: true}
{action: "list", folder: "INBOX", preview: false, limit: 50}

# Read message
{action: "read", folder: "INBOX", payload: "12345"}
{action: "read", folder: "INBOX", payload: "12345:full"}  # include full quoted tail

# Search (preview: true for body snippets)
{action: "search", folder: "INBOX", payload: "from:boss@company.com", preview: true}
{action: "search", folder: "INBOX", payload: "subject:urgent", preview: false}
{action: "search", folder: "INBOX", payload: "since:2024-01-01", preview: true}

# Create draft
{action: "draft", payload: '{"to":"x@y.com","subject":"Re: Hi","body":"Thanks!","in_reply_to":"<msgid>"}'}

# Edit draft (surgical replacement)
{action: "edit", folder: "Drafts", payload: '{"id": 1444, "replacements": [{"old": "11 ducks", "new": "12 ducks"}]}'}

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
{action: "help", payload: "draft"}
```

### Multi-Account

```
# Use default account
{action: "list", folder: "INBOX", preview: true}

# Use specific account
{action: "list", folder: "INBOX", account: "work", preview: false}
```

## Release Highlights

- **v1.0.0** — Multi-account fix, injection defense module with NFKC normalization and randomized nonce delimiters.

## License

MIT, See [LICENSE](LICENSE) for more information.
