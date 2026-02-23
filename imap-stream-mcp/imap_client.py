#!/usr/bin/env python3
"""IMAP Client for Streammail MCP.

Handles all IMAP operations with lazy connection management.
Credentials are fetched from macOS Keychain at connection time.
"""

import email
import email.header
import email.message
import email.utils
import json
import mimetypes
import os
import re
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

import keyring
from imapclient import IMAPClient

SERVICE_NAME = "imap-stream"

# Standard IMAP flags (RFC 3501)
STANDARD_FLAGS = {"seen", "flagged", "answered", "deleted", "draft"}


def normalize_flag_output(flag: str) -> str:
    """Strip backslash from IMAP flags for display.

    Args:
        flag: IMAP flag (e.g., '\\Seen' or '$label1')

    Returns:
        Flag without leading backslash (e.g., 'Seen' or '$label1')
    """
    if flag.startswith("\\"):
        return flag[1:]
    return flag


def normalize_flag_input(flag: str) -> str:
    """Prepare flag for IMAP: add backslash to standard flags.

    Args:
        flag: User-provided flag (e.g., 'seen', 'Flagged', '$label1')

    Returns:
        IMAP-ready flag (e.g., '\\Seen', '\\Flagged', '$label1')
    """
    # Strip existing backslash for normalization
    clean = flag.lstrip("\\")
    clean_lower = clean.lower()

    if clean_lower in STANDARD_FLAGS:
        # Capitalize standard flags consistently
        return "\\" + clean_lower.capitalize()
    return flag.lstrip("\\")  # Return keyword as-is


# Flag query -> IMAP search criterion mapping
# Liberal parsing: "flagged", "flagged:yes", "is:flagged", "starred" all work
_FLAG_QUERY_MAP: dict[str, str] = {
    # Flagged/starred
    "flagged": "FLAGGED",
    "flagged:yes": "FLAGGED",
    "is:flagged": "FLAGGED",
    "starred": "FLAGGED",
    "is:starred": "FLAGGED",
    "unflagged": "UNFLAGGED",
    "flagged:no": "UNFLAGGED",
    "is:unflagged": "UNFLAGGED",
    "unstarred": "UNFLAGGED",
    # Seen/read
    "seen": "SEEN",
    "seen:yes": "SEEN",
    "read": "SEEN",
    "is:seen": "SEEN",
    "is:read": "SEEN",
    "unseen": "UNSEEN",
    "seen:no": "UNSEEN",
    "unread": "UNSEEN",
    "is:unseen": "UNSEEN",
    "is:unread": "UNSEEN",
    # Answered
    "answered": "ANSWERED",
    "answered:yes": "ANSWERED",
    "is:answered": "ANSWERED",
    "unanswered": "UNANSWERED",
    "answered:no": "UNANSWERED",
    "is:unanswered": "UNANSWERED",
    # Deleted
    "deleted": "DELETED",
    "deleted:yes": "DELETED",
    "is:deleted": "DELETED",
}


def parse_flag_query(query: str) -> str | None:
    """Parse flag-based search query to IMAP criterion.

    Args:
        query: User query (e.g., 'flagged', 'is:unread', 'seen:no')

    Returns:
        IMAP search criterion string or None if not a flag query.
    """
    return _FLAG_QUERY_MAP.get(query.lower().strip())


class IMAPError(Exception):
    """IMAP operation error with helpful message."""

    pass


