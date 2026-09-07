#!/usr/bin/env python3
"""The action surface, defined once.

Every front-end - the MCP tool, and the daemon and CLI that follow - dispatches
through run_action. A second copy of these eleven branches would drift from this
one silently.

Deliberately imports no front-end: pulling FastMCP in here would cost the CLI the
40 MB it exists to avoid.
"""

import json
from pathlib import Path
from typing import Literal

import html2text
from imap_client import (
    IMAPError,
    cleanup_attachments,
    create_draft,
    download_attachment,
    get_default_account,
    list_accounts,
    list_folders,
    list_messages,
    modify_draft,
    modify_flags,
    parse_folder_path,
    read_message,
    search_messages,
)
from injection_defense import sanitize_external_text, wrap_untrusted
from markdown_utils import convert_body
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from render import (
    POTENTIAL_INJECTION_WARNING,
    classify_connection_error,
    format_attachment_line,
    format_description,
    format_flags,
)


def parse_flag_payload(payload: str) -> tuple[list[int], list[str], list[str]]:
    """Parse flag payload into message IDs and flag lists.

    Args:
        payload: Format "MSG_ID:+FLAG,-FLAG" or "MSG1,MSG2:+FLAG"

    Returns:
        Tuple of (message_ids, add_flags, remove_flags)

    Raises:
        ValueError: If payload format is invalid
    """
    payload = payload.strip()

    if ":" not in payload:
        raise ValueError("Invalid payload format. Expected 'MSG_ID:+FLAG,-FLAG'")

    ids_part, flags_part = payload.split(":", 1)
    ids_part = ids_part.strip()
    flags_part = flags_part.strip()

    # Parse message IDs
    message_ids = []
    for id_str in ids_part.split(","):
        id_str = id_str.strip()
        try:
            message_ids.append(int(id_str))
        except ValueError as exc:
            raise ValueError(f"Invalid message ID: '{id_str}'") from exc

    # Parse flags
    if not flags_part:
        raise ValueError("No flags specified")

    add_flags = []
    remove_flags = []

    for flag_str in flags_part.split(","):
        flag_str = flag_str.strip()
        if not flag_str:
            continue

        if flag_str.startswith("+"):
            add_flags.append(flag_str[1:])
        elif flag_str.startswith("-"):
            remove_flags.append(flag_str[1:])
        else:
            raise ValueError(f"Flag '{flag_str}' must start with '+' or '-'")

    if not add_flags and not remove_flags:
        raise ValueError("No flags specified")

    return message_ids, add_flags, remove_flags


# Initialize MCP server - token-efficient naming
class MailAction(BaseModel):
    """Input for use_mail tool - Jesse Vincent style single-tool pattern."""

    model_config = ConfigDict(str_strip_whitespace=True)

    action: str = Field(..., description="Action: list|read|search|create|replace|flag|attachment|cleanup|folders|accounts|help")
    folder: str | None = Field(default=None, description="IMAP folder path or URL (e.g., 'INBOX' or 'imap://x@y/INBOX/Sub')")
    payload: str | None = Field(
        default=None,
        description="Action data: read=msg_id[:N|:full] | search=query | create=JSON{to,subject,body,in_reply_to?,cc?,attachments?:[paths]} | replace=JSON{id,body,subject?,to?,cc?,attachments?} | flag=MSG_ID:+FLAG,-FLAG",
    )
    limit: int | None = Field(default=20, description="Max results for list/search", ge=1, le=100)
    preview: bool | None = Field(
        default=None, description="Include body snippet (~100 chars) in list/search results. Required for list and search actions."
    )
    account: str | None = Field(
        default=None, description="Account name for multi-account setups. Use 'accounts' action to list. Default account used if omitted."
    )
    format: Literal["markdown", "plain"] | None = Field(
        default=None,
        description="Body format, required for draft. 'markdown': rendered to HTML plus a plain alternative; a newline is a line break, a blank line a paragraph. 'plain': sent exactly as written, no HTML.",
    )

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        valid = {"list", "read", "search", "create", "replace", "folders", "help", "attachment", "cleanup", "accounts", "flag"}
        v_lower = v.lower()
        if v_lower not in valid:
            raise ValueError(f"Invalid action '{v}'. Valid: {', '.join(sorted(valid))}")
        return v_lower

    @model_validator(mode="after")
    def validate_preview_required(self) -> "MailAction":
        if self.action in {"list", "search"} and self.preview is None:
            raise ValueError("preview parameter required for list/search (true=include body snippets, false=headers only)")
        return self

    @model_validator(mode="after")
    def validate_format_required(self) -> "MailAction":
        if self.action in {"create", "replace"} and self.format is None:
            raise ValueError(
                "format parameter required for draft: 'markdown' (rendered to HTML plus a plain "
                "alternative; newline = line break) or 'plain' (sent exactly as written, no HTML)"
            )
        return self


