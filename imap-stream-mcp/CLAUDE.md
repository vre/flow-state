# IMAP Stream MCP - AI Assistant Context

Context for AI assistants working on this codebase.

## Design Philosophy

Based on [Jesse Vincent's MCP patterns](https://blog.fsck.com/2025/10/19/mcps-are-not-like-other-apis/):

1. **Token efficiency** - Single tool with action dispatcher (~500 tokens vs 15,000+)
2. **Self-documenting** - `help` action provides all documentation
3. **Postel's Law** - Liberal in inputs, strict in outputs

## Architecture

```
imap_stream_mcp.py   # FastMCP server, use_mail tool, action routing
imap_client.py       # IMAP operations, keychain access
markdown_utils.py    # Markdown→HTML for drafts
setup.py             # Account configuration CLI
```

## Key Patterns

### Single Tool Pattern

All operations through one `use_mail(action, folder?, payload?, limit?)` tool:
- Reduces token overhead
- Simplifies Claude's tool selection
- Self-documenting via `help` action

### Multi-Account Storage

```
Keychain service: "imap-stream"
Keys:
  accounts              → JSON: ["work", "personal"]
  default_account       → "work"
  {account}:imap_server → "mail.example.com"
  {account}:imap_port   → "993"
  {account}:imap_username
  {account}:imap_password
```

### Credential Priority

1. Keychain (primary)
2. Environment variables IMAP_STREAM_* (fallback for Docker/CI)

## Code Conventions

- **Type hints** - Use throughout
- **Docstrings** - Google style
- **Error handling** - Raise `IMAPError` with helpful messages
- **Tests** - pytest, mock keyring and IMAP client

## Testing

```bash
uv run pytest tests/ -v
```

Tests use mocked keyring and IMAP client. See `tests/conftest.py` for fixtures.

## Adding New Actions

1. Add to valid actions in `MailAction.validate_action()`
2. Add handler in `use_mail()` function
3. Add help topic in `HELP_TOPICS`
4. Add tests

## Files

| File | Purpose |
|------|---------|
| `imap_stream_mcp.py` | MCP server, action dispatcher |
| `imap_client.py` | IMAP operations, credentials |
| `markdown_utils.py` | Draft formatting |
| `setup.py` | Account management CLI |
| `debug_imap.py` | Connection debugging |