def get_credentials(account: str | None = None) -> tuple[str, str, str, str]:
    """Fetch IMAP credentials from keychain or environment.

    Primary: System keychain (cross-platform via keyring)
    Fallback: Environment variables (for automation/Docker/CI)

    Args:
        account: Account name. None = default account.

    Returns:
        Tuple of (server, port, username, password)

    Raises:
        IMAPError: If credentials not configured or account not found
    """
    accounts = list_accounts()

    if accounts:
        # Use account from keychain
        if account is None:
            account = get_default_account()
        if account not in accounts:
            raise IMAPError(f"Account '{account}' not found. Available: {', '.join(accounts)}")

        server = keyring.get_password(SERVICE_NAME, f"{account}:imap_server")
        port = keyring.get_password(SERVICE_NAME, f"{account}:imap_port")
        username = keyring.get_password(SERVICE_NAME, f"{account}:imap_username")
        password = keyring.get_password(SERVICE_NAME, f"{account}:imap_password")

        if not all([server, username, password]):
            raise IMAPError(f"Account '{account}' credentials incomplete.")

        return server, port or "993", username, password

    # Fallback: Environment variables (automation/Docker)
    server = os.environ.get("IMAP_STREAM_SERVER")
    port = os.environ.get("IMAP_STREAM_PORT")
    username = os.environ.get("IMAP_STREAM_USERNAME")
    password = os.environ.get("IMAP_STREAM_PASSWORD")

    if not all([server, username, password]):
        raise IMAPError("IMAP not configured. Run 'uv run python setup.py' to configure, or set IMAP_STREAM_* environment variables.")

    return server, port or "993", username, password


def list_accounts() -> list[str]:
    """Return list of configured account names.

    Returns:
        List of account names, empty if none configured
    """
    accounts_json = keyring.get_password(SERVICE_NAME, "accounts")
    if accounts_json:
        return json.loads(accounts_json)
    return []


def get_default_account() -> str | None:
    """Return default account name.

    Returns:
        Default account name, or None if no accounts configured
    """
    accounts = list_accounts()
    if not accounts:
        return None

    # Check for explicit default
    default = keyring.get_password(SERVICE_NAME, "default_account")
    if default and default in accounts:
        return default

    # Return first account
    return accounts[0]


