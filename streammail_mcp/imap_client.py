#!/usr/bin/env python3
"""
IMAP Client for Streammail MCP.

Handles all IMAP operations with lazy connection management.
Credentials are fetched from macOS Keychain at connection time.
"""

import email
import email.header
import email.utils
import json
import keyring
import os
import re
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from imapclient import IMAPClient

SERVICE_NAME = "streammail"


class IMAPError(Exception):
    """IMAP operation error with helpful message."""
    pass


def get_credentials() -> tuple[str, str, str, str]:
    """Fetch IMAP credentials from keychain.

    Returns:
        Tuple of (server, port, username, password)

    Raises:
        IMAPError: If credentials not configured
    """
    server = keyring.get_password(SERVICE_NAME, "imap_server")
    port = keyring.get_password(SERVICE_NAME, "imap_port")
    username = keyring.get_password(SERVICE_NAME, "imap_username")
    password = keyring.get_password(SERVICE_NAME, "imap_password")

    if not all([server, username, password]):
        raise IMAPError(
            "IMAP not configured. Run 'python setup.py' first."
        )

    return server, port or "993", username, password


@contextmanager
def imap_connection():
    """Context manager for IMAP connection.

    Yields:
        Connected IMAPClient instance

    Example:
        with imap_connection() as client:
            client.select_folder('INBOX')
    """
    server, port, username, password = get_credentials()

    client = IMAPClient(server, port=int(port), ssl=True)
    try:
        client.login(username, password)
        yield client
    finally:
        try:
            client.logout()
        except Exception:
            pass


