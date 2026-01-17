# IMAP Stream MCP

Lightweight IMAP email client for Claude Desktop/Code/Cowork.

Inspired by [Jesse Vincent's MCP design philosophy](https://blog.fsck.com/2025/10/19/mcps-are-not-like-other-apis/):
- **~500 tokens** vs typical 15,000+ token MCP servers
- Single `use_mail` tool with action dispatcher
- Self-documenting via `help` action
- Credentials stored securely in OS keychain (cross-platform)

## Features

- **list** - List messages in any IMAP folder
- **read** - Read message content
- **search** - Search by sender, subject, date, or text
- **draft** - Create draft replies (saved to IMAP Drafts folder)
- **folders** - List available folders
- **help** - Built-in documentation

## Installation

```bash
cd imap-stream-mcp

# Install dependencies with uv
uv sync

# Configure IMAP credentials (stored in system keychain)
uv run python setup.py

# Test connection
uv run python imap_client.py
```

## Credentials Setup

### Primary: System Keychain (Recommended)

The setup script stores credentials in your system's secure credential store:

| Platform | Backend |
|----------|---------|
| macOS | Keychain |
| Windows | Credential Manager |
| Linux | GNOME Keyring / KWallet / Secret Service |

```bash
uv run python setup.py
```

The script asks for:
- IMAP server (e.g., `mail.example.com`)
- Port (default: `993` for SSL)
- Username (your email address)
- Password (stored securely in keychain)

Manage credentials:
```bash
uv run python setup.py --show   # Show config (no password)
uv run python setup.py --clear  # Remove credentials
```

### Fallback: Environment Variables (Automation/Docker)

For CI/CD, Docker, or automation, set environment variables instead:

```bash
export IMAP_STREAM_SERVER="mail.example.com"
export IMAP_STREAM_PORT="993"
export IMAP_STREAM_USERNAME="user@example.com"
export IMAP_STREAM_PASSWORD="app-password"
```

Environment variables are used only when keychain credentials are not configured.

## Claude Configuration

### Claude Desktop

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

### Claude Code

```bash
claude mcp add imap-stream -- uv --directory /path/to/imap-stream-mcp run imap-stream
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

- Credentials stored in system keychain (never in files)
- Password fetched only when IMAP connection opens
- Password never appears in logs or tool output
- IMAP connection uses SSL/TLS

## License

MIT
