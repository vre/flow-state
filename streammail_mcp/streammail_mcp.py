#!/usr/bin/env python3
"""
Streammail MCP Server - Lightweight IMAP client for Claude.

Inspired by Jesse Vincent's MCP design philosophy:
- Single tool with action dispatcher (~900 tokens vs typical 15,000+)
- Self-documenting via 'help' action
- Credentials from OS keychain (never exposed)

Usage with Claude Desktop/Code:
    Add to your MCP config:
    {
        "mcpServers": {
            "streammail": {
                "command": "python",
                "args": ["/path/to/streammail_mcp.py"]
            }
        }
    }
"""

import json
import re
from typing import Optional

import html2text
import markdown
from pymdownx import emoji

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, field_validator, ConfigDict

from imap_client import (
    IMAPError,
    list_folders,
    list_messages,
    read_message,
    download_attachment,
    cleanup_attachments,
    search_messages,
    create_draft,
    modify_draft,
    parse_folder_path,
)

def preprocess_markdown(text: str) -> str:
    """Fix common markdown issues before conversion.

    Ensures blank lines before block elements (lists, code blocks, blockquotes, headings).
    """
    lines = text.split('\n')
    result = []
    prev_was_blank = True  # Start as if there was a blank line

    for line in lines:
        stripped = line.strip()
        is_blank = stripped == ''

        # Check if line starts a block element
        is_block_start = (
            stripped.startswith('- ') or
            stripped.startswith('* ') or
            stripped.startswith('+ ') or
            re.match(r'^\d+\. ', stripped) or  # ordered list
            stripped.startswith('> ') or  # blockquote
            stripped.startswith('```') or  # code block
            stripped.startswith('#')  # heading
        )

        # Add blank line before block element if previous line wasn't blank
        if is_block_start and not prev_was_blank:
            result.append('')

        result.append(line)
        prev_was_blank = is_blank

    return '\n'.join(result)


def markdown_to_plain(text: str) -> str:
    """Convert markdown to pre-markdown plain text (Gmail style).

    - **bold** -> *bold*
    - [text](url) -> text <url>
    - ~~strike~~ -> text (markers removed)
    - ==highlight== -> text (markers removed)
    """
    # **bold** or __bold__ -> *bold*
    text = re.sub(r'\*\*(.+?)\*\*', r'*\1*', text)
    text = re.sub(r'__(.+?)__', r'*\1*', text)
    # [text](url) -> text <url>
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1 <\2>', text)
    # ~~strike~~ -> plain
    text = re.sub(r'~~(.+?)~~', r'\1', text)
    # ==highlight== -> plain
    text = re.sub(r'==(.+?)==', r'\1', text)
    return text


# Initialize MCP server - token-efficient naming
mcp = FastMCP("streammail_mcp")


class MailAction(BaseModel):
    """Input for use_mail tool - Jesse Vincent style single-tool pattern."""

    model_config = ConfigDict(str_strip_whitespace=True)

    action: str = Field(
        ...,
        description="Action: list|read|search|draft|folders|help"
    )
    folder: Optional[str] = Field(
        default=None,
        description="IMAP folder path or URL (e.g., 'INBOX' or 'imap://x@y/INBOX/Sub')"
    )
    payload: Optional[str] = Field(
        default=None,
        description="Action data: read=msg_id | search=query | draft=JSON{to,subject,body,in_reply_to?,cc?}"
    )
    limit: Optional[int] = Field(
        default=20,
        description="Max results for list/search",
        ge=1,
        le=100
    )

    @field_validator('action')
    @classmethod
    def validate_action(cls, v: str) -> str:
        valid = {'list', 'read', 'search', 'draft', 'folders', 'help', 'attachment', 'cleanup'}
        v_lower = v.lower()
        if v_lower not in valid:
            raise ValueError(f"Invalid action '{v}'. Valid: {', '.join(sorted(valid))}")
        return v_lower


