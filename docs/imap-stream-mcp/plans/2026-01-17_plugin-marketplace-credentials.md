# Plugin Marketplace Credentials Handling

## Research Summary

### Python keyring Library - Cross-Platform

The `keyring` library handles credential storage across all platforms:

| Platform | Backend |
|----------|---------|
| macOS | Keychain |
| Windows | Credential Manager |
| Linux | GNOME Keyring / KWallet / Secret Service |

**Note:** Linux may require `dbus-python` as system package.

### Claude Code Plugin Credential Options

1. **No built-in user_config prompts** - Unlike Desktop Extensions (.mcpb)
   - Plugins don't prompt for secrets during install
   - Users must configure credentials externally

2. **Environment variables** - Passed via `process.env`
   - User sets in shell profile
   - Useful for CI/CD, Docker, automation

### Known Bug: env Block in .mcp.json

[Issue #1254](https://github.com/anthropics/claude-code/issues/1254): When `.mcp.json` has an `env` section, it **replaces** `process.env` instead of merging.

**Decision:** Remove env block from `.mcp.json`

## Decision: Keychain Primary

### Credential Flow

```
get_credentials()
    │
    ├─► PRIMARY: keyring.get_password()
    │   └─► Cross-platform system credential store
    │   └─► Configured via: uv run python setup.py
    │
    └─► FALLBACK: os.environ.get("STREAMMAIL_IMAP_*")
        └─► For automation, CI/CD, Docker
        │
        └─► If neither: raise IMAPError with instructions
```

### User Setup

**Primary: System Keychain** (all platforms)
```bash
uv run python setup.py
```

**Fallback: Environment Variables** (automation/Docker)
```bash
export STREAMMAIL_IMAP_SERVER="mail.example.com"
export STREAMMAIL_IMAP_PORT="993"
export STREAMMAIL_IMAP_USERNAME="user@example.com"
export STREAMMAIL_IMAP_PASSWORD="app-password"
```

## Implementation

### Files to Change

1. **`imap_client.py`** - Swap priority: keyring first, env vars second
2. **`.mcp.json`** - Remove env block
3. **`README.md`** - Document credential setup for all platforms

### Code Change: get_credentials()

```python
def get_credentials():
    # PRIMARY: System keychain (cross-platform)
    server = keyring.get_password(SERVICE_NAME, "imap_server")
    if server:
        port = keyring.get_password(SERVICE_NAME, "imap_port")
        username = keyring.get_password(SERVICE_NAME, "imap_username")
        password = keyring.get_password(SERVICE_NAME, "imap_password")
    else:
        # FALLBACK: Environment variables (automation/Docker)
        server = os.environ.get("STREAMMAIL_IMAP_SERVER")
        port = os.environ.get("STREAMMAIL_IMAP_PORT")
        username = os.environ.get("STREAMMAIL_IMAP_USERNAME")
        password = os.environ.get("STREAMMAIL_IMAP_PASSWORD")

    if not all([server, username, password]):
        raise IMAPError("IMAP not configured. Run 'uv run python setup.py'")

    return server, port or "993", username, password
```

### Verification

1. Without credentials → helpful error message
2. With keychain (`setup.py`) → works (primary)
3. With env vars only → works (fallback)
4. Run tests: `uv run pytest tests/`

## Sources

- [Python keyring](https://pypi.org/project/keyring/) - Cross-platform credential storage
- [Env Bug #1254](https://github.com/anthropics/claude-code/issues/1254) - Why no env block
- [Plugin Docs](https://code.claude.com/docs/en/plugins)
