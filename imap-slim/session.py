"""IMAP session management with caching.

Provides AccountSession for connection keepalive and folder/message caching.
"""

import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field

from bodystructure import count_attachments, extract_snippet, find_html_part, find_text_part, get_body_peek
from imapclient import IMAPClient

# Kept well below any plausible server idle-reaping window. Beyond this a
# connection is discarded unprobed, because discovering death costs a full
# socket timeout while discarding costs nothing.
CONNECTION_MAX_IDLE = 60

_sessions: dict[str, "AccountSession"] = {}
_sessions_lock = threading.Lock()


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

    with _sessions_lock:
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
    with _sessions_lock:
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
    with _sessions_lock:
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
    """Create a new IMAP connection.

    Credential lookup is the config stage and propagates unchanged, so the
    "not configured" setup guide still reaches the caller. Only the network
    portion becomes a ConnectionFailure.

    Args:
        account: Account name.

    Returns:
        A logged-in IMAPClient.

    Raises:
        ConnectionFailure: stage "connect", if the socket or login fails.
    """
    from imap_client import ConnectionFailure, get_credentials

    server, port, username, password = get_credentials(account)

    started = time.monotonic()
    client = None
    try:
        client = IMAPClient(server, port=int(port), ssl=True, timeout=30)
        client.login(username, password)
    except Exception as exc:
        if client is not None:
            # Without this the client is a local that nothing can ever close,
            # so a rejected login leaks a server slot until garbage collection.
            try:
                client.shutdown()
            except Exception:
                pass
        raise ConnectionFailure("connect", time.monotonic() - started) from exc
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
        """Get or create an IMAP connection, holding the session lock."""
        with self.lock:
            return self._acquire()

    def _acquire(self) -> IMAPClient:
        """Return a connection believed live. Caller must hold self.lock."""
        from imap_client import is_transport_failure

        if self.connection is not None:
            if time.time() - self.last_activity > CONNECTION_MAX_IDLE:
                self._discard_connection()
            else:
                try:
                    self.connection.noop()
                except Exception as exc:
                    if not is_transport_failure(exc, stage="probe"):
                        raise
                    self._discard_connection()

        if self.connection is None:
            self.connection = _create_connection(self.account)

        # Stamped after the slow work, not before it: a replacement must not be
        # born already aged by the probe and login that produced it.
        self.last_activity = time.time()
        return self.connection

    def _discard_connection(self):
        """Drop a connection believed dead. Sends nothing.

        LOGOUT is itself an IMAP command: on a silent socket it blocks for the
        full socket timeout, which is the cost this whole path exists to avoid.
        """
        if self.connection:
            try:
                self.connection.shutdown()
            except Exception:
                pass
            self.connection = None

    def _close_connection(self):
        """Close a connection believed healthy, releasing the server's slot."""
        if self.connection:
            try:
                self.connection.logout()
            except Exception:
                pass
            self.connection = None

    @contextmanager
    def _lease(self, stage: str = "command"):
        """Hold the lock, the connection and the failure policy for one operation.

        The lease covers the whole operation rather than just handing out a
        connection: one IMAP connection is a single protocol stream, so two
        callers using it concurrently interleave their responses, and either
        one's failure would otherwise discard the connection the other is using.

        Args:
            stage: Reported on failure, one of "probe", "connect", "command".
        """
        from imap_client import ConnectionFailure, is_transport_failure

        with self.lock:
            conn = self._acquire()
            started = time.monotonic()
            try:
                yield conn
            except Exception as exc:
                if is_transport_failure(exc, stage=stage):
                    self._discard_connection()
                    raise ConnectionFailure(stage, time.monotonic() - started) from exc
                raise
            self.last_activity = time.time()

    def run_op(self, operation, *, retry: bool = False, stage: str = "command"):
        """Run one operation under a lease, optionally retrying once.

        A context manager cannot do this: an exception thrown back at its yield
        can be suppressed or transformed, but the caller's `with` body cannot be
        run again. So an operation that wants a retry hands its body over as a
        callable instead.

        `retry` is opt-in and defaults off. A connection can die between the
        liveness probe and the command - that race cannot be probed away, only
        retried through - but replaying an operation that already appended a
        message would duplicate it. Only callers that read may opt in.

        Args:
            operation: Callable taking the connection and returning a result.
            retry: Whether to attempt once more on a fresh connection.
            stage: Reported on failure: "probe", "connect" or "command".

        Returns:
            Whatever `operation` returns.

        Raises:
            ConnectionFailure: if the transport failed and no attempt remains.
        """
        from imap_client import ConnectionFailure

        attempts = 2 if retry else 1
        for attempt in range(attempts):
            try:
                # The public lease, not _lease: run_op is public API and should
                # go through the same door its callers would.
                with self.connection_ctx(stage) as conn:
                    return operation(conn)
            except ConnectionFailure:
                # The lease already discarded the dead connection, so the next
                # attempt builds a fresh one.
                if attempt + 1 >= attempts:
                    raise
        raise AssertionError("unreachable")

    @contextmanager
    def connection_ctx(self, stage: str = "command"):
        """Public lease for one IMAP operation."""
        with self._lease(stage) as conn:
            yield conn

    def get_folders(self) -> list[dict]:
        """Get folder list, using cache if available.

        Returns:
            List of folder dicts with 'name' and 'flags'
        """
        if self.folder_cache:
            return self.folder_cache.folders

        with self._lease() as conn:
            folders = conn.list_folders()

        self.folder_cache = FolderCache(
            folders=[{"name": _to_str(name), "flags": [_to_str(f) for f in flags]} for flags, _, name in folders], fetched_at=time.time()
        )
        return self.folder_cache.folders

    def get_messages(self, folder: str, limit: int = 20, preview: bool = False) -> list[dict]:
        """Get message list, validating cache with IMAP metadata.

        Args:
            folder: Folder path
            limit: Maximum messages to return
            preview: Include body snippet (~100 chars) per message.

        Returns:
            List of message summaries (newest first)
        """
        with self._lease() as conn:
            return self._fetch_messages(conn, folder, limit, preview)

    def _fetch_messages(self, conn: IMAPClient, folder: str, limit: int, preview: bool) -> list[dict]:
        """Cache-validate and fetch. Caller must hold the lease."""
        from imap_client import IMAPError, is_transport_failure

        # Use select_folder to get atomic state for validation
        try:
            select_res = conn.select_folder(folder, readonly=True)
        except Exception as e:
            if is_transport_failure(e, stage="command"):
                raise
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

        data = conn.fetch(selected_ids, ["ENVELOPE", "FLAGS", "RFC822.SIZE", "BODYSTRUCTURE"])

        snippets: dict[int, str] = {}
        if preview:
            try:
                snippet_info: dict[int, tuple[str, bytes, bytes, bool]] = {}
                for msg_id in selected_ids:
                    msg_data = data.get(msg_id)
                    if not msg_data:
                        continue
                    bodystructure = msg_data.get(b"BODYSTRUCTURE")
                    part = find_text_part(bodystructure)
                    is_html = False
                    if part is None:
                        part = find_html_part(bodystructure)
                        is_html = part is not None
                    if part:
                        section, charset, encoding = part
                        snippet_info[msg_id] = (section, charset, encoding, is_html)

                snippet_raw: dict[int, dict] = {}
                section_groups: dict[str, list[int]] = {}
                for msg_id, (section, _, _, _) in snippet_info.items():
                    section_groups.setdefault(section, []).append(msg_id)

                for section, group_ids in section_groups.items():
                    try:
                        group_data = conn.fetch(group_ids, [f"BODY.PEEK[{section}]<0.600>"])
                    except Exception as exc:
                        if is_transport_failure(exc, stage="command"):
                            raise
                        continue
                    for msg_id, payload in group_data.items():
                        if isinstance(payload, dict):
                            snippet_raw[msg_id] = payload

                for msg_id, (section, charset, encoding, is_html) in snippet_info.items():
                    raw = get_body_peek(snippet_raw.get(msg_id, {}), section)
                    snippets[msg_id] = extract_snippet(raw, charset, encoding, is_html) if raw else ""
            except Exception as exc:
                if is_transport_failure(exc, stage="command"):
                    raise
                snippets = {}

        messages = []
        for msg_id in selected_ids:
            if msg_id not in data:
                continue
            msg_data = data[msg_id]
            envelope = msg_data[b"ENVELOPE"]
            bodystructure = msg_data.get(b"BODYSTRUCTURE")

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
                    "attachment_count": count_attachments(bodystructure) if bodystructure is not None else 0,
                    "snippet": snippets.get(msg_id, ""),
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
