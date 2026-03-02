# Security Review: imap-stream-mcp

**Date:** 2026-02-25
**Updated:** 2026-03-02
**Scope:** Full codebase (7 source files, 4 test files)
**Commit:** HEAD on main

## Threat Model

MCP plugin connecting an LLM agent to email via IMAP. Primary attack surface: **malicious email containing prompt injection that drives the LLM to exfiltrate data**. Secondary: credential handling, network, filesystem.

## Findings

### 1. Data Exfiltration via File Attachment (High) — FIXED

**File:** `imap_client.py` (`_attach_files`, `_check_attachment_path`)

`_attach_files()` previously read any file the process user could access. Only validation was `is_absolute()` and `is_file()`.

**Attack chain:**
1. Malicious email contains prompt injection text
2. LLM reads email via `read` action
3. Injection instructs LLM to create draft: `draft` + `attachments: ["/Users/x/.ssh/id_rsa"]`
4. Sensitive file saved as attachment in Drafts folder

**Fix applied** (`cd14f0d`): Blocklist + warning approach:
- **Hard block**: `~/.ssh`, `~/.gnupg`, `~/.aws`, `~/.config`, `~/.kube`, `~/.docker`, `~/.env*`, `~/.npmrc`, `~/.pypirc`, `~/.netrc`, `~/.claude`, `~/.git-credentials`, all dotfiles/dotdirs in home, `/etc/shadow`, `/etc/passwd`, `/etc/ssl/private`
- **Safe (no warning)**: `/tmp/`, `~/Downloads/`, `~/Desktop/`, `~/Documents/`
- **Warning**: all other paths — warning string returned in attachment response so the LLM sees it
- Path resolution via `Path.resolve()` prevents symlink bypass (e.g. macOS `/tmp` → `/private/tmp`)

### 2. Prompt Injection Sanitization Gaps (High) — PARTIALLY FIXED

**File:** `imap_stream_mcp.py`

`_contains_injection_patterns()` checks only:
- `<untrusted_` / `</untrusted_`
- `<|` / `|>`

Missing patterns (not yet addressed):
- `</tool_use>`, `</function_call>`, `<tool_result>` (MCP/Claude tool-use XML)
- `<system>`, `</system>` (system prompt boundaries)
- `Human:`, `Assistant:` (Claude conversation markers)

**Bug fixed** (`c091aeb`): Detection was case-insensitive (`.lower()`) but sanitization used exact-case `replace()`. Fixed with `re.sub(r"...", ..., flags=re.IGNORECASE)`.

**Remaining:** Pattern expansion (finding #6) not yet implemented.

### 3. modify_draft Performs EXPUNGE (Medium) — FIXED

**File:** `imap_client.py` (`modify_draft`, `edit_draft`)

`modify_draft` and `edit_draft` use delete+expunge to replace drafts. This is correct append-before-delete pattern, but previously:
- Help text misleadingly stated "Safe: marks only, no expunge"
- No validation that the message was actually a draft

**Fix applied** (`c091aeb`): Both functions now fetch `FLAGS` and verify `\Draft` flag is present before delete+expunge. Help text corrected.

### 4. No Connection Timeout (Medium) — FIXED

**File:** `session.py`, `imap_client.py`

**Fix applied** (`c091aeb`): Added `timeout=30` to both `IMAPClient()` call sites.

### 5. Session Dict Not Thread-Safe (Medium) — FIXED

**File:** `session.py`

**Fix applied** (`c091aeb`): Added `_sessions_lock = threading.Lock()` wrapping all `_sessions` dict access (`get_session`, `invalidate_message_cache`, `update_cached_flags`).

### 6. Attachment Filename Collision (Medium) — FIXED

**File:** `imap_client.py`

**Fix applied** (`c091aeb`): After sanitizing filename, check if file exists. If collision, append counter suffix (`file_1.pdf`, `file_2.pdf`, etc.).

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

| # | Finding | Effort | Impact | Status |
|---|---------|--------|--------|--------|
| 1 | Sanitization case-insensitivity bug | Small | Fixes known bypass | Fixed `c091aeb` |
| 2 | Connection timeout | Small | Prevents hang | Fixed `c091aeb` |
| 3 | Filename collision | Small | Prevents data loss | Fixed `c091aeb` |
| 4 | Session dict thread safety | Small | Prevents race condition | Fixed `c091aeb` |
| 5 | modify_draft draft flag guard | Medium | Prevents accidental deletion | Fixed `c091aeb` |
| 6 | Injection pattern expansion | Medium | Improves protection | Open |
| 7 | File attachment path guard | Large | Prevents exfiltration | Fixed `cd14f0d` |

## Test Coverage

**Tested:** flag parsing (49 cases), search queries (22 cases), session management (50+ cases).

**Not tested:** draft creation, edit action, read action, attachment download/upload, injection detection, markdown conversion, credential retrieval. Estimated ~25% coverage.
