# IMAP Stream MCP

Lightweight IMAP email client for Claude Desktop/Code/Cowork.

Inspired by [Jesse Vincent's MCP design philosophy](https://blog.fsck.com/2025/10/19/mcps-are-not-like-other-apis/):
- **~500 tokens** vs typical 15,000+ token MCP servers
- Single `use_mail` tool with action dispatcher
- Self-documenting via `help` action
- Credentials stored securely in OS keychain

## Features

- **list** - List messages in any folder
- **read** - Read message content with attachments
- **search** - Search by sender, subject, date, or text
- **draft** - Create/modify draft replies with file attachments
- **edit** - Surgical draft text replacement (old→new) without full body rewrite
- **flag** - Add/remove flags and labels (Seen, Flagged, Deleted, $label1, etc.)
- **folders** - List available folders
- **accounts** - List configured email accounts
- **attachment** - Download attachments to temp directory (`{tempdir}/streammail/`)
- **cleanup** - Remove downloaded attachments (auto-cleared on reboot on macOS/Linux, persists on Windows until user cleans)
- **help** - Built-in documentation

## Installation for Claude Code

### As a Plugin

```bash
/plugin marketplace add vre/flow-state
/plugin install imap-stream-mcp@flow-state
```

Then configure credentials (see below).

### Manual Installation

```bash
git clone https://github.com/vre/flow-state.git
cd flow-state/imap-stream-mcp
uv sync
claude mcp add imap-stream -- uv --directory $(pwd) run imap-stream
```
(you can define the [installation scope](https://code.claude.com/docs/en/mcp#mcp-installation-scopes) with "claude mcp add --scope local|user|project ...")

## Configuration

### Option 1: OS Keychain (Recommended)

```bash
uv run python setup.py                 # Interactive setup
uv run python setup.py --add work      # Add named account
uv run python setup.py --list          # Show accounts
uv run python setup.py --default work  # Set default
uv run python setup.py --remove work   # Remove account
```

### Option 2: Environment Variables (Automation/Docker)

Add to your MCP config:

```json
"env": {
  "IMAP_STREAM_SERVER": "imap.example.com",
  "IMAP_STREAM_USERNAME": "you@example.com",
  "IMAP_STREAM_PASSWORD": "app-password"
}
```

## Installation for Claude Desktop (Manual)

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "imap-stream": {
      "command": "uv",
      "args": ["--directory", "/path/to/imap-stream-mcp", "run", "imap-stream"]
    }
  }
}
```

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
imap_stream_mcp.py   # MCP server entry point, action dispatcher
imap_client.py       # IMAP operations (list, read, search, draft)
markdown_utils.py    # Markdown → HTML conversion for drafts
setup.py             # Credential configuration utility
debug_imap.py        # Connection troubleshooting utility
.mcp.json            # MCP server configuration for plugin install
```

## MCP API - Usage

```
# List messages
{action: "list", folder: "INBOX"}
{action: "list", folder: "INBOX", limit: 50}

# Read message
{action: "read", folder: "INBOX", payload: "12345"}

# Search
{action: "search", folder: "INBOX", payload: "from:boss@company.com"}
{action: "search", folder: "INBOX", payload: "subject:urgent"}
{action: "search", folder: "INBOX", payload: "since:2024-01-01"}

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

## MCP API - Multi-Account Usage

```
# Use default account
{action: "list", folder: "INBOX"}

# Use specific account
{action: "list", folder: "INBOX", account: "work"}
```

## License

MIT, See [LICENSE](LICENSE) for more information.