@contextmanager
def imap_connection():
    """Context manager for standalone IMAP connection.

    NOTE: Only used by test_connection() utility. All other operations
    should use session.connection_ctx() for connection pooling and caching.

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
        return value.decode("utf-8", errors="replace")
    return str(value)


def decode_header_value(value) -> str:
    """Decode MIME-encoded header value."""
    if not value:
        return ""

    # Convert bytes to str first
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")

    decoded_parts = []
    for part, charset in email.header.decode_header(value):
        if isinstance(part, bytes):
            decoded_parts.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded_parts.append(part)

    return "".join(decoded_parts)


def format_address(addr) -> str:
    """Format a single email address for display.

    Args:
        addr: Address object with name, mailbox, host attributes

    Returns:
        Formatted string like "Name <email@domain>" or "email@domain"
    """
    name = decode_header_value(addr.name) if addr.name else ""
    mailbox = to_str(addr.mailbox)
    host = to_str(addr.host)

    if name:
        return f"{name} <{mailbox}@{host}>"
    return f"{mailbox}@{host}"


def format_address_list(addr_list) -> list[str]:
    """Format a list of email addresses for display.

    Args:
        addr_list: List of address objects, or None

    Returns:
        List of formatted address strings
    """
    if not addr_list:
        return []
    return [format_address(addr) for addr in addr_list]


def parse_folder_path(imap_url: str) -> str:
    """Extract folder path from IMAP URL.

    Args:
        imap_url: URL like 'imap://user@server/INBOX/Folder/Sub'

    Returns:
        Folder path like 'INBOX/Folder/Sub'
    """
    # Remove scheme and authority, keep path
    # imap://user@server/INBOX/Folder → INBOX/Folder
    match = re.match(r"^imap://[^/]+/(.+)$", imap_url)
    if match:
        return match.group(1)

    # If it's just a path, return as-is
    if "://" not in imap_url:
        return imap_url

    raise IMAPError(f"Invalid IMAP URL format: {imap_url}")


def list_folders(account: str = None) -> list[dict]:
    """List all available IMAP folders.

    Args:
        account: Account name. None uses default.

    Returns:
        List of folder info dicts with 'name' and 'flags'
    """
    from session import get_session

    session = get_session(account)
    return session.get_folders()


def list_messages(folder: str, limit: int = 20, account: str = None) -> list[dict]:
    """List messages in a folder.

    Args:
        folder: Folder path (e.g., 'INBOX' or 'INBOX/Subfolder')
        limit: Maximum messages to return (newest first)
        account: Account name. None uses default.

    Returns:
        List of message summaries
    """
    from session import get_session

    session = get_session(account)
    return session.get_messages(folder, limit)


def read_message(folder: str, message_id: int, account: str = None) -> dict:
    """Read a specific message.

    Args:
        folder: Folder path
        message_id: Message ID (UID)
        account: Account name. None uses default.

    Returns:
        Full message data including body
    """
    from session import get_session

    session = get_session(account)
    with session.connection_ctx() as client:
        try:
            client.select_folder(folder, readonly=True)
        except Exception as e:
            raise IMAPError(f"Cannot open folder '{folder}': {e}") from e

        # Fetch full message
        messages = client.fetch([message_id], ["RFC822", "ENVELOPE", "FLAGS"])

        if message_id not in messages:
            raise IMAPError(f"Message {message_id} not found in '{folder}'")

        data = messages[message_id]
        envelope = data[b"ENVELOPE"]
        raw_email = data[b"RFC822"]

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
                if disposition == "attachment" or (disposition == "inline" and part.get_filename()):
                    payload = part.get_payload(decode=True)
                    attachments.append(
                        {"filename": part.get_filename() or "unnamed", "content_type": content_type, "size": len(payload) if payload else 0}
                    )
                # Body text
                elif content_type == "text/plain" and not body_text:
                    payload = part.get_payload(decode=True)
                    charset = part.get_content_charset() or "utf-8"
                    body_text = payload.decode(charset, errors="replace")
                # Body HTML
                elif content_type == "text/html" and not body_html:
                    payload = part.get_payload(decode=True)
                    charset = part.get_content_charset() or "utf-8"
                    body_html = payload.decode(charset, errors="replace")
        else:
            payload = msg.get_payload(decode=True)
            charset = msg.get_content_charset() or "utf-8"
            if msg.get_content_type() == "text/html":
                body_html = payload.decode(charset, errors="replace")
            else:
                body_text = payload.decode(charset, errors="replace")

        return {
            "id": message_id,
            "subject": decode_header_value(envelope.subject) if envelope.subject else "",
            "from": format_address_list(envelope.from_),
            "to": format_address_list(envelope.to),
            "cc": format_address_list(envelope.cc),
            "date": str(envelope.date) if envelope.date else "",
            "message_id": to_str(envelope.message_id) if envelope.message_id else "",
            "in_reply_to": to_str(envelope.in_reply_to) if envelope.in_reply_to else "",
            "body_text": body_text,
            "body_html": body_html,
            "attachments": attachments,
            "flags": [normalize_flag_output(to_str(f)) for f in data.get(b"FLAGS", [])],
        }


def download_attachment(folder: str, message_id: int, attachment_index: int, account: str = None) -> dict:
    """Download an attachment from a message.

    Args:
        folder: Folder path
        message_id: Message ID (UID)
        attachment_index: Zero-based index of the attachment
        account: Account name. None uses default.

    Returns:
        Dict with saved_to path, content_type, size, filename
    """
    from session import get_session

    session = get_session(account)
    with session.connection_ctx() as client:
        try:
            client.select_folder(folder, readonly=True)
        except Exception as e:
            raise IMAPError(f"Cannot open folder '{folder}': {e}") from e

        messages = client.fetch([message_id], ["RFC822"])

        if message_id not in messages:
            raise IMAPError(f"Message {message_id} not found in '{folder}'")

        raw_email = messages[message_id][b"RFC822"]
        msg = email.message_from_bytes(raw_email)

        # Find attachments
        attachments = []
        for part in msg.walk():
            disposition = part.get_content_disposition()
            if disposition == "attachment" or (disposition == "inline" and part.get_filename()):
                attachments.append(part)

        if not attachments:
            raise IMAPError(f"Message {message_id} has no attachments")

        if attachment_index < 0 or attachment_index >= len(attachments):
            raise IMAPError(f"Attachment index {attachment_index} out of range (0-{len(attachments) - 1})")

        part = attachments[attachment_index]
        filename = part.get_filename() or f"attachment_{attachment_index}"
        content_type = part.get_content_type()
        payload = part.get_payload(decode=True)

        # Save to temp directory
        temp_dir = Path(tempfile.gettempdir()) / "streammail"
        temp_dir.mkdir(exist_ok=True)

        # Sanitize filename
        safe_filename = re.sub(r"[^\w\-_\.]", "_", filename)
        file_path = temp_dir / safe_filename

        with open(file_path, "wb") as f:
            f.write(payload)

        return {"saved_to": str(file_path), "filename": filename, "content_type": content_type, "size": len(payload)}


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


def search_messages(folder: str, query: str, limit: int = 20, account: str = None) -> list[dict]:
    """Search messages in a folder.

    Args:
        folder: Folder path
        query: Search query. Supports:
            - Simple text: searches subject and body
            - from:address
            - subject:text
            - since:YYYY-MM-DD
            - before:YYYY-MM-DD
            - Flag queries: flagged, unread, seen, answered, deleted
              Also: is:flagged, flagged:yes, flagged:no, starred, etc.
        limit: Maximum results
        account: Account name. None uses default.

    Returns:
        List of matching message summaries with id, subject, from, date, flags.
    """
    from session import get_session

    session = get_session(account)
    with session.connection_ctx() as client:
        try:
            client.select_folder(folder, readonly=True)
        except Exception as e:
            raise IMAPError(f"Cannot open folder '{folder}': {e}") from e

        # Build IMAP search criteria
        query_lower = query.lower().strip()

        # Try flag-based query first
        flag_criterion = parse_flag_query(query)
        if flag_criterion:
            criteria = [flag_criterion]
        elif query_lower.startswith("from:"):
            criteria = ["FROM", query[5:].strip()]
        elif query_lower.startswith("subject:"):
            criteria = ["SUBJECT", query[8:].strip()]
        elif query_lower.startswith("since:"):
            criteria = ["SINCE", query[6:].strip()]
        elif query_lower.startswith("before:"):
            criteria = ["BEFORE", query[7:].strip()]
        else:
            # General text search - search subject OR body
            criteria = ["OR", "SUBJECT", query, "BODY", query]

        # Execute search
        message_ids = client.search(criteria)

        if not message_ids:
            return []

        # Get newest matches
        selected_ids = message_ids[-limit:] if len(message_ids) > limit else message_ids
        selected_ids = list(reversed(selected_ids))

        # Fetch summaries
        messages = client.fetch(selected_ids, ["ENVELOPE", "FLAGS"])

        results = []
        for msg_id, data in messages.items():
            envelope = data[b"ENVELOPE"]
            from_addr = format_address(envelope.from_[0]) if envelope.from_ else ""

            flags = [f.decode() if isinstance(f, bytes) else str(f) for f in data.get(b"FLAGS", [])]
            results.append(
                {
                    "id": msg_id,
                    "subject": decode_header_value(envelope.subject) if envelope.subject else "",
                    "from": from_addr,
                    "date": str(envelope.date) if envelope.date else "",
                    "flags": flags,
                }
            )

        return results


MAX_ATTACHMENT_SIZE = 25 * 1024 * 1024  # 25 MB


def _attach_files(msg: email.message.EmailMessage, paths: list[str]) -> list[dict]:
    """Validate and attach files to an EmailMessage.

    Fail-fast: validates all paths before reading any file data.

    Args:
        msg: EmailMessage to attach files to.
        paths: List of absolute file paths.

    Returns:
        List of {name, size} dicts for response formatting.

    Raises:
        IMAPError: On invalid path, missing file, or oversize file.
    """
    resolved = []
    for p in paths:
        path = Path(p)
        if not path.is_absolute():
            raise IMAPError(f"Path must be absolute: '{p}'")
        if not path.is_file():
            if path.exists():
                raise IMAPError(f"Path is not a file: '{p}'")
            raise IMAPError(f"File not found: '{p}'")
        try:
            size = path.stat().st_size
        except OSError as e:
            raise IMAPError(f"Cannot read file: '{p}': {e}") from e
        if size > MAX_ATTACHMENT_SIZE:
            size_mb = size / (1024 * 1024)
            raise IMAPError(f"File too large: {path.name} is {size_mb:.1f} MB (max 25 MB)")
        resolved.append((path, size))

    result = []
    for path, size in resolved:
        try:
            data = path.read_bytes()
        except OSError as e:
            raise IMAPError(f"Cannot read file: '{path.name}': {e}") from e
        mime_type, _ = mimetypes.guess_type(str(path))
        if mime_type and "/" in mime_type:
            maintype, subtype = mime_type.split("/", 1)
        else:
            maintype, subtype = "application", "octet-stream"
        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=path.name)
        result.append({"name": path.name, "size": size})

    return result


def create_draft(
    folder: str,
    to: str,
    subject: str,
    body: str,
    in_reply_to: str | None = None,
    cc: str | None = None,
    html: str | None = None,
    attachments: list[str] | None = None,
    account: str = None,
) -> dict:
    """Create a draft message in IMAP Drafts folder.

    Args:
        folder: Currently active folder (for context)
        to: Recipient address
        subject: Message subject
        body: Message body (plain text)
        in_reply_to: Message-ID to reply to
        cc: CC addresses (comma-separated)
        html: HTML body (if provided, creates multipart/alternative)
        attachments: List of absolute file paths to attach.
        account: Account name. None uses default.

    Returns:
        Info about created draft
    """
    from session import get_session

    session = get_session(account)
    with session.connection_ctx() as client:
        # Build email message
        msg = email.message.EmailMessage()

        # Get username for From header
        _, _, username, _ = get_credentials()
        msg["From"] = username
        msg["To"] = to
        msg["Subject"] = subject
        msg["Date"] = email.utils.formatdate(localtime=True)
        msg["Message-ID"] = email.utils.make_msgid()

        if cc:
            msg["Cc"] = cc

        if in_reply_to:
            msg["In-Reply-To"] = in_reply_to
            msg["References"] = in_reply_to

        # Set body - plain text, optionally with HTML alternative
        msg.set_content(body)
        if html:
            msg.add_alternative(html, subtype="html")

        # Attach files (validates all paths before modifying message)
        att_info = []
        if attachments:
            att_info = _attach_files(msg, attachments)

        # Find Drafts folder
        folders = client.list_folders()
        drafts_folder = None

        for flags, _delimiter, folder_name in folders:
            # Look for Drafts folder by flag or name
            if b"\\Drafts" in flags or folder_name.lower() in ["drafts", "draft", "luonnokset"]:
                drafts_folder = folder_name
                break

        if not drafts_folder:
            # Try common names
            for name in ["Drafts", "INBOX.Drafts", "Draft"]:
                try:
                    client.select_folder(name)
                    drafts_folder = name
                    break
                except Exception:
                    continue

        if not drafts_folder:
            raise IMAPError("Cannot find Drafts folder. Available folders: " + ", ".join(f[2] for f in folders))

        # Append to Drafts with \Draft flag
        client.append(drafts_folder, msg.as_bytes(), flags=[b"\\Draft", b"\\Seen"])

        # Invalidate cache for drafts folder
        from session import invalidate_message_cache

        invalidate_message_cache(session.account, drafts_folder)

        response = {"status": "created", "folder": drafts_folder, "to": to, "subject": subject, "message_id": msg["Message-ID"]}
        if att_info:
            response["attachments"] = att_info
        return response


def modify_draft(
    folder: str,
    message_id: int,
    body: str,
    subject: str | None = None,
    to: str | None = None,
    cc: str | None = None,
    html: str | None = None,
    attachments: list[str] | None = None,
    account: str = None,
) -> dict:
    """Modify an existing draft message.

    Reads the original draft, preserves threading info and existing attachments,
    creates a new draft, then deletes the old one (append-before-delete).

    Args:
        folder: Folder containing the draft (usually Drafts)
        message_id: Message ID of the draft to modify
        body: New message body (required)
        subject: New subject (optional, keeps original if not provided)
        to: New recipient (optional, keeps original if not provided)
        cc: New CC (optional, keeps original if not provided)
        html: HTML body (if provided, creates multipart/alternative)
        attachments: List of absolute file paths to attach.
        account: Account name. None uses default.

    Returns:
        Info about the modified draft
    """
    from session import get_session

    session = get_session(account)
    with session.connection_ctx() as client:
        # Select folder
        try:
            client.select_folder(folder, readonly=False)
        except Exception as e:
            raise IMAPError(f"Cannot open folder '{folder}': {e}") from e

        # Fetch original draft
        messages = client.fetch([message_id], ["RFC822", "ENVELOPE"])

        if message_id not in messages:
            raise IMAPError(f"Message {message_id} not found in '{folder}'")

        data = messages[message_id]
        envelope = data[b"ENVELOPE"]
        raw_email = data[b"RFC822"]
        original_msg = email.message_from_bytes(raw_email)

        # Extract original values
        original_subject = decode_header_value(envelope.subject) if envelope.subject else ""
        original_to = []
        if envelope.to:
            for a in envelope.to:
                mailbox = to_str(a.mailbox)
                host = to_str(a.host)
                original_to.append(f"{mailbox}@{host}")
        original_cc = []
        if envelope.cc:
            for a in envelope.cc:
                mailbox = to_str(a.mailbox)
                host = to_str(a.host)
                original_cc.append(f"{mailbox}@{host}")

        # Preserve threading fields (decode and clean up)
        in_reply_to = original_msg.get("In-Reply-To", "")
        if in_reply_to:
            in_reply_to = decode_header_value(in_reply_to).replace("\n", "").replace("\r", "").strip()
        references = original_msg.get("References", "")
        if references:
            references = decode_header_value(references).replace("\n", "").replace("\r", "").strip()

        # Build new message
        new_msg = email.message.EmailMessage()

        _, _, username, _ = get_credentials()
        new_msg["From"] = username
        new_msg["To"] = to if to else ", ".join(original_to)
        new_msg["Subject"] = subject if subject else original_subject
        new_msg["Date"] = email.utils.formatdate(localtime=True)
        new_msg["Message-ID"] = email.utils.make_msgid()

        if cc:
            new_msg["Cc"] = cc
        elif original_cc:
            new_msg["Cc"] = ", ".join(original_cc)

        # Preserve threading
        if in_reply_to:
            new_msg["In-Reply-To"] = in_reply_to
        if references:
            new_msg["References"] = references

        # Set body - plain text, optionally with HTML alternative
        new_msg.set_content(body)
        if html:
            new_msg.add_alternative(html, subtype="html")

        # Preserve existing attachments from original draft
        preserved_att_info = []
        for part in original_msg.walk():
            disposition = part.get_content_disposition()
            filename = part.get_filename()
            if disposition == "attachment" or (disposition == "inline" and filename):
                payload = part.get_payload(decode=True)
                if payload is not None:
                    content_type = part.get_content_type()
                    maintype, subtype = content_type.split("/", 1)
                    new_msg.add_attachment(
                        payload,
                        maintype=maintype,
                        subtype=subtype,
                        filename=filename or "unnamed",
                    )
                    preserved_att_info.append(
                        {
                            "name": filename or "unnamed",
                            "size": len(payload),
                        }
                    )

        # Attach new files
        att_info = []
        if attachments:
            att_info = _attach_files(new_msg, attachments)

        # Find Drafts folder for appending
        folders = client.list_folders()
        drafts_folder = None
        for flags, _, folder_name in folders:
            if b"\\Drafts" in flags or folder_name.lower() in ["drafts", "draft", "luonnokset"]:
                drafts_folder = folder_name
                break

        if not drafts_folder:
            drafts_folder = folder  # Use current folder as fallback

        # Append-before-delete: append new draft first, then delete old
        client.append(drafts_folder, new_msg.as_bytes(), flags=[b"\\Draft", b"\\Seen"])

        client.delete_messages([message_id])
        client.expunge()

        # Invalidate cache for affected folders
        from session import invalidate_message_cache

        invalidate_message_cache(session.account, folder)  # Original folder
        if drafts_folder != folder:
            invalidate_message_cache(session.account, drafts_folder)

        all_att_info = preserved_att_info + att_info
        response = {
            "status": "modified",
            "folder": drafts_folder,
            "to": new_msg["To"],
            "subject": new_msg["Subject"],
            "message_id": new_msg["Message-ID"],
            "preserved_reply_to": bool(in_reply_to),
        }
        if all_att_info:
            response["attachments"] = all_att_info
        return response


def modify_flags(folder: str, message_ids: list[int], add_flags: list[str], remove_flags: list[str], account: str = None) -> dict:
    """Add or remove flags from messages.

    Args:
        folder: IMAP folder path
        message_ids: List of message IDs to modify
        add_flags: Flags to add (user format: 'Flagged', '$label1')
        remove_flags: Flags to remove
        account: Account name. None uses default.

    Returns:
        Dict with modified count, flags_added, flags_removed, failed list
    """
    from session import get_session

    session = get_session(account)

    result = {"modified": 0, "flags_added": list(set(add_flags)), "flags_removed": list(set(remove_flags)), "failed": []}

    if not message_ids:
        return result

    with session.connection_ctx() as client:
        try:
            client.select_folder(folder, readonly=False)
        except Exception as e:
            raise IMAPError(f"Cannot open folder '{folder}': {e}") from e

        for msg_id in message_ids:
            try:
                # Verify message exists
                exists = client.search(["UID", msg_id])
                if not exists:
                    result["failed"].append({"id": msg_id, "error": "Message not found"})
                    continue

                # Add flags
                if add_flags:
                    imap_flags = [normalize_flag_input(f).encode() for f in add_flags]
                    try:
                        client.add_flags([msg_id], imap_flags)
                    except Exception as e:
                        result["failed"].append({"id": msg_id, "operation": "add_flags", "flags": add_flags, "error": str(e)})
                        continue

                # Remove flags
                if remove_flags:
                    imap_flags = [normalize_flag_input(f).encode() for f in remove_flags]
                    try:
                        client.remove_flags([msg_id], imap_flags)
                    except Exception as e:
                        result["failed"].append({"id": msg_id, "operation": "remove_flags", "flags": remove_flags, "error": str(e)})
                        continue

                result["modified"] += 1

                # Update cache for successfully modified message
                try:
                    msg_data = client.fetch([msg_id], ["FLAGS"])
                    if msg_id in msg_data:
                        current_flags = [normalize_flag_output(to_str(f)) for f in msg_data[msg_id].get(b"FLAGS", [])]
                        from session import update_cached_flags

                        update_cached_flags(session.account, folder, msg_id, current_flags)
                except Exception:
                    pass  # Cache update failure is not critical

            except Exception as e:
                result["failed"].append({"id": msg_id, "error": str(e)})

    return result


def test_connection():
    """Test IMAP connection with stored credentials."""
    try:
        server, port, username, _ = get_credentials()
        print(f"Testing connection to {server}:{port} as {username}...")

        with imap_connection() as client:
            folders = client.list_folders()
            print("✓ Connected successfully!")
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
