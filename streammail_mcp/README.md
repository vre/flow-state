# Streammail MCP

Lightweight IMAP email client for Claude Desktop/Code/Cowork.

Inspired by [Jesse Vincent's MCP design philosophy](https://blog.fsck.com/2025/10/19/mcps-are-not-like-other-apis/):
- **~500 tokens** vs typical 15,000+ token MCP servers
- Single `use_mail` tool with action dispatcher
- Self-documenting via `help` action
- Credentials stored securely in OS keychain

## Features

- **list** - List messages in any IMAP folder
- **read** - Read message content
- **search** - Search by sender, subject, date, or text
- **draft** - Create draft replies (saved to IMAP Drafts folder)
- **folders** - List available folders
- **help** - Built-in documentation

## Installation

```bash
cd streammail

# Install dependencies with uv
uv sync

# Configure IMAP credentials (stored in macOS Keychain)
uv run python setup.py

# Test connection
uv run python imap_client.py
```

## Setup

The setup script asks for:
- IMAP server (e.g., `mail.example.com`)
- Port (default: `993` for SSL)
- Username (your email address)
- Password (stored securely in keychain)

```bash
uv run python setup.py
```

Manage credentials:
```bash
uv run python setup.py --show   # Show config (no password)
uv run python setup.py --clear  # Remove credentials
```

## Claude Configuration

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "streammail": {
      "command": "uv",
      "args": ["--directory", "/path/to/streammail", "run", "streammail"]
    }
  }
}
```

### Claude Code

```bash
claude mcp add streammail -- uv --directory /path/to/streammail run streammail
```

### Cowork

Same as Claude Desktop - add to MCP configuration.

## Usage

Once configured, Claude can use the `use_mail` tool:

```
List messages:
{action: "list", folder: "INBOX"}
{action: "list", folder: "INBOX/Projects", limit: 50}

Read a message:
{action: "read", folder: "INBOX", payload: "12345"}

Search:
{action: "search", folder: "INBOX", payload: "from:boss@company.com"}
{action: "search", folder: "INBOX", payload: "subject:urgent"}
{action: "search", folder: "INBOX", payload: "since:2024-01-01"}

Create draft reply:
{action: "draft", folder: "INBOX", payload: '{"to":"x@y.com","subject":"Re: Meeting","body":"Thanks...","in_reply_to":"<msgid>"}'}

List folders:
{action: "folders"}

Get help:
{action: "help"}
{action: "help", payload: "search"}
```

## Workflow: Reply to Email

1. **List messages** to find the one you want:
   ```
   {action: "list", folder: "INBOX"}
   ```

2. **Read the message** to see content and get Message-ID:
   ```
   {action: "read", folder: "INBOX", payload: "12345"}
   ```

3. **Create a draft reply** with Claude's help:
   ```
   {action: "draft", payload: '{"to":"sender@example.com","subject":"Re: Subject","body":"Your reply...","in_reply_to":"<original-message-id>"}'}
   ```

4. **Open Thunderbird** → Drafts → Review and send

## Folder URL Format

You can pass IMAP URLs - the folder path is extracted automatically:

```
imap://user@server/INBOX/Projects/PLoP
→ folder: "INBOX/Projects/PLoP"
```

## Security

- Credentials stored in macOS Keychain (never in files)
- Password fetched only when IMAP connection opens
- Password never appears in logs or tool output
- IMAP connection uses SSL/TLS

## License

MIT
