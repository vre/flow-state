# Email/IMAP MCP Server Research Report

**Date:** 2026-01-17
**Search Terms:** "email mcp server", "imap mcp", "gmail mcp", "mail mcp server"

---

## Executive Summary

This research identifies **20+ email-related MCP servers** on GitHub, revealing common patterns in naming conventions, tool design, parameter structures, and credential handling. Most servers use multiple specialized tools (5-20+), environment variables for credentials, and lack explicit token efficiency considerations.

---

## 1. Server Names and Naming Patterns

### Naming Conventions Observed

| Pattern | Examples | Frequency |
|---------|----------|-----------|
| `{service}-mcp` | `gmail-mcp`, `imap-mcp`, `icloud-mail-mcp` | Most common |
| `mcp-{service}` | `mcp-gmail`, `mcp-mail-server` | Common |
| `{service}-mcp-server` | `gmail-mcp-server`, `imap-mcp-server` | Common |
| `mcp-server-{service}` | `mcp-server-smtp` | Occasional |
| `{descriptive}-mcp` | `email-reader-mcp` | Occasional |

### Complete Server List

**IMAP-focused:**
- [non-dirty/imap-mcp](https://github.com/non-dirty/imap-mcp) - Interactive email processing
- [nikolausm/imap-mcp-server](https://github.com/nikolausm/imap-mcp-server) - Powerful with encrypted storage
- [dominik1001/imap-mcp](https://github.com/dominik1001/imap-mcp) - TypeScript, draft-focused
- [yunfeizhu/mcp-mail-server](https://github.com/yunfeizhu/mcp-mail-server) - Lightweight IMAP+SMTP
- [gabigabogabu/email-mcp-server](https://github.com/gabigabogabu/email-mcp-server) - IMAP/SMTP connectivity
- [djaboxx/imap-mcp-server](https://github.com/djaboxx/imap-mcp-server) - Basic implementation

**Gmail-focused:**
- [GongRzhe/Gmail-MCP-Server](https://github.com/GongRzhe/Gmail-MCP-Server) - 18 tools, auto-auth
- [theposch/gmail-mcp](https://github.com/theposch/gmail-mcp) - Comprehensive Python
- [shinzo-labs/gmail-mcp](https://github.com/shinzo-labs/gmail-mcp) - Smithery-integrated
- [jeremyjordan/mcp-gmail](https://github.com/jeremyjordan/mcp-gmail) - Python SDK powered
- [baryhuang/mcp-headless-gmail](https://github.com/baryhuang/mcp-headless-gmail) - No local credentials
- [automatearmy/email-reader-mcp](https://github.com/automatearmy/email-reader-mcp) - IMAP-based Gmail reader
- [david-strejc/gmail-mcp-server](https://github.com/david-strejc/gmail-mcp-server) - IMAP/SMTP via Gmail

**Other Providers:**
- [minagishl/icloud-mail-mcp](https://github.com/minagishl/icloud-mail-mcp) - iCloud Mail (15 tools)
- [elyxlz/microsoft-mcp](https://github.com/elyxlz/microsoft-mcp) - Outlook via Graph API
- [taylorwilsdon/google_workspace_mcp](https://github.com/taylorwilsdon/google_workspace_mcp) - Full Workspace suite
- [samihalawa/mcp-server-smtp](https://github.com/samihalawa/mcp-server-smtp) - SMTP only with templates
- [omd01/aws-ses-mcp](https://github.com/omd01/aws-ses-mcp) - AWS SES integration

---

## 2. Tool Design Patterns

### Single Tool vs Multiple Tools

| Approach | Count | Examples |
|----------|-------|----------|
| **Multiple Tools** | ~95% | Most servers (5-20+ tools) |
| **Single Tool** | ~5% | `dominik1001/imap-mcp` (just `create-draft`) |

**Key Finding:** Nearly all servers use **multiple specialized tools**. No server uses a single-tool/action-pattern design.

### Tool Count by Server

| Server | Tool Count | Categories |
|--------|------------|------------|
| nikolausm/imap-mcp-server | 15+ | Account, email ops, folders |
| GongRzhe/Gmail-MCP-Server | 18 | Email, labels, filters, batch |
| minagishl/icloud-mail-mcp | 15 | Email, mailbox, system |
| mcp-mail-server | 17 | Connection, search, mailbox |
| jeremyjordan/mcp-gmail | 9 | Email ops, labels |
| gabigabogabu/email-mcp-server | 3 | send, search, list_folders |
| dominik1001/imap-mcp | 1 | create-draft only |

### Common Tool Naming Patterns

**Verb-noun format (most common):**
```
send_email, search_emails, get_message, list_folders
mark_as_read, delete_email, create_label
```

**Service-prefixed (workspace servers):**
```
search_gmail_messages, get_gmail_message_content
send_gmail_message, draft_gmail_message
```

**IMAP-prefixed (for multi-service):**
```
imap_search_emails, imap_get_email, imap_send_email
imap_add_account, imap_connect, imap_disconnect
```

---

## 3. Parameters for Core Operations

### List/Get Messages

**nikolausm/imap-mcp-server - `imap_get_latest_emails`:**
```
accountId: string (required)
folder: string (default: "INBOX")
count: number (default: 10)
```

**yunfeizhu/mcp-mail-server - `get_messages`:**
```
uids: number[] (required)
markSeen: boolean (optional)
```

**automatearmy/email-reader-mcp - `get-messages`:**
```
limit: number (default: 10)
includeFullContent: boolean (default: false)
dateFrom: string (ISO date)
dateTo: string (ISO date)
unreadOnly: boolean (default: false)
from: string (sender filter)
subject: string (partial match)
```

**jeremyjordan/mcp-gmail - `get_emails`:**
```
message_ids: string[] (required)
```

### Search Messages

**nikolausm/imap-mcp-server - `imap_search_emails`:**
```
accountId: string (required)
folder: string (default: "INBOX")
from: string (optional)
to: string (optional)
subject: string (optional)
body: string (optional)
since: date (optional)
before: date (optional)
seen: boolean (optional)
flagged: boolean (optional)
limit: number (default: 50)
```

**yunfeizhu/mcp-mail-server - `search_messages`:**
```
criteria: array (IMAP search criteria)
```

**Specialized search tools in mcp-mail-server:**
```
search_by_sender: { sender: string }
search_by_subject: { subject: string }
search_by_body: { text: string }
search_since_date: { date: string }
search_larger_than: { size: number }
```

**GongRzhe/Gmail-MCP-Server - `search_emails`:**
```
query: string (Gmail operators: from:, to:, subject:, etc.)
maxResults: number
```

### Read Single Message

**nikolausm/imap-mcp-server - `imap_get_email`:**
```
accountId: string (required)
folder: string (required)
uid: number (required)
maxContentLength: number (default: 10000)
includeAttachmentText: boolean (default: true)
maxAttachmentTextChars: number (default: 100000)
```

**minagishl/icloud-mail-mcp - `get_messages`:**
```
mailbox: string
limit: number
unreadOnly: boolean
```

### Send Email

**nikolausm/imap-mcp-server - `imap_send_email`:**
```
accountId: string (required)
to: string/array (required)
subject: string (required)
text: string (optional)
html: string (optional)
cc: string/array (optional)
bcc: string/array (optional)
replyTo: string (optional)
attachments: array (optional)
  - filename: string
  - content/path: string
  - contentType: string
```

**GongRzhe/Gmail-MCP-Server - `send_email`:**
```
to: string (required)
subject: string (required)
body: string (required)
cc: string (optional)
bcc: string (optional)
mimeType: string (optional)
attachments: array (optional)
```

**yunfeizhu/mcp-mail-server - `send_email`:**
```
to: string (required)
subject: string (required)
text: string (optional)
html: string (optional)
cc: string (optional)
bcc: string (optional)
```

**samihalawa/mcp-server-smtp - `send-email`:**
```
to: array<{email, name?}> (required)
subject: string (required)
body: string (required)
from: object (optional)
cc: array (optional)
bcc: array (optional)
templateId: string (optional)
templateData: object (optional)
smtpConfigId: string (optional)
```

---

## 4. Credential Handling Approaches

### Environment Variables (Most Common)

**Standard pattern:**
```bash
IMAP_HOST=imap.gmail.com
IMAP_PORT=993
IMAP_USERNAME=user@gmail.com
IMAP_PASSWORD=app-password
IMAP_USE_SSL=true
SMTP_HOST=smtp.gmail.com
SMTP_PORT=465
```

**Used by:**
- dominik1001/imap-mcp
- yunfeizhu/mcp-mail-server
- gabigabogabu/email-mcp-server
- automatearmy/email-reader-mcp
- minagishl/icloud-mail-mcp

### OAuth 2.0 (Gmail API Servers)

**Pattern:**
```bash
MCP_GMAIL_CREDENTIALS_PATH=credentials.json
MCP_GMAIL_TOKEN_PATH=token.json
```

**OAuth flow:**
1. Download credentials from Google Cloud Console
2. Run authentication command
3. Token stored locally (auto-refresh)

**Used by:**
- GongRzhe/Gmail-MCP-Server
- jeremyjordan/mcp-gmail
- theposch/gmail-mcp
- taylorwilsdon/google_workspace_mcp

### Encrypted Local Storage

**nikolausm/imap-mcp-server:**
- AES-256-CBC encryption for credentials
- Key stored in `~/.imap-mcp/.key`
- Accounts in `~/.imap-mcp/accounts.json`
- Tools: `imap_add_account`, `imap_list_accounts`, `imap_remove_account`

### MCP Configuration File

**Claude Desktop config pattern:**
```json
{
  "mcpServers": {
    "imap": {
      "command": "npx",
      "args": ["imap-mcp"],
      "env": {
        "IMAP_HOST": "imap.gmail.com",
        "IMAP_PORT": "993",
        "IMAP_USERNAME": "user@gmail.com",
        "IMAP_PASSWORD": "app-password"
      }
    }
  }
}
```

### Security Recommendations (Common Across Servers)

- Use app-specific passwords (not main account password)
- Never commit credentials to version control
- Store `.env` files securely
- Enable TLS/SSL for all connections
- Consider limiting folder access

---

## 5. Token Efficiency Considerations

### Explicit Mentions

**Very rare.** Only one email server mentioned efficiency:

**yunfeizhu/mcp-mail-server:**
> "A lightweight Model Context Protocol (MCP) server"

### Relevant Non-Email Examples

**GitHub MCP Lightweight (`wipiano/github-mcp-lw`):**
> "Minimal response sizes by returning only essential fields... 90%+ smaller than full GitHub API responses."

**mcp-text-editor (`tumf/mcp-text-editor`):**
> "Line-oriented text file editor optimized for LLM tools with efficient partial file access to minimize token usage."

### Efficiency Patterns Observed

| Pattern | Implementation | Servers |
|---------|----------------|---------|
| **Content truncation** | `maxContentLength: 10000` | nikolausm/imap-mcp-server |
| **Preview mode** | `includeFullContent: false` (500-char preview) | automatearmy/email-reader-mcp |
| **Batch operations** | Process 50 emails at once | GongRzhe/Gmail-MCP-Server |
| **Connection pooling** | Reuse connections | nikolausm/imap-mcp-server |
| **Service caching** | 30-minute cache | google_workspace_mcp |

### Token Efficiency Gaps

Most servers:
- Return full message bodies by default
- Include all headers and metadata
- No pagination for large result sets
- No field selection options
- No summarization of long emails

---

## 6. Key Learnings and Recommendations

### For Naming

1. Use `{service}-mcp` or `mcp-{service}` format
2. Add `-server` suffix if ambiguous
3. Be specific: `imap-mcp` not just `email-mcp`

### For Tool Design

1. **Multiple specialized tools preferred** over single action-based tool
2. Group tools by operation type:
   - Connection/account management
   - Read operations (list, get, search)
   - Write operations (send, reply, draft)
   - Organization (labels, folders, flags)
3. Use consistent verb-noun naming: `send_email`, `search_messages`

### For Parameters

1. **Required:** identifier (accountId/uid), target (folder/mailbox)
2. **Common defaults:**
   - folder: "INBOX"
   - limit: 10-50
   - includeBody: false (efficiency)
3. **Truncation options** for body content
4. **Date filters** use ISO format strings

### For Credentials

1. Environment variables for IMAP/SMTP servers
2. OAuth 2.0 for API-based servers (Gmail, Microsoft)
3. Consider encrypted storage for multi-account scenarios
4. Always recommend app-specific passwords

### For Token Efficiency (Underserved Area)

1. **Preview mode by default** - short body excerpts
2. **Field selection** - let users choose what to return
3. **Pagination** - limit results, support offset
4. **Content limits** - truncate at N characters
5. **Summarization** - optional AI summary of long emails

---

## 7. Competitive Analysis Summary

| Feature | Most Common | Best Practice |
|---------|-------------|---------------|
| Tool count | 5-18 tools | Moderate (8-12) |
| Tool naming | `verb_noun` | Consistent patterns |
| Search | Separate tools per criteria | Combined with operators |
| Credentials | Env vars | OAuth for Gmail, env for IMAP |
| Token efficiency | Rarely addressed | Truncation + preview mode |
| Multi-account | Usually single | Support multiple |
| Attachments | Full support | Size limits needed |

---

## 8. GitHub Repository Links

### Primary Research Sources

- https://github.com/non-dirty/imap-mcp
- https://github.com/nikolausm/imap-mcp-server
- https://github.com/dominik1001/imap-mcp
- https://github.com/yunfeizhu/mcp-mail-server
- https://github.com/gabigabogabu/email-mcp-server
- https://github.com/GongRzhe/Gmail-MCP-Server
- https://github.com/theposch/gmail-mcp
- https://github.com/jeremyjordan/mcp-gmail
- https://github.com/automatearmy/email-reader-mcp
- https://github.com/minagishl/icloud-mail-mcp
- https://github.com/elyxlz/microsoft-mcp
- https://github.com/taylorwilsdon/google_workspace_mcp
- https://github.com/samihalawa/mcp-server-smtp
- https://github.com/omd01/aws-ses-mcp

### Curated Lists

- https://github.com/modelcontextprotocol/servers
- https://github.com/wong2/awesome-mcp-servers
- https://github.com/punkpeye/awesome-mcp-servers

---

## 9. Appendix: Example Tool Definitions

### nikolausm/imap-mcp-server (Most Comprehensive)

```
Account Tools:
- imap_add_account(name, host, port, user, password, tls)
- imap_list_accounts()
- imap_remove_account(accountId)
- imap_connect(accountId | accountName)
- imap_disconnect(accountId)

Email Tools:
- imap_search_emails(accountId, folder, from, to, subject, body, since, before, seen, flagged, limit)
- imap_get_email(accountId, folder, uid, maxContentLength, includeAttachmentText, maxAttachmentTextChars)
- imap_get_latest_emails(accountId, folder, count)
- imap_mark_as_read(accountId, folder, uid)
- imap_mark_as_unread(accountId, folder, uid)
- imap_delete_email(accountId, folder, uid)
- imap_send_email(accountId, to, subject, text, html, cc, bcc, replyTo, attachments)
- imap_reply_to_email(accountId, folder, uid, text, html, replyAll, attachments)
- imap_forward_email(accountId, folder, uid, to, text, includeAttachments)

Folder Tools:
- imap_list_folders(accountId)
- imap_folder_status(accountId, folder)
- imap_get_unread_count(accountId, folders?)
```

### jeremyjordan/mcp-gmail (Moderate Size)

```
Email Tools:
- compose_email() - Create draft
- send_email() - Send immediately
- search_emails() - Search with filters
- query_emails() - Gmail query syntax
- get_emails() - Get by IDs

Organization Tools:
- list_available_labels()
- mark_message_read()
- add_label_to_message()
- remove_label_from_message()
```

### dominik1001/imap-mcp (Minimal)

```
Single Tool:
- create-draft(to, subject, body, from?)
```

---

*Research conducted using web searches and GitHub repository analysis.*