# Help documentation - loaded only when needed
HELP_TOPICS = {
    "overview": """
# IMAP Stream - Email Tool

## Actions

- **list** - List messages in a folder (`[att:N]` and snippet preview shown)
- **read** - Read a specific message
- **search** - Search messages (`[att:N]` and snippet preview shown)
- **create** - Write a new draft to the Drafts folder
- **replace** - Supersede an existing draft with new content
- **flag** - Add or remove flags/labels on messages
- **attachment** - Download email attachment to temp file
- **cleanup** - Remove downloaded attachment temp files
- **folders** - List available folders
- **accounts** - List configured email accounts
- **help** - Show this help (help topic=<topic> for details)

## Quick Examples

List inbox: {action: "list", folder: "INBOX", preview: false}
List with snippets: {action: "list", folder: "INBOX", preview: true}
Read message: {action: "read", folder: "INBOX", payload: "123"}
Search: {action: "search", folder: "INBOX", payload: "from:boss@example.com", preview: true}
Create draft: {action: "create", format: "markdown", payload: '{"to":"x@y.com","subject":"Re: Hi","body":"..."}'}
Replace draft: {action: "replace", folder: "Drafts", format: "markdown", payload: '{"id":1253,"body":"..."}'}
Flag message: {action: "flag", folder: "INBOX", payload: "123:+Flagged,-Seen"}
""",
    "list": """
# list - List Messages

Lists messages in a folder, newest first.
Output includes `[att:N]` when a message has attachments. Set `preview: true` to include `> ...` body snippet (~100 chars).

## Parameters
- folder: Folder path (required)
- preview: true/false (required) — include body snippet per message
- limit: Max messages (default 20)

## Examples
{action: "list", folder: "INBOX", preview: false}
{action: "list", folder: "INBOX", preview: true}
{action: "list", folder: "INBOX/Projects", limit: 50, preview: true}
""",
    "read": """
# read - Read Message

Fetches message content by ID.

## Parameters
- folder: Folder containing message
- payload: Message ID (from list/search results), optionally with :N (depth) or :full

## Returns
Full message with: subject, from, to, cc, date, body_text, body_html, message_id, in_reply_to

## Example
{action: "read", folder: "INBOX", payload: "12345"}
{action: "read", folder: "INBOX", payload: "12345:1"}
{action: "read", folder: "INBOX", payload: "12345:full"}
""",
    "search": """
# search - Search Messages

Search messages in a folder.
Output includes `[att:N]` when a message has attachments. Set `preview: true` to include `> ...` body snippet (~100 chars).

## Parameters
- folder: Folder to search
- payload: Search query
- preview: true/false (required) — include body snippet per message
- limit: Max results (default 20)

## Query Syntax
- Simple text: searches subject and body
- from:address - sender contains
- subject:text - subject contains
- since:YYYY-MM-DD - messages after date
- before:YYYY-MM-DD - messages before date
- flagged / is:flagged / starred - flagged messages
- unread / is:unread / unseen - unread messages
- read / is:read / seen - read messages
- answered / is:answered - replied messages
- Negate with :no suffix: flagged:no, seen:no, answered:no

## Examples
{action: "search", folder: "INBOX", payload: "project update"}
{action: "search", folder: "INBOX", payload: "from:client@example.com"}
{action: "search", folder: "INBOX", payload: "flagged"}
{action: "search", folder: "INBOX", payload: "is:unread"}
""",
    "create": """
# create - Write a New Draft

Appends a new message to the Drafts folder. Nothing is sent.

## Parameters
- format: "markdown" or "plain" - REQUIRED, top-level, not inside the payload
- payload: JSON with to, subject, body (required), in_reply_to, cc, attachments (optional)

{action: "create", format: "markdown", payload: '{"to":"x@y.com","subject":"Hi","body":"**bold** text"}'}

## Attachments
- attachments: list of absolute file paths, max 25 MB each, MIME type auto-detected

{action: "create", format: "markdown", payload: '{"to":"x@y.com","subject":"Report","body":"See attached","attachments":["/path/to/file.pdf"]}'}

## Format (required)
- "markdown": renders an HTML part plus a plain-text alternative. **bold**, *italic*, ~~strike~~,
  ==highlight==, :emoji:, `- [ ]` checkboxes, lists, headings, links, blockquotes, fenced code
  blocks and pipe tables. Code block content is sent exactly as written, in both parts.
  A newline inside a paragraph is a line break, a blank line starts a
  paragraph, and markdown block syntax still wins - a line of "=" under text is a heading.
  Fences must start at the left margin.
- "plain": the body is sent exactly as written, plain text only, no HTML part. Nothing is
  interpreted, so ASCII art and rule lines survive untouched.
- There is no default. Omitting it is an error.

## Reply Workflow
1. Use 'read' to get the message and note its message_id
2. Use 'create' with in_reply_to - quote relevant parts with >
3. Open your mail client, review, send
""",
    "replace": """
# replace - Supersede an Existing Draft

There is no way to edit a message: IMAP messages are immutable. Replace appends the new version
and expunges the draft it replaced. That expunge is the only deletion this client performs.

## Parameters
- folder: the folder holding the draft, e.g. 'Drafts'
- format: "markdown" or "plain" - REQUIRED, same meaning as for create
- payload: JSON with id and body (required), subject/to/cc/attachments (optional)

{action: "replace", folder: "Drafts", format: "markdown", payload: '{"id":1253,"body":"Updated..."}'}

## What is preserved, and what is not
- In-Reply-To, References and existing attachments are carried over
- **The draft gets a new message id.** Any id you were holding is stale afterwards; use the one
  the response reports
- Safety: the message must carry the \\Draft flag, or the replace is refused

## Keep your own source
Nothing stores the markdown you wrote. To change a draft, send the whole body again.
""",
    "folders": """
# folders - List Folders

Lists all available IMAP folders.

## Parameters
None required.

## Example
{action: "folders"}

## Returns
List of folders with their names and IMAP flags.
""",
    "flag": """
# flag - Add or Remove Flags/Labels

Modify flags on messages. No EXPUNGE - Deleted flag only marks for deletion.

## Parameters
- folder: Folder containing message(s)
- payload: "MSG_ID:+FLAG,-FLAG"

## Flags (case-insensitive)
Seen, Flagged, Answered, Deleted, Draft

## Keywords/labels
$label1-5 (Thunderbird), or any server-supported keyword

## Examples
{action: "flag", folder: "INBOX", payload: "123:+Flagged"}
{action: "flag", folder: "INBOX", payload: "123:-Seen"}
{action: "flag", folder: "INBOX", payload: "123:+Flagged,-Seen"}
{action: "flag", folder: "INBOX", payload: "123,124,125:+Deleted"}
{action: "flag", folder: "INBOX", payload: "123:+$label1"}
""",
    "attachment": """
# attachment - Download Attachment

Downloads an attachment from a message to a temp file.

## Parameters
- folder: Folder containing message
- payload: "msg_id:index" (e.g., "1253:0" for first attachment)

## Returns
File path, content type, size. Use Read tool for images, pdf/docx skills for documents.

## Example
{action: "attachment", folder: "Drafts", payload: "1253:0"}
""",
    "cleanup": """
# cleanup - Remove Downloaded Attachments

Deletes all downloaded attachments from temp directory.

## Parameters
None required.

## Example
{action: "cleanup"}
""",
    "accounts": """
# accounts - List Configured Accounts

Shows all configured email accounts and which is the default.

## Parameters
None required.

## Example
{action: "accounts"}

## Multi-Account Usage
When multiple accounts are configured, specify which account to use:
{action: "list", folder: "INBOX", account: "work"}

If no account is specified, the default account is used.
""",
}


