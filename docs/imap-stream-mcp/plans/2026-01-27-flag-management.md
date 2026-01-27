# Flag Management for IMAP Stream MCP

## Summary

Add `flag` action to manage IMAP flags and keywords/labels on messages.

## Scope

Single `flag` action supporting:
- All standard IMAP flags (Seen, Flagged, Answered, Deleted, Draft)
- All server-supported keywords/labels ($label1-5, custom keywords)
- Add (+) and remove (-) operations
- Single and batch message operations

## API

### Action: flag

```python
# Single message, single flag
{action: "flag", folder: "INBOX", payload: "123:+Flagged"}
{action: "flag", folder: "INBOX", payload: "123:-Seen"}

# Single message, multiple flags
{action: "flag", folder: "INBOX", payload: "123:+Flagged,-Seen"}

# Batch messages
{action: "flag", folder: "INBOX", payload: "123,124,125:+Flagged"}

# Keywords/labels
{action: "flag", folder: "INBOX", payload: "123:+$label1"}
{action: "flag", folder: "INBOX", payload: "123:+important"}
```

### Input format

- Standard flags: case-insensitive, backslash optional
  - `+Flagged`, `+flagged`, `+\Flagged` all accepted
- Keywords: as-is (`$label1`, `important`)
- Prefix: `+` to add, `-` to remove

### Output format

Flags displayed without backslashes:

```python
# list/read message output:
"flags": ["Seen", "Flagged", "$label1", "important"]
```

### Response

```python
{
  "modified": 2,
  "flags_added": ["Flagged"],
  "flags_removed": ["Seen"],
  "failed": [
    {"id": 999, "error": "Message not found"},
    {"id": 123, "flag": "Recent", "error": "Read-only flag"}
  ]
}
```

## Error handling

No pre-validation. Try all operations, report results:
- Message not found: report in `failed` list, continue batch
- Unsupported keyword: let IMAP server reject, report in `failed`
- Read-only flag (\Recent): let IMAP server reject, report in `failed`

Partial success is OK for batch operations.

## Security

- All flag operations allowed (add/remove)
- No EXPUNGE operation (deletion remains just a marking)
- `\Deleted` flag only marks for deletion, does not destroy data
- README update: "Read-only for mailboxes" → "No destructive operations"

## Help text

```
flag - Add or remove flags/labels from messages

Usage:
  payload: "MSG_ID:+FLAG,-FLAG"
  payload: "MSG1,MSG2:+FLAG"

Flags (case-insensitive):
  Seen, Flagged, Answered, Deleted, Draft

Keywords/labels:
  $label1-5 (Thunderbird), or any server-supported keyword

Examples:
  "123:+Flagged"           Mark important
  "123:-Seen"              Mark unread
  "123:+Flagged,-Seen"     Multiple flags
  "123,124,125:+Deleted"   Batch mark for deletion
  "123:+$label1"           Add Thunderbird tag
```

## Implementation Context

### Project structure

```
imap-stream-mcp/
├── imap_client.py       # IMAP operations (list, read, search, draft, NEW: modify_flags)
├── imap_stream_mcp.py   # MCP server, action dispatcher, help texts
├── markdown_utils.py    # Markdown → HTML conversion
└── pyproject.toml
```

Note: No existing tests directory. Unit tests for pure functions (parsing, normalization) can be added.

### Key patterns in imap_client.py

```python
# Connection context manager - use this pattern:
@contextmanager
def imap_connection(account: str | None = None):
    """Yields connected IMAPClient instance."""

# Existing functions return dicts, use same pattern
def list_messages(folder: str, limit: int = 20) -> list[dict]:
def read_message(folder: str, message_id: int) -> dict:

# Flag conversion helper needed:
def normalize_flag_output(flag: str) -> str:
    """Strip backslash: '\\Seen' -> 'Seen'"""

def normalize_flag_input(flag: str) -> str:
    """Add backslash to standard flags: 'seen' -> '\\Seen'"""

STANDARD_FLAGS = {'seen', 'flagged', 'answered', 'deleted', 'draft'}
```

### Key patterns in imap_stream_mcp.py

```python
# Action dispatcher in handle_mail() function
if action == "list":
    result = list_messages(...)
elif action == "flag":  # Add here
    result = handle_flag_action(folder, payload)

# Help texts in HELP_TEXTS dict
HELP_TEXTS = {
    "flag": "...",  # Add here
}
```

### IMAPClient library reference

```python
# Add flags
client.add_flags([msg_id], [b'\\Flagged', b'\\Seen'])

# Remove flags
client.remove_flags([msg_id], [b'\\Seen'])

# Flags must be bytes with backslash for standard flags
# Keywords can be bytes without backslash: b'$label1', b'important'
```

### Running tests

```bash
cd imap-stream-mcp

# Unit tests (after creating tests/)
uv run pytest tests/ -v

# Manual testing with real IMAP (requires configured account)
uv run python -c "from imap_client import test_connection; test_connection()"

# Test via Claude CLI (plugin installed locally)
claude -p "list my inbox"
claude -p "flag message 123 as important"
```

## Implementation Tasks

### 1. imap_client.py

Add `modify_flags` function:

```python
def modify_flags(folder: str, message_ids: list[int],
                 add_flags: list[str], remove_flags: list[str],
                 account: str | None = None) -> dict:
    """Add or remove flags from messages.

    Args:
        folder: IMAP folder path
        message_ids: List of message IDs to modify
        add_flags: Flags to add (normalized input: 'Flagged', '$label1')
        remove_flags: Flags to remove
        account: Optional account name

    Returns:
        Dict with modified count, flags_added, flags_removed, failed list
    """
```

Update `list_messages` and `read_message` to normalize flag output (strip backslash).

### 2. imap_stream_mcp.py

Add payload parser:

```python
def parse_flag_payload(payload: str) -> tuple[list[int], list[str], list[str]]:
    """Parse '123,124:+Flagged,-Seen' -> ([123,124], ['Flagged'], ['Seen'])"""
```

Add `flag` action to dispatcher.
Add help text to HELP_TEXTS dict.

### 3. Tests

Create tests/test_flag_parsing.py for pure functions:
- test_normalize_flag_input
- test_normalize_flag_output
- test_parse_flag_payload

No mocking of IMAP - manual testing with real server.

## Acceptance criteria

1. Can add/remove standard flags (Seen, Flagged, Deleted, etc.)
2. Can add/remove keywords ($label1, custom)
3. Batch operations work
4. Partial failures reported correctly
5. Flags displayed without backslashes in list/read
6. Help text available via `{action: "help", payload: "flag"}`

## Validation

Manual testing with Thunderbird:
1. Flag message in Claude → verify in Thunderbird
2. Flag message in Thunderbird → verify in Claude
3. Batch flag multiple messages
4. Add/remove Thunderbird tags ($label1-5)
