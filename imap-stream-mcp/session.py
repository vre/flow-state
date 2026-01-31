"""IMAP session management with caching.

Provides AccountSession for connection keepalive and folder/message caching.
"""

import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field

from imapclient import IMAPClient
from imapclient.exceptions import IMAPClientError

CONNECTION_IDLE_TIMEOUT = 300  # 5 minutes

_sessions: dict[str, "AccountSession"] = {}


def get_default_account() -> str | None:
    """Get default account name from imap_client."""
    from imap_client import get_default_account as _get_default

    return _get_default()


def get_session(account: str | None = None) -> "AccountSession":
    """Get or create session for account.

    Args:
        account: Account name. None uses default account.

    Returns:
        AccountSession for the account
    """
    if account is None:
        account = get_default_account()

    if account not in _sessions:
        _sessions[account] = AccountSession(account)

    return _sessions[account]


def invalidate_message_cache(account: str, folder: str):
    """Invalidate message cache for a folder.

    Called after operations that modify folder contents (move, delete, draft).

    Args:
        account: Account name
        folder: Folder to invalidate
    """
    session = _sessions.get(account)
    if session:
        with session.lock:
            session.message_cache.pop(folder, None)


def update_cached_flags(account: str, folder: str, message_id: int, new_flags: list[str]):
    """Update flags for a message in cache.

    Called after successful flag modification to keep cache in sync.

    Args:
        account: Account name
        folder: Folder containing message
        message_id: Message ID
        new_flags: New flag list (user format without backslashes)
    """
    session = _sessions.get(account)
    if not session:
        return

    with session.lock:
        cache = session.message_cache.get(folder)
        if not cache:
            return

        for msg in cache.messages:
            if msg.get("id") == message_id:
                msg["flags"] = new_flags
                break


def _create_connection(account: str) -> IMAPClient:
    """Create new IMAP connection for account."""
    from imap_client import get_credentials

    server, port, username, password = get_credentials(account)
    client = IMAPClient(server, port=int(port), ssl=True)
    client.login(username, password)
    return client


@dataclass
class FolderCache:
    """Cached folder listing."""

    folders: list[dict]
    fetched_at: float


@dataclass
class MessageListCache:
    """Cached message list with validation metadata."""

    messages: list[dict]
    uidvalidity: int
    uidnext: int
    exists: int


@dataclass
class AccountSession:
    """IMAP session with connection keepalive and caching."""

    account: str
    connection: IMAPClient | None = None
    last_activity: float = 0.0
    folder_cache: FolderCache | None = None
    message_cache: dict[str, MessageListCache] = field(default_factory=dict)
    lock: threading.RLock = field(default_factory=threading.RLock)

    def get_connection(self) -> IMAPClient:
        """Get or create IMAP connection."""
        now = time.time()

        if self.connection:
            if now - self.last_activity > CONNECTION_IDLE_TIMEOUT:
                self._close_connection()
            else:
                try:
                    self.connection.noop()
                except Exception:
                    self._close_connection()

        if not self.connection:
            try:
                self.connection = _create_connection(self.account)
            except Exception:
                self.connection = None
                raise

        self.last_activity = now
        return self.connection

    def _close_connection(self):
        """Close connection without clearing caches."""
        if self.connection:
            try:
                self.connection.logout()
            except Exception:
                pass
            self.connection = None

    @contextmanager
    def connection_ctx(self):
        """Context manager for IMAP operations.

        Yields connection for use. On error, closes connection but preserves caches.
        """
        try:
            conn = self.get_connection()
            yield conn
            self.last_activity = time.time()
        except (OSError, IMAPClientError, ConnectionError):
            self._close_connection()
            raise

    def get_folders(self) -> list[dict]:
        """Get folder list, using cache if available.

        Returns:
            List of folder dicts with 'name' and 'flags'
        """
        if self.folder_cache:
            return self.folder_cache.folders

        conn = self.get_connection()
        folders = conn.list_folders()

        self.folder_cache = FolderCache(
            folders=[{"name": _to_str(name), "flags": [_to_str(f) for f in flags]} for flags, _, name in folders], fetched_at=time.time()
        )
        return self.folder_cache.folders

    def get_messages(self, folder: str, limit: int = 20) -> list[dict]:
        """Get message list, validating cache with IMAP metadata.

        Args:
            folder: Folder path
            limit: Maximum messages to return

        Returns:
            List of message summaries (newest first)
        """
        conn = self.get_connection()

        # Use select_folder to get atomic state for validation
        try:
            select_res = conn.select_folder(folder, readonly=True)
        except Exception as e:
            from imap_client import IMAPError

            raise IMAPError(f"Cannot open folder '{folder}': {e}") from e

        # Parse metadata from select response
        # IMAPClient usually returns dict with keys like b'UIDVALIDITY', b'UIDNEXT', b'EXISTS'
        uidvalidity = select_res.get(b"UIDVALIDITY")
        uidnext = select_res.get(b"UIDNEXT")
        exists = select_res.get(b"EXISTS")

        with self.lock:
            cached = self.message_cache.get(folder)
            if cached and cached.uidvalidity == uidvalidity and cached.uidnext == uidnext and cached.exists == exists:
                return cached.messages[:limit]

        # Cache miss - fetch fresh
        # Folder is already selected
        message_ids = conn.search(["ALL"])

        if not message_ids:
            with self.lock:
                self.message_cache[folder] = MessageListCache(messages=[], uidvalidity=uidvalidity, uidnext=uidnext, exists=exists)
            return []

        # Get newest messages
        selected_ids = message_ids[-limit:] if len(message_ids) > limit else message_ids
        selected_ids = list(reversed(selected_ids))

        data = conn.fetch(selected_ids, ["ENVELOPE", "FLAGS", "RFC822.SIZE"])

        messages = []
        for msg_id in selected_ids:
            if msg_id not in data:
                continue
            msg_data = data[msg_id]
            envelope = msg_data[b"ENVELOPE"]

            from_addr = ""
            if envelope.from_:
                addr = envelope.from_[0]
                mailbox = _to_str(addr.mailbox)
                host = _to_str(addr.host)
                from_addr = f"{mailbox}@{host}"

            date_str = ""
            if envelope.date:
                try:
                    date_str = envelope.date.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    date_str = str(envelope.date)

            messages.append(
                {
                    "id": msg_id,
                    "subject": _to_str(envelope.subject) if envelope.subject else "(no subject)",
                    "from": from_addr,
                    "date": date_str,
                    "size": msg_data.get(b"RFC822.SIZE", 0),
                    "flags": [_to_str(f).lstrip("\\") for f in msg_data.get(b"FLAGS", [])],
                }
            )

        with self.lock:
            self.message_cache[folder] = MessageListCache(messages=messages, uidvalidity=uidvalidity, uidnext=uidnext, exists=exists)
        return messages


def _to_str(value) -> str:
    """Convert bytes or str to str."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)