# Help documentation - loaded only when needed
HELP_TOPICS = {
    "overview": """
# Streammail - IMAP Email Tool

## Actions

- **list** - List messages in a folder
- **read** - Read a specific message
- **search** - Search messages
- **draft** - Create draft reply (saved to Drafts folder)
- **folders** - List available folders
- **help** - Show this help (help topic=<topic> for details)

## Quick Examples

List inbox: {action: "list", folder: "INBOX"}
Read message: {action: "read", folder: "INBOX", payload: "123"}
Search: {action: "search", folder: "INBOX", payload: "from:boss@example.com"}
Create draft: {action: "draft", folder: "INBOX", payload: '{"to":"x@y.com","subject":"Re: Hi","body":"..."}'}
""",

    "list": """
# list - List Messages

Lists messages in a folder, newest first.

## Parameters
- folder: Folder path (required)
- limit: Max messages (default 20)

## Examples
{action: "list", folder: "INBOX"}
{action: "list", folder: "INBOX/Projects", limit: 50}
{action: "list", folder: "imap://user@server/INBOX/Sub"}  # URL format extracts folder
""",

    "read": """
# read - Read Message

Fetches full message content by ID.

## Parameters
- folder: Folder containing message
- payload: Message ID (from list/search results)

## Returns
Full message with: subject, from, to, cc, date, body_text, body_html, message_id, in_reply_to

## Example
{action: "read", folder: "INBOX", payload: "12345"}
""",

    "search": """
# search - Search Messages

Search messages in a folder.

## Parameters
- folder: Folder to search
- payload: Search query
- limit: Max results (default 20)

## Query Syntax
- Simple text: searches subject and body
- from:address - sender contains
- subject:text - subject contains
- since:YYYY-MM-DD - messages after date
- before:YYYY-MM-DD - messages before date

## Examples
{action: "search", folder: "INBOX", payload: "project update"}
{action: "search", folder: "INBOX", payload: "from:client@example.com"}
{action: "search", folder: "INBOX", payload: "since:2024-01-01", limit: 50}
""",

    "draft": """
# draft - Create or Modify Draft

Creates a new draft or modifies an existing one.

## Create New Draft
- payload: JSON with to, subject, body (required), in_reply_to, cc, format (optional)

{action: "draft", payload: '{"to":"x@y.com","subject":"Hi","body":"**bold** text"}'}

## Format
- "markdown" (default): HTML + plain text. Supports: **bold**, *italic*, ~~strike~~, ==highlight==, :emoji:, `- [ ]` checkboxes, lists, headings, links, blockquotes
- "plain": plain text only

## Modify Existing Draft
- payload: JSON with id (required), body (required), subject/to/cc/format (optional)
- Preserves In-Reply-To and References for reply threading

{action: "draft", folder: "Drafts", payload: '{"id":1253,"body":"Updated..."}'}

## Workflow
1. Use 'read' to get message (note message_id for replies)
2. Use 'draft' with in_reply_to - quote relevant parts with >
3. Open email client → Drafts → review and send
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
"""
}


