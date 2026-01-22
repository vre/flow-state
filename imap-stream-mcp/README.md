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
- **draft** - Create/modify draft replies
- **folders** - List available folders
- **accounts** - List configured email accounts
- **attachment** - Download attachments
- **help** - Built-in documentation

## Installation

### Plugin

```bash
/plugin marketplace add vre/flow-state
/plugin install imap-stream-mcp@flow-state
```

Then configure credentials (see below).

### Manual

```bash
git clone https://github.com/vre/flow-state.git
cd flow-state/imap-stream-mcp
uv sync
claude mcp add imap-stream -- uv --directory $(pwd) run imap-stream
```

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

## Claude Desktop (Manual)

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

## Usage

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

## Multi-Account Usage

```
# Use default account
{action: "list", folder: "INBOX"}

# Use specific account
{action: "list", folder: "INBOX", account: "work"}
```

## Workflow: Reply to Email

1. **List messages** to find the one you want
2. **Read the message** to see content and Message-ID
3. **Create draft** with Claude's help
4. **Open email client** → Drafts → Review and send

## Security

- Credentials in system keychain (macOS Keychain, Windows Credential Manager, Linux Secret Service)
- Password fetched only when IMAP connection opens
- Password never in logs or output
- SSL/TLS connection

## License

MIT
