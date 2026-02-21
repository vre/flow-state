# DONE: Multi-Account Support

Support for multiple email accounts.

## Keychain Storage

Current (single account):
```
Service: "imap-stream"
Keys: imap_server, imap_port, imap_username, imap_password
```

New (multiple accounts):
```
Service: "imap-stream"
Keys:
  accounts                    → JSON list: ["work", "personal"]
  default_account             → "work"
  work:imap_server           → "mail.company.com"
  work:imap_port             → "993"
  work:imap_username         → "me@company.com"
  work:imap_password         → "xxx"
  personal:imap_server       → "imap.gmail.com"
  ...
```

## Files to Modify

### 1. `imap_client.py`

```python
def list_accounts() -> list[str]:
    """Return list of configured account names."""

def get_default_account() -> str | None:
    """Return default account name."""

def get_credentials(account: str | None = None) -> tuple[str, str, str, str]:
    """Get credentials for account. None = default account."""

def imap_connection(account: str | None = None):
    """Context manager with account parameter."""
```

### 2. `imap_stream_mcp.py`

```python
class MailAction(BaseModel):
    account: Optional[str] = Field(
        default=None,
        description="Account name (uses default if not specified)"
    )
```

New action:
```python
if action == "accounts":
    accounts = list_accounts()
    default = get_default_account()
    # Return list of accounts
```

### 3. `setup.py`

```bash
python setup.py                    # Interactive (add/edit)
python setup.py --list             # Show accounts
python setup.py --add <name>       # Add account
python setup.py --remove <name>    # Remove account
python setup.py --default <name>   # Set default account
```

## Backward Compatibility

- If `accounts` not found in keychain → migration: current config = "default" account
- If `account` parameter missing → use default account
- Environment variables still work (no account prefix)

## Simplicity for Single Account Usage

- `account` parameter exists in schema but **ignored** if only 1 account
- `help` action shows accounts **only if** multiple configured
- `accounts` action returns list **only if** multiple accounts (otherwise shows setup hint)
- Tool description is static, but responses are dynamic

## Verification

1. `uv run pytest tests/`
2. `{action: "accounts"}` → shows accounts
3. `{action: "list", folder: "INBOX"}` → uses default account
4. `{action: "list", folder: "INBOX", account: "work"}` → uses named account