def to_str(value) -> str:
    """Convert bytes or str to str."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode('utf-8', errors='replace')
    return str(value)


def decode_header_value(value) -> str:
    """Decode MIME-encoded header value."""
    if not value:
        return ""

    # Convert bytes to str first
    if isinstance(value, bytes):
        value = value.decode('utf-8', errors='replace')

    decoded_parts = []
    for part, charset in email.header.decode_header(value):
        if isinstance(part, bytes):
            decoded_parts.append(part.decode(charset or 'utf-8', errors='replace'))
        else:
            decoded_parts.append(part)

    return ''.join(decoded_parts)


def parse_folder_path(imap_url: str) -> str:
    """Extract folder path from IMAP URL.

    Args:
        imap_url: URL like 'imap://user@server/INBOX/Folder/Sub'

    Returns:
        Folder path like 'INBOX/Folder/Sub'
    """
    # Remove scheme and authority, keep path
    # imap://user@server/INBOX/Folder → INBOX/Folder
    match = re.match(r'^imap://[^/]+/(.+)$', imap_url)
    if match:
        return match.group(1)

    # If it's just a path, return as-is
    if '://' not in imap_url:
        return imap_url

    raise IMAPError(f"Invalid IMAP URL format: {imap_url}")


def list_folders() -> list[dict]:
    """List all available IMAP folders.

    Returns:
        List of folder info dicts with 'name' and 'flags'
    """
    with imap_connection() as client:
        folders = client.list_folders()
        return [
            {
                "name": to_str(folder_name),
                "flags": [to_str(f) for f in flags]
            }
            for flags, delimiter, folder_name in folders
        ]


def list_messages(folder: str, limit: int = 20) -> list[dict]:
    """List messages in a folder.

    Args:
        folder: Folder path (e.g., 'INBOX' or 'INBOX/Subfolder')
        limit: Maximum messages to return (newest first)

    Returns:
        List of message summaries
    """
    with imap_connection() as client:
        # Select folder
        try:
            client.select_folder(folder, readonly=True)
        except Exception as e:
            raise IMAPError(f"Cannot open folder '{folder}': {e}")

        # Search for all messages, get newest
        message_ids = client.search(['ALL'])

        if not message_ids:
            return []

        # Get newest messages (last N)
        selected_ids = message_ids[-limit:] if len(message_ids) > limit else message_ids
        selected_ids = list(reversed(selected_ids))  # Newest first

        # Fetch headers
        messages = client.fetch(selected_ids, ['ENVELOPE', 'FLAGS', 'RFC822.SIZE'])

        results = []
        for msg_id, data in messages.items():
            envelope = data[b'ENVELOPE']

            # Parse sender
            from_addr = ""
            if envelope.from_:
                f = envelope.from_[0]
                name = decode_header_value(f.name) if f.name else ""
                mailbox = to_str(f.mailbox)
                host = to_str(f.host)
                if name:
                    from_addr = f"{name} <{mailbox}@{host}>"
                else:
                    from_addr = f"{mailbox}@{host}"

            # Parse date
            date_str = ""
            if envelope.date:
                try:
                    date_str = envelope.date.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    date_str = str(envelope.date)

            results.append({
                "id": msg_id,
                "subject": decode_header_value(envelope.subject) if envelope.subject else "(no subject)",
                "from": from_addr,
                "date": date_str,
                "size": data.get(b'RFC822.SIZE', 0),
                "flags": [to_str(f) for f in data.get(b'FLAGS', [])]
            })

        return results


def read_message(folder: str, message_id: int) -> dict:
    """Read a specific message.

    Args:
        folder: Folder path
        message_id: Message ID (UID)

    Returns:
        Full message data including body
    """
    with imap_connection() as client:
        try:
            client.select_folder(folder, readonly=True)
        except Exception as e:
            raise IMAPError(f"Cannot open folder '{folder}': {e}")

        # Fetch full message
        messages = client.fetch([message_id], ['RFC822', 'ENVELOPE', 'FLAGS'])

        if message_id not in messages:
            raise IMAPError(f"Message {message_id} not found in '{folder}'")

        data = messages[message_id]
        envelope = data[b'ENVELOPE']
        raw_email = data[b'RFC822']

        # Parse email
        msg = email.message_from_bytes(raw_email)

        # Extract body and attachments
        body_text = ""
        body_html = ""
        attachments = []

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                disposition = part.get_content_disposition()

                # Attachments
                if disposition == 'attachment' or (disposition == 'inline' and part.get_filename()):
                    payload = part.get_payload(decode=True)
                    attachments.append({
                        'filename': part.get_filename() or 'unnamed',
                        'content_type': content_type,
                        'size': len(payload) if payload else 0
                    })
                # Body text
                elif content_type == "text/plain" and not body_text:
                    payload = part.get_payload(decode=True)
                    charset = part.get_content_charset() or 'utf-8'
                    body_text = payload.decode(charset, errors='replace')
                # Body HTML
                elif content_type == "text/html" and not body_html:
                    payload = part.get_payload(decode=True)
                    charset = part.get_content_charset() or 'utf-8'
                    body_html = payload.decode(charset, errors='replace')
        else:
            payload = msg.get_payload(decode=True)
            charset = msg.get_content_charset() or 'utf-8'
            if msg.get_content_type() == "text/html":
                body_html = payload.decode(charset, errors='replace')
            else:
                body_text = payload.decode(charset, errors='replace')

        # Parse addresses
        def format_addrs(addr_list):
            if not addr_list:
                return []
            result = []
            for a in addr_list:
                name = decode_header_value(a.name) if a.name else ""
                mailbox = to_str(a.mailbox)
                host = to_str(a.host)
                if name:
                    result.append(f"{name} <{mailbox}@{host}>")
                else:
                    result.append(f"{mailbox}@{host}")
            return result

        return {
            "id": message_id,
            "subject": decode_header_value(envelope.subject) if envelope.subject else "",
            "from": format_addrs(envelope.from_),
            "to": format_addrs(envelope.to),
            "cc": format_addrs(envelope.cc),
            "date": str(envelope.date) if envelope.date else "",
            "message_id": to_str(envelope.message_id) if envelope.message_id else "",
            "in_reply_to": to_str(envelope.in_reply_to) if envelope.in_reply_to else "",
            "body_text": body_text,
            "body_html": body_html,
            "attachments": attachments,
            "flags": [to_str(f) for f in data.get(b'FLAGS', [])]
        }


def download_attachment(folder: str, message_id: int, attachment_index: int) -> dict:
    """Download an attachment from a message.

    Args:
        folder: Folder path
        message_id: Message ID (UID)
        attachment_index: Zero-based index of the attachment

    Returns:
        Dict with saved_to path, content_type, size, filename
    """
    with imap_connection() as client:
        try:
            client.select_folder(folder, readonly=True)
        except Exception as e:
            raise IMAPError(f"Cannot open folder '{folder}': {e}")

        messages = client.fetch([message_id], ['RFC822'])

        if message_id not in messages:
            raise IMAPError(f"Message {message_id} not found in '{folder}'")

        raw_email = messages[message_id][b'RFC822']
        msg = email.message_from_bytes(raw_email)

        # Find attachments
        attachments = []
        for part in msg.walk():
            disposition = part.get_content_disposition()
            if disposition == 'attachment' or (disposition == 'inline' and part.get_filename()):
                attachments.append(part)

        if not attachments:
            raise IMAPError(f"Message {message_id} has no attachments")

        if attachment_index < 0 or attachment_index >= len(attachments):
            raise IMAPError(f"Attachment index {attachment_index} out of range (0-{len(attachments)-1})")

        part = attachments[attachment_index]
        filename = part.get_filename() or f"attachment_{attachment_index}"
        content_type = part.get_content_type()
        payload = part.get_payload(decode=True)

        # Save to temp directory
        temp_dir = Path(tempfile.gettempdir()) / "streammail"
        temp_dir.mkdir(exist_ok=True)

        # Sanitize filename
        safe_filename = re.sub(r'[^\w\-_\.]', '_', filename)
        file_path = temp_dir / safe_filename

        with open(file_path, 'wb') as f:
            f.write(payload)

        return {
            "saved_to": str(file_path),
            "filename": filename,
            "content_type": content_type,
            "size": len(payload)
        }


def cleanup_attachments() -> dict:
    """Remove all downloaded attachments from temp directory."""
    temp_dir = Path(tempfile.gettempdir()) / "streammail"

    if not temp_dir.exists():
        return {"deleted": 0, "freed_bytes": 0}

    deleted = 0
    freed_bytes = 0

    for file_path in temp_dir.iterdir():
        if file_path.is_file():
            freed_bytes += file_path.stat().st_size
            file_path.unlink()
            deleted += 1

    return {"deleted": deleted, "freed_bytes": freed_bytes}


def search_messages(folder: str, query: str, limit: int = 20) -> list[dict]:
    """Search messages in a folder.

    Args:
        folder: Folder path
        query: Search query. Supports:
            - Simple text: searches subject and body
            - from:address
            - subject:text
            - since:YYYY-MM-DD
            - before:YYYY-MM-DD
        limit: Maximum results

    Returns:
        List of matching message summaries
    """
    with imap_connection() as client:
        try:
            client.select_folder(folder, readonly=True)
        except Exception as e:
            raise IMAPError(f"Cannot open folder '{folder}': {e}")

        # Build IMAP search criteria
        criteria = []

        # Parse query
        query_lower = query.lower()

        if query_lower.startswith("from:"):
            criteria = ['FROM', query[5:].strip()]
        elif query_lower.startswith("subject:"):
            criteria = ['SUBJECT', query[8:].strip()]
        elif query_lower.startswith("since:"):
            date_str = query[6:].strip()
            criteria = ['SINCE', date_str]
        elif query_lower.startswith("before:"):
            date_str = query[7:].strip()
            criteria = ['BEFORE', date_str]
        else:
            # General text search - search subject OR body
            criteria = ['OR', 'SUBJECT', query, 'BODY', query]

        # Execute search
        message_ids = client.search(criteria)

        if not message_ids:
            return []

        # Get newest matches
        selected_ids = message_ids[-limit:] if len(message_ids) > limit else message_ids
        selected_ids = list(reversed(selected_ids))

        # Fetch summaries
        messages = client.fetch(selected_ids, ['ENVELOPE', 'FLAGS'])

        results = []
        for msg_id, data in messages.items():
            envelope = data[b'ENVELOPE']

            from_addr = ""
            if envelope.from_:
                f = envelope.from_[0]
                name = decode_header_value(f.name) if f.name else ""
                mailbox = to_str(f.mailbox)
                host = to_str(f.host)
                if name:
                    from_addr = f"{name} <{mailbox}@{host}>"
                else:
                    from_addr = f"{mailbox}@{host}"

            results.append({
                "id": msg_id,
                "subject": decode_header_value(envelope.subject) if envelope.subject else "",
                "from": from_addr,
                "date": str(envelope.date) if envelope.date else ""
            })

        return results


def create_draft(folder: str, to: str, subject: str, body: str,
                 in_reply_to: Optional[str] = None,
                 cc: Optional[str] = None) -> dict:
    """Create a draft message in IMAP Drafts folder.

    Args:
        folder: Currently active folder (for context)
        to: Recipient address
        subject: Message subject
        body: Message body (plain text)
        in_reply_to: Message-ID to reply to
        cc: CC addresses (comma-separated)

    Returns:
        Info about created draft
    """
    with imap_connection() as client:
        # Build email message
        msg = email.message.EmailMessage()

        # Get username for From header
        _, _, username, _ = get_credentials()
        msg['From'] = username
        msg['To'] = to
        msg['Subject'] = subject
        msg['Date'] = email.utils.formatdate(localtime=True)
        msg['Message-ID'] = email.utils.make_msgid()

        if cc:
            msg['Cc'] = cc

        if in_reply_to:
            msg['In-Reply-To'] = in_reply_to
            msg['References'] = in_reply_to

        msg.set_content(body)

        # Find Drafts folder
        folders = client.list_folders()
        drafts_folder = None

        for flags, delimiter, folder_name in folders:
            # Look for Drafts folder by flag or name
            if b'\\Drafts' in flags or folder_name.lower() in ['drafts', 'draft', 'luonnokset']:
                drafts_folder = folder_name
                break

        if not drafts_folder:
            # Try common names
            for name in ['Drafts', 'INBOX.Drafts', 'Draft']:
                try:
                    client.select_folder(name)
                    drafts_folder = name
                    break
                except Exception:
                    continue

        if not drafts_folder:
            raise IMAPError("Cannot find Drafts folder. Available folders: " +
                          ", ".join(f[2] for f in folders))

        # Append to Drafts with \Draft flag
        result = client.append(
            drafts_folder,
            msg.as_bytes(),
            flags=[b'\\Draft', b'\\Seen']
        )

        return {
            "status": "created",
            "folder": drafts_folder,
            "to": to,
            "subject": subject,
            "message_id": msg['Message-ID']
        }


def test_connection():
    """Test IMAP connection with stored credentials."""
    try:
        server, port, username, _ = get_credentials()
        print(f"Testing connection to {server}:{port} as {username}...")

        with imap_connection() as client:
            folders = client.list_folders()
            print(f"✓ Connected successfully!")
            print(f"✓ Found {len(folders)} folders")

            # Show first few folders
            print("\nFolders:")
            for _, _, name in folders[:10]:
                print(f"  - {name}")
            if len(folders) > 10:
                print(f"  ... and {len(folders) - 10} more")

    except Exception as e:
        print(f"✗ Connection failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    test_connection()