@mcp.tool(
    name="use_mail",
    annotations={
        "title": "Email Operations",
        "readOnlyHint": False,  # draft action modifies
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True
    }
)
async def use_mail(params: MailAction) -> str:
    """IMAP email operations. Actions: list|read|search|draft|folders|help.

    Examples:
      {action:"list", folder:"INBOX"} - list messages
      {action:"read", folder:"INBOX", payload:"123"} - read message
      {action:"search", folder:"INBOX", payload:"from:x@y.com"}
      {action:"draft", payload:'{"to":"x","subject":"y","body":"z"}'}
      {action:"help", payload:"search"} - help on topic
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
            folders = list_folders()
            lines = ["# Available Folders", ""]
            for f in folders:
                flags = " ".join(f["flags"]) if f["flags"] else ""
                lines.append(f"- **{f['name']}** {flags}")
            return "\n".join(lines)

        # Parse folder from URL if needed
        folder = params.folder
        if folder and "://" in folder:
            folder = parse_folder_path(folder)

        # List
        if action == "list":
            if not folder:
                return "Error: folder required. Example: {action:'list', folder:'INBOX'}"

            messages = list_messages(folder, limit=params.limit)

            if not messages:
                return f"No messages in '{folder}'"

            lines = [f"# Messages in {folder}", f"Showing {len(messages)} messages", ""]
            for msg in messages:
                # Separate standard flags from custom tags
                std_flags = []
                tags = []
                for f in msg["flags"]:
                    if f.startswith('\\'):
                        # Standard flag: \Seen -> seen
                        std_flags.append(f[1:].lower())
                    else:
                        tags.append(f)

                # Format: [flags] #tags
                flag_str = ""
                if std_flags:
                    flag_str = f"[{','.join(std_flags)}]"
                if tags:
                    flag_str += " " + " ".join(f"#{t}" for t in tags)
                flag_str = flag_str.strip()

                lines.append(f"**[{msg['id']}]** {msg['subject']}")
                lines.append(f"  From: {msg['from']} | {msg['date']} {flag_str}")
                lines.append("")

            return "\n".join(lines)

        # Read
        if action == "read":
            if not folder:
                return "Error: folder required."
            if not params.payload:
                return "Error: payload (message ID) required. Example: {action:'read', folder:'INBOX', payload:'123'}"

            try:
                msg_id = int(params.payload)
            except ValueError:
                return f"Error: payload must be numeric message ID, got '{params.payload}'"

            msg = read_message(folder, msg_id)

            lines = [
                f"# {msg['subject']}",
                "",
                f"**From:** {', '.join(msg['from'])}",
                f"**To:** {', '.join(msg['to'])}",
            ]

            if msg['cc']:
                lines.append(f"**Cc:** {', '.join(msg['cc'])}")

            lines.extend([
                f"**Date:** {msg['date']}",
                f"**Message-ID:** {msg['message_id']}",
            ])

            if msg['in_reply_to']:
                lines.append(f"**In-Reply-To:** {msg['in_reply_to']}")

            # Attachments
            if msg.get('attachments'):
                lines.append("")
                lines.append(f"**Attachments:** ({len(msg['attachments'])})")
                for att in msg['attachments']:
                    size_kb = att['size'] / 1024
                    lines.append(f"  - {att['filename']} ({att['content_type']}, {size_kb:.1f} KB)")

            lines.extend(["", "---", ""])

            # Prefer plain text, fall back to HTML converted to text
            if msg['body_text']:
                lines.append(msg['body_text'])
            elif msg['body_html']:
                h = html2text.HTML2Text()
                h.ignore_links = False
                h.body_width = 0  # No wrapping
                lines.append(h.handle(msg['body_html']))

            return "\n".join(lines)

        # Search
        if action == "search":
            if not folder:
                return "Error: folder required."
            if not params.payload:
                return "Error: payload (search query) required. Use 'help search' for syntax."

            messages = search_messages(folder, params.payload, limit=params.limit)

            if not messages:
                return f"No messages matching '{params.payload}' in '{folder}'"

            lines = [f"# Search Results: {params.payload}", f"Found {len(messages)} in {folder}", ""]
            for msg in messages:
                lines.append(f"**[{msg['id']}]** {msg['subject']}")
                lines.append(f"  From: {msg['from']} | {msg['date']}")
                lines.append("")

            return "\n".join(lines)

        # Draft (create or modify)
        if action == "draft":
            if not params.payload:
                return "Error: payload required. Use 'help draft' for details."

            try:
                draft_data = json.loads(params.payload)
            except json.JSONDecodeError as e:
                return f"Error: Invalid JSON in payload: {e}"

            # Modify existing draft if 'id' provided
            if 'id' in draft_data:
                if not folder:
                    return "Error: folder required for modify (e.g., 'Drafts')"
                if 'body' not in draft_data:
                    return "Error: 'body' required for modify"

                body = draft_data['body']
                format_type = draft_data.get('format', 'markdown')

                if format_type == 'markdown':
                    preprocessed = preprocess_markdown(body)
                    html_body = markdown.markdown(
                        preprocessed,
                        extensions=[
                            'pymdownx.tilde',
                            'pymdownx.tasklist',
                            'pymdownx.mark',
                            'pymdownx.betterem',
                                                        'pymdownx.emoji',
                        ],
                        extension_configs={
                            'pymdownx.emoji': {'emoji_generator': emoji.to_alt}
                        }
                    )
                    plain_body = markdown_to_plain(body)
                else:
                    html_body = None
                    plain_body = body

                result = modify_draft(
                    folder=folder,
                    message_id=int(draft_data['id']),
                    body=plain_body,
                    subject=draft_data.get('subject'),
                    to=draft_data.get('to'),
                    cc=draft_data.get('cc'),
                    html=html_body
                )

                reply_info = " (reply threading preserved)" if result['preserved_reply_to'] else ""
                return f"""# Draft Modified{reply_info}

