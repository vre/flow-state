# Security Review: imap-stream-mcp

**Date:** 2026-02-25
**Scope:** Full codebase (7 source files, 4 test files)
**Commit:** HEAD on main

## Threat Model

MCP plugin connecting an LLM agent to email via IMAP. Primary attack surface: **malicious email containing prompt injection that drives the LLM to exfiltrate data**. Secondary: credential handling, network, filesystem.

## Findings

### 1. Data Exfiltration via File Attachment (High)

**File:** `imap_client.py:743-790` (`_attach_files`)

`_attach_files()` reads any file the process user can access. Only validation: `is_absolute()` and `is_file()`.

**Attack chain:**
1. Malicious email contains prompt injection text
2. LLM reads email via `read` action
3. Injection instructs LLM to create draft: `draft` + `attachments: ["/Users/x/.ssh/id_rsa"]`
4. Sensitive file saved as attachment in Drafts folder

The untrusted content wrapper makes this harder but does not prevent it.

**Recommendation:** Whitelist-based path restriction (e.g. only `/tmp/streammail/`), or explicit user confirmation before file reads. Best option: MCP permission prompt before reading files for attachment.

### 2. Prompt Injection Sanitization Gaps (High)

**File:** `imap_stream_mcp.py:88-110`

`_contains_injection_patterns()` checks only:
- `<untrusted_` / `</untrusted_`
- `<|` / `|>`

Missing patterns:
- `</tool_use>`, `</function_call>`, `<tool_result>` (MCP/Claude tool-use XML)
- `<system>`, `</system>` (system prompt boundaries)
- `Human:`, `Assistant:` (Claude conversation markers)

**Bug:** Detection is case-insensitive (`.lower()`) but sanitization uses exact-case `replace()`:

```python
# Detection finds "<UNTRUSTED_" via .lower() check
# But sanitization does not replace it:
result = text.replace("</untrusted_", "&lt;/untrusted_")  # misses "</UNTRUSTED_"
```

**Recommendation:** Use `re.sub` with `re.IGNORECASE` for sanitization. Add detection patterns for tool-use XML and conversation markers.

### 3. modify_draft Performs EXPUNGE (Medium)

**File:** `imap_client.py:1037-1038`

```python
client.delete_messages([message_id])
client.expunge()
```

The tool help text states "Safe: marks only, no expunge" (`imap_stream_mcp.py:471`), but `edit` and `draft` (modify) actions permanently delete the old draft. This is a correct append-before-delete pattern, but:
- Documentation is misleading
- No validation that the target folder is actually a Drafts folder — operating on INBOX would permanently delete messages

**Recommendation:** Validate folder has `\Draft` flag or matching name before allowing delete+expunge. Fix help text.

### 4. No Connection Timeout (Medium)

**File:** `session.py:91`

```python
client = IMAPClient(server, port=int(port), ssl=True)  # no timeout
```

Network problems cause the MCP tool to block indefinitely. `IMAPClient` supports a `timeout` parameter.

**Recommendation:** `IMAPClient(server, port=int(port), ssl=True, timeout=30)`

### 5. Session Dict Not Thread-Safe (Medium)

**File:** `session.py:17, 38-42`

```python
_sessions: dict[str, "AccountSession"] = {}

def get_session(account):
    if account not in _sessions:
        _sessions[account] = AccountSession(account)  # race condition
    return _sessions[account]
```

MCP server is async (FastMCP). `AccountSession` has an internal `RLock` but the module-level `_sessions` dict is unprotected.

**Recommendation:** Add a module-level lock around `_sessions` dict access.

### 6. Attachment Filename Collision (Medium)

**File:** `imap_client.py:632-633`

```python
safe_filename = re.sub(r"[^\w\-_\.]", "_", filename)
file_path = temp_dir / safe_filename  # silent overwrite
```

Two attachments with the same name overwrite each other without warning.

**Recommendation:** Use `f"{message_id}_{attachment_index}_{safe_filename}"`.

### 7. Credential Env Var Fallback (Low)

**File:** `imap_client.py:157-160`

`IMAP_STREAM_PASSWORD` in environment variables is visible via `/proc/<pid>/environ` on Linux. Acceptable for Docker/CI use. Document the risk.

### 8. URL Autolink Regex (Low)

**File:** `markdown_utils.py:34`

Negative lookbehind only handles `href="` (double quotes). Single-quoted `href='...'` bypassed. Only affects outgoing email formatting — not security-critical.

## Positive Observations

- **SSL/TLS enforced**: `ssl=True`, port 993, no plaintext IMAP option
- **Credentials never returned to LLM**: fetched at connection time only, stored in OS keychain
- **Pydantic validation** on action parameters with explicit whitelist
- **No subprocess calls**, no `eval`/`exec`
- **IMAP queries via imapclient library**: no raw IMAP command construction, library handles escaping
- **Attachment download sanitizes filenames**: `re.sub(r"[^\w\-_\.]", "_", filename)`
- **Read operations use `readonly=True`**
- **No EXPUNGE in flag operations**: flag action only marks, does not expunge
- **Append-before-delete pattern** in draft modification prevents data loss on failure

## Priority Matrix

| # | Finding | Effort | Impact |
|---|---------|--------|--------|
| 1 | Sanitization case-insensitivity bug | Small | Fixes known bypass |
| 2 | Connection timeout | Small | Prevents hang |
| 3 | Filename collision | Small | Prevents data loss |
| 4 | Session dict thread safety | Small | Prevents race condition |
| 5 | modify_draft folder validation | Medium | Prevents accidental deletion |
| 6 | Injection pattern expansion | Medium | Improves protection |
| 7 | File attachment restriction | Large | Prevents exfiltration |

## Test Coverage

**Tested:** flag parsing (49 cases), search queries (22 cases), session management (50+ cases).

**Not tested:** draft creation, edit action, read action, attachment download/upload, injection detection, markdown conversion, credential retrieval. Estimated ~25% coverage.
