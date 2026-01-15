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
from typing import Optional

import html2text

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, field_validator, ConfigDict

from imap_client import (
    IMAPError,
    list_folders,
    list_messages,
    read_message,
    search_messages,
    create_draft,
    parse_folder_path,
)

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
        valid = {'list', 'read', 'search', 'draft', 'folders', 'help'}
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
# draft - Create Draft Reply

Creates a draft message in the IMAP Drafts folder.
You can then review/edit/send it in Thunderbird.

## Parameters
- folder: Current folder (for context)
- payload: JSON object with:
  - to (required): Recipient email
  - subject (required): Message subject
  - body (required): Plain text body
  - in_reply_to (optional): Message-ID being replied to
  - cc (optional): CC addresses, comma-separated

## Example
{action: "draft", folder: "INBOX", payload: '{"to":"boss@example.com","subject":"Re: Q4 Report","body":"Thanks for the update...","in_reply_to":"<abc123@mail.example.com>"}'}

## Workflow
1. Use 'read' to get the original message (note the message_id)
2. Use 'draft' with in_reply_to set to that message_id
3. Open Thunderbird → Drafts → review and send
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
                flags = " ".join(msg["flags"])
                lines.append(f"**[{msg['id']}]** {msg['subject']}")
                lines.append(f"  From: {msg['from']} | {msg['date']} {flags}")
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

        # Draft
        if action == "draft":
            if not params.payload:
                return "Error: payload required. JSON with to, subject, body. Use 'help draft' for details."

            try:
                draft_data = json.loads(params.payload)
            except json.JSONDecodeError as e:
                return f"Error: Invalid JSON in payload: {e}"

            required = ['to', 'subject', 'body']
            missing = [f for f in required if f not in draft_data]
            if missing:
                return f"Error: Missing required fields: {', '.join(missing)}"

            result = create_draft(
                folder=folder or "INBOX",
                to=draft_data['to'],
                subject=draft_data['subject'],
                body=draft_data['body'],
                in_reply_to=draft_data.get('in_reply_to'),
                cc=draft_data.get('cc')
            )

            return f"""# Draft Created

**To:** {result['to']}
**Subject:** {result['subject']}
**Saved to:** {result['folder']}

Open Thunderbird → Drafts to review and send."""

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