def run_action(params: MailAction) -> str:
    """Dispatch one validated action and return its rendered text.

    Synchronous: no branch awaits anything, verified before this was extracted.
    The IMAP work blocks the calling thread, as it always has.

    Args:
        params: A validated MailAction. Callers that did not come through
            FastMCP must run MailAction.model_validate themselves.

    Returns:
        Markdown text for the caller to display.
    """
    try:
        action = params.action

        # Help - self-documenting
        if action == "help":
            topic = (params.payload or "overview").lower()
            if topic in HELP_TOPICS:
                return HELP_TOPICS[topic]
            return f"Unknown topic '{topic}'. Available: {', '.join(HELP_TOPICS.keys())}"

        # Folders
        if action == "folders":
            folders = list_folders(account=params.account)
            suspicious_patterns_found = False
            lines = ["# Available Folders", ""]
            for f in folders:
                safe_name, name_flag = sanitize_external_text(f["name"])
                raw_flags = " ".join(f["flags"]) if f["flags"] else ""
                safe_flags, flags_flag = sanitize_external_text(raw_flags)
                if name_flag or flags_flag:
                    suspicious_patterns_found = True
                lines.append(f"- **{safe_name}** {safe_flags}")
            body = "\n".join(lines)
            if suspicious_patterns_found:
                return POTENTIAL_INJECTION_WARNING + "\n\n" + body
            return body

        # Accounts
        if action == "accounts":
            accounts = list_accounts()
            default = get_default_account()

            if not accounts:
                plugin_dir = Path(__file__).parent.resolve()
                return f"""# No Accounts Configured

**Option 1:** Run setup (stores in OS keychain):
```bash
uv run --directory {plugin_dir} python setup.py
```

**Option 2:** Set environment variables in MCP config:
```json
"env": {{
  "IMAP_SLIM_SERVER": "imap.example.com",
  "IMAP_SLIM_USERNAME": "you@example.com",
  "IMAP_SLIM_PASSWORD": "app-password"
}}
```"""

            lines = ["# Configured Accounts", ""]
            suspicious_patterns_found = False
            for acc in accounts:
                safe_acc, acc_flag = sanitize_external_text(acc)
                if acc_flag:
                    suspicious_patterns_found = True
                marker = " (default)" if acc == default else ""
                lines.append(f"- **{safe_acc}**{marker}")

            body = "\n".join(lines)
            if suspicious_patterns_found:
                return POTENTIAL_INJECTION_WARNING + "\n\n" + body
            return body

        # Parse folder from URL if needed
        folder = params.folder
        if folder and "://" in folder:
            folder = parse_folder_path(folder)

        # List
        if action == "list":
            if not folder:
                return "Error: folder required. Example: {action:'list', folder:'INBOX'}"

            messages = list_messages(folder, limit=params.limit, account=params.account, preview=params.preview or False)

            safe_folder, folder_flag = sanitize_external_text(folder)
            suspicious_patterns_found = folder_flag

            if not messages:
                body = f"No messages in '{safe_folder}'"
                if suspicious_patterns_found:
                    return POTENTIAL_INJECTION_WARNING + "\n\n" + body
                return body

            lines = [f"# Messages in {safe_folder}", f"Showing {len(messages)} messages", ""]
            for msg in messages:
                flag_str = format_flags(msg["flags"])
                attachment_count = msg.get("attachment_count", 0)
                att_str = f"[att:{attachment_count}]" if attachment_count > 0 else ""
                suffix_parts = [part for part in [flag_str, att_str] if part]
                safe_subject, subj_flag = sanitize_external_text(msg["subject"])
                safe_from, from_flag = sanitize_external_text(msg["from"])
                if subj_flag or from_flag:
                    suspicious_patterns_found = True
                lines.append(f"**[{msg['id']}]** {safe_subject}")
                suffix = f" {' '.join(suffix_parts)}" if suffix_parts else ""
                lines.append(f"  From: {safe_from} | {msg['date']}{suffix}")
                snippet = msg.get("snippet", "")
                if snippet:
                    safe_snippet, snip_flag = sanitize_external_text(snippet)
                    if snip_flag:
                        suspicious_patterns_found = True
                    lines.append(f"  > {safe_snippet}")
                lines.append("")

            body = "\n".join(lines)
            if suspicious_patterns_found:
                return POTENTIAL_INJECTION_WARNING + "\n\n" + body
            return body

        # Read
        if action == "read":
            if not folder:
                return "Error: folder required."
            if not params.payload:
                return "Error: payload (message ID) required. Example: {action:'read', folder:'INBOX', payload:'123'}"

            if ":" in params.payload:
                id_str, modifier = params.payload.split(":", 1)
                if modifier == "full":
                    full = True
                    depth = 0
                elif modifier.isdigit():
                    full = False
                    depth = int(modifier)
                else:
                    return (
                        f"Error: unknown modifier '{modifier}'. Use '{id_str}', '{id_str}:1' (include previous message), or '{id_str}:full'"
                    )
            else:
                id_str = params.payload
                full = False
                depth = 0

            try:
                msg_id = int(id_str)
            except ValueError:
                return f"Error: payload must be numeric message ID, got '{id_str}'"

            msg = read_message(folder, msg_id, account=params.account, full=full, depth=depth)

            suspicious_patterns_found = False

            def _sanitize(value: str) -> str:
                nonlocal suspicious_patterns_found
                safe, flag = sanitize_external_text(value)
                if flag:
                    suspicious_patterns_found = True
                return safe

            from_safe = ", ".join(_sanitize(addr) for addr in msg["from"])
            to_safe = ", ".join(_sanitize(addr) for addr in msg["to"])
            cc_safe = ", ".join(_sanitize(addr) for addr in msg["cc"]) if msg["cc"] else ""
            subject_safe = _sanitize(msg["subject"])
            date_safe = _sanitize(msg["date"])
            message_id_safe = _sanitize(msg["message_id"])
            in_reply_to_safe = _sanitize(msg["in_reply_to"]) if msg["in_reply_to"] else ""

            header_lines = [
                f"From: {from_safe}",
                f"To: {to_safe}",
            ]
            if cc_safe:
                header_lines.append(f"Cc: {cc_safe}")
            header_lines.extend(
                [
                    f"Subject: {subject_safe}",
                    f"Date: {date_safe}",
                    f"Message-ID: {message_id_safe}",
                ]
            )
            if in_reply_to_safe:
                header_lines.append(f"In-Reply-To: {in_reply_to_safe}")

            # Get body content
            body_content = ""
            if msg["body_text"]:
                body_content = msg["body_text"]
            elif msg["body_html"]:
                h = html2text.HTML2Text()
                h.ignore_links = False
                h.body_width = 0  # No wrapping
                body_content = h.handle(msg["body_html"])

            body_safe = _sanitize(body_content)

            wrapped = wrap_untrusted("\n".join(header_lines) + "\n\n" + body_safe)

            truncation_notice = ""
            if msg.get("quoted_truncated"):
                count = msg.get("quoted_message_count", 0)
                chars = msg.get("quoted_chars_truncated", 0)
                chars_k = chars // 1000
                next_depth = depth + 1
                if depth >= 1:
                    truncation_notice = (
                        f"\n**Older reply chain omitted** (~{chars_k}k chars, estimated {count} messages). "
                        f'Use ":{next_depth}" for next layer or ":full" for complete chain.\n'
                    )
                else:
                    truncation_notice = (
                        f"\n**Quoted reply chain omitted** (~{chars_k}k chars, estimated {count} messages). "
                        f'Use ":1" for previous message with inline replies, or ":full" for complete chain.\n'
                    )

            # Attachments info (safe metadata, outside wrapper)
            attachments_info = ""
            attachments = msg.get("attachments", [])
            inline_images = msg.get("inline_images", [])
            att_lines = []

            if attachments:
                att_lines.append(f"**Attachments:** ({len(attachments)})")
                for att in attachments:
                    size_kb = att["size"] / 1024
                    index = att.get("index", "?")
                    fname_safe = _sanitize(att["filename"])
                    ctype_safe = _sanitize(att["content_type"])
                    att_lines.append(f"  [{index}] {fname_safe} ({ctype_safe}, {size_kb:.1f} KB)")

            if inline_images:
                inline_parts = [f"[{img.get('index', '?')}] {_sanitize(img['filename'])}" for img in inline_images]
                if att_lines:
                    att_lines.append("")
                att_lines.append(f"**Inline images:** ({len(inline_images)}) " + ", ".join(inline_parts))

            if att_lines:
                attachments_info = "\n" + "\n".join(att_lines) + "\n"

            security_notice = POTENTIAL_INJECTION_WARNING + "\n\n" if suspicious_patterns_found else ""

            return security_notice + wrapped + truncation_notice + attachments_info

        # Search
        if action == "search":
            if not folder:
                return "Error: folder required."
            if not params.payload:
                return "Error: payload (search query) required. Use 'help search' for syntax."

            messages = search_messages(folder, params.payload, limit=params.limit, account=params.account, preview=params.preview or False)

            safe_folder, folder_flag = sanitize_external_text(folder)
            suspicious_patterns_found = folder_flag

            if not messages:
                body = f"No messages matching '{params.payload}' in '{safe_folder}'"
                if suspicious_patterns_found:
                    return POTENTIAL_INJECTION_WARNING + "\n\n" + body
                return body

            lines = [f"# Search Results: {params.payload}", f"Found {len(messages)} in {safe_folder}", ""]
            for msg in messages:
                flag_str = format_flags(msg.get("flags", []))
                attachment_count = msg.get("attachment_count", 0)
                att_str = f"[att:{attachment_count}]" if attachment_count > 0 else ""
                suffix_parts = [part for part in [flag_str, att_str] if part]
                safe_subject, subj_flag = sanitize_external_text(msg["subject"])
                safe_from, from_flag = sanitize_external_text(msg["from"])
                if subj_flag or from_flag:
                    suspicious_patterns_found = True
                lines.append(f"**[{msg['id']}]** {safe_subject}")
                suffix = f" {' '.join(suffix_parts)}" if suffix_parts else ""
                lines.append(f"  From: {safe_from} | {msg['date']}{suffix}")
                snippet = msg.get("snippet", "")
                if snippet:
                    safe_snippet, snip_flag = sanitize_external_text(snippet)
                    if snip_flag:
                        suspicious_patterns_found = True
                    lines.append(f"  > {safe_snippet}")
                lines.append("")

            body = "\n".join(lines)
            if suspicious_patterns_found:
                return POTENTIAL_INJECTION_WARNING + "\n\n" + body
            return body

        # Edit existing draft with surgical replacements
        # create = APPEND. replace = APPEND then expunge the draft it replaced.
        # There is no edit: IMAP messages are immutable, so what used to be
        # called editing was always a replace.
        if action in {"create", "replace"}:
            if not params.payload:
                return f"Error: payload required. Use 'help {action}' for details."

            try:
                draft_data = json.loads(params.payload)
            except json.JSONDecodeError as e:
                return f"Error: Invalid JSON in payload: {e}"

            # Only a key of a decoded object: payload='"format"' decodes to a
            # string, where there is no key to forbid.
            if isinstance(draft_data, dict) and "format" in draft_data:
                return (
                    "Error: 'format' no longer goes inside the payload. Pass it as a top-level "
                    'parameter instead: {action:"create"|"replace", format:"markdown"|"plain", payload:\'{...}\'}'
                )

            has_id = isinstance(draft_data, dict) and "id" in draft_data
            if action == "replace" and not has_id:
                return "Error: 'id' required for replace - the draft being replaced. Use 'create' for a new draft."
            if action == "create" and has_id:
                return "Error: 'id' is not valid for create. Use 'replace' to supersede an existing draft."

            if action == "replace":
                if not folder:
                    return "Error: folder required for replace (e.g., 'Drafts')"
                if "body" not in draft_data:
                    return "Error: 'body' required for replace"

                body = draft_data["body"]
                format_type = params.format
                html_body, plain_body = convert_body(body, format_type)

                # Parse and validate attachments
                att_paths = draft_data.get("attachments")
                if att_paths is not None and not isinstance(att_paths, list):
                    return "Error: 'attachments' must be a list of file paths"
                if att_paths and not all(isinstance(p, str) for p in att_paths):
                    return "Error: each attachment must be a file path string"

                result = modify_draft(
                    folder=folder,
                    message_id=int(draft_data["id"]),
                    body=plain_body,
                    subject=draft_data.get("subject"),
                    to=draft_data.get("to"),
                    cc=draft_data.get("cc"),
                    html=html_body,
                    attachments=att_paths,
                    account=params.account,
                )

                reply_info = " (reply threading preserved)" if result["preserved_reply_to"] else ""
                leftover = (
                    ""
                    if result.get("superseded_expunged", True)
                    else "\n\n**Note:** the server does not support UIDPLUS, so the superseded draft was "
                    "left marked \\Deleted rather than expunged. A bare expunge would have removed every "
                    "other \\Deleted message in the folder too."
                )
                att_info = format_attachment_line(result.get("attachments", []))
                return f"""# Draft Replaced{reply_info}

**To:** {result["to"]}
**Subject:** {result["subject"]}{att_info}
**Format:** {format_description(format_type)}
**Saved to:** {result["folder"]}{leftover}

Open Thunderbird → Drafts to review and send."""

            # Create new draft
            required = ["to", "subject", "body"]
            missing = [f for f in required if f not in draft_data]
            if missing:
                return f"Error: Missing required fields: {', '.join(missing)}"

            body = draft_data["body"]
            format_type = params.format
            html_body, plain_body = convert_body(body, format_type)

            # Parse and validate attachments
            att_paths = draft_data.get("attachments")
            if att_paths is not None and not isinstance(att_paths, list):
                return "Error: 'attachments' must be a list of file paths"
            if att_paths and not all(isinstance(p, str) for p in att_paths):
                return "Error: each attachment must be a file path string"

            result = create_draft(
                folder=folder or "INBOX",
                to=draft_data["to"],
                subject=draft_data["subject"],
                body=plain_body,
                in_reply_to=draft_data.get("in_reply_to"),
                cc=draft_data.get("cc"),
                html=html_body,
                attachments=att_paths,
                account=params.account,
            )

            att_info = format_attachment_line(result.get("attachments", []))
            return f"""# Draft Created

**To:** {result["to"]}
**Subject:** {result["subject"]}{att_info}
**Format:** {format_description(format_type)}
**Saved to:** {result["folder"]}

Open Thunderbird → Drafts to review and send."""

        # Attachment
        if action == "attachment":
            if not folder:
                return "Error: folder required."
            if not params.payload:
                return "Error: payload required. Format: 'msg_id:index' (e.g., '1253:0')"

            try:
                parts = params.payload.split(":")
                if len(parts) != 2:
                    raise ValueError("Expected format 'msg_id:index'")
                msg_id = int(parts[0])
                att_index = int(parts[1])
            except ValueError:
                return f"Error: Invalid payload '{params.payload}'. Use 'msg_id:index' format (e.g., '1253:0')"

            result = download_attachment(folder, msg_id, att_index, account=params.account)

            safe_filename, fname_flag = sanitize_external_text(result["filename"])
            safe_ctype, ctype_flag = sanitize_external_text(result["content_type"])
            suspicious_patterns_found = fname_flag or ctype_flag

            body = f"""# Attachment Downloaded

**File:** {safe_filename}
**Type:** {safe_ctype}
**Size:** {result["size"] / 1024:.1f} KB
**Saved to:** {result["saved_to"]}

Use Read tool for images, pdf/docx skills for documents."""
            if suspicious_patterns_found:
                return POTENTIAL_INJECTION_WARNING + "\n\n" + body
            return body

        # Flag
        if action == "flag":
            if not folder:
                return "Error: folder required. Example: {action:'flag', folder:'INBOX', payload:'123:+Flagged'}"
            if not params.payload:
                return "Error: payload required. Use 'help flag' for details."

            try:
                msg_ids, add_flags, remove_flags = parse_flag_payload(params.payload)
            except ValueError as e:
                return f"Error: {e}"

            result = modify_flags(folder, msg_ids, add_flags, remove_flags, account=params.account)

            # Build response
            lines = ["# Flag Operation"]

            if result["modified"] > 0:
                lines.append(f"\nModified {result['modified']} message(s)")

            if result["flags_added"]:
                lines.append(f"Added: {', '.join(result['flags_added'])}")
            if result["flags_removed"]:
                lines.append(f"Removed: {', '.join(result['flags_removed'])}")

            if result["failed"]:
                lines.append(f"\n**Failed:** ({len(result['failed'])})")
                for fail in result["failed"]:
                    if "flag" in fail:
                        lines.append(f"  - Message {fail['id']}, flag '{fail['flag']}': {fail['error']}")
                    else:
                        lines.append(f"  - Message {fail['id']}: {fail['error']}")

            return "\n".join(lines)

        # Cleanup
        if action == "cleanup":
            result = cleanup_attachments()
            freed_kb = result["freed_bytes"] / 1024
            return f"Cleaned up {result['deleted']} file(s), freed {freed_kb:.1f} KB"

        return f"Unknown action '{action}'. Use 'help' for available actions."

    except ValueError as e:
        return f"Error: {e}"
    except IMAPError as e:
        classified = classify_connection_error(e)
        if classified:
            return classified
        error_msg = str(e)
        # Provide friendly setup guide for unconfigured credentials
        if "not configured" in error_msg.lower():
            plugin_dir = Path(__file__).parent.resolve()
            return f"""# IMAP Stream - Setup Required

Your IMAP credentials are not configured yet.

## Quick Setup

```bash
uv run --directory {plugin_dir} python setup.py
```

This stores your IMAP credentials securely in your system keychain.

## What You'll Need
- IMAP server address (e.g., `imap.gmail.com`, `mail.example.com`)
- Your email address
- App-specific password (recommended for Gmail/iCloud)

## Alternative: Environment Variables
```bash
export IMAP_SLIM_SERVER="imap.example.com"
export IMAP_SLIM_USERNAME="you@example.com"
export IMAP_SLIM_PASSWORD="app-password"
```

After setup, try: `{{action: "folders"}}` to verify connection.
"""
        return f"Error: {e}"
    except Exception as e:
        classified = classify_connection_error(e)
        if classified:
            return classified
        return f"Error: {type(e).__name__}: {e}"