**To:** {result['to']}
**Subject:** {result['subject']}
**Saved to:** {result['folder']}

Open Thunderbird → Drafts to review and send."""

            # Create new draft
            required = ['to', 'subject', 'body']
            missing = [f for f in required if f not in draft_data]
            if missing:
                return f"Error: Missing required fields: {', '.join(missing)}"

            body = draft_data['body']
            format_type = draft_data.get('format', 'markdown')

            if format_type == 'markdown':
                preprocessed = preprocess_markdown(body)
                html_body = markdown.markdown(
                    preprocessed,
                    extensions=[
                        'pymdownx.tilde',
                        'pymdownx.tasklist',
                        'pymdownx.mark',
                        'pymdownx.betterem',
                                                'pymdownx.emoji',
                    ],
                    extension_configs={
                        'pymdownx.emoji': {'emoji_generator': emoji.to_alt}
                    }
                )
                plain_body = markdown_to_plain(body)
            else:
                html_body = None
                plain_body = body

            result = create_draft(
                folder=folder or "INBOX",
                to=draft_data['to'],
                subject=draft_data['subject'],
                body=plain_body,
                in_reply_to=draft_data.get('in_reply_to'),
                cc=draft_data.get('cc'),
                html=html_body
            )

            return f"""# Draft Created

**To:** {result['to']}
**Subject:** {result['subject']}
**Saved to:** {result['folder']}

Open Thunderbird → Drafts to review and send."""

        # Attachment
        if action == "attachment":
            if not folder:
                return "Error: folder required."
            if not params.payload:
                return "Error: payload required. Format: 'msg_id:index' (e.g., '1253:0')"

            try:
                parts = params.payload.split(':')
                if len(parts) != 2:
                    raise ValueError("Expected format 'msg_id:index'")
                msg_id = int(parts[0])
                att_index = int(parts[1])
            except ValueError as e:
                return f"Error: Invalid payload '{params.payload}'. Use 'msg_id:index' format (e.g., '1253:0')"

            result = download_attachment(folder, msg_id, att_index)

            return f"""# Attachment Downloaded

**File:** {result['filename']}
**Type:** {result['content_type']}
**Size:** {result['size'] / 1024:.1f} KB
**Saved to:** {result['saved_to']}

Use Read tool for images, pdf/docx skills for documents."""

        # Cleanup
        if action == "cleanup":
            result = cleanup_attachments()
            freed_kb = result['freed_bytes'] / 1024
            return f"Cleaned up {result['deleted']} file(s), freed {freed_kb:.1f} KB"

        return f"Unknown action '{action}'. Use 'help' for available actions."

    except IMAPError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error: {type(e).__name__}: {e}"


def main():
    """Entry point for streammail MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
