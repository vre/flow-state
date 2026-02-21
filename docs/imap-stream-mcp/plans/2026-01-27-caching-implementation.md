# DONE: IMAP Session Caching Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add connection keepalive and caching for folder/message lists to reduce latency and IMAP server load.

**Architecture:** New `session.py` module with `AccountSession` class holding connection + caches per account. All IMAP operations route through `get_session()`. Cache validated via IMAP metadata (UIDVALIDITY, UIDNEXT, EXISTS).

**Tech Stack:** Python 3.13, imapclient, dataclasses, pytest with mocking

**Design doc:** `docs/imap-stream-mcp/plans/2026-01-27-caching.md`

---

## Task 1: Data Structures

**Files:**
- Create: `imap-stream-mcp/session.py`
- Create: `imap-stream-mcp/tests/test_session.py`

**Step 1: Write the failing test**

```python
# tests/test_session.py
"""Tests for session caching."""
import pytest
from session import FolderCache, MessageListCache, AccountSession


class TestDataStructures:
    def test_folder_cache_creation(self):
        cache = FolderCache(
            folders=[{"name": "INBOX", "flags": ["\\HasNoChildren"]}],
            fetched_at=1000.0
        )
        assert cache.folders[0]["name"] == "INBOX"
        assert cache.fetched_at == 1000.0

    def test_message_list_cache_creation(self):
        cache = MessageListCache(
            messages=[{"uid": 1, "subject": "Test"}],
            uidvalidity=12345,
            uidnext=100,
            exists=50
        )
        assert cache.uidvalidity == 12345
        assert cache.uidnext == 100
        assert cache.exists == 50

    def test_account_session_initial_state(self):
        session = AccountSession("test@example.com")
        assert session.account == "test@example.com"
        assert session.connection is None
        assert session.folder_cache is None
        assert session.message_cache == {}
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/vre/work/flow-state/.worktrees/imap-caching/imap-stream-mcp && uv run pytest tests/test_session.py -v`
Expected: FAIL with "No module named 'session'"

**Step 3: Write minimal implementation**

```python
# session.py
"""IMAP session management with caching.

Provides AccountSession for connection keepalive and folder/message caching.
"""
from dataclasses import dataclass, field
from typing import Optional

from imapclient import IMAPClient


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
    connection: Optional[IMAPClient] = None
    last_activity: float = 0.0
    folder_cache: Optional[FolderCache] = None
    message_cache: dict[str, MessageListCache] = field(default_factory=dict)
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/vre/work/flow-state/.worktrees/imap-caching/imap-stream-mcp && uv run pytest tests/test_session.py -v`
Expected: PASS

**Step 5: Commit**

```bash
cd /Users/vre/work/flow-state/.worktrees/imap-caching/imap-stream-mcp
git add session.py tests/test_session.py
git commit -m "Add session data structures"
```

---

## Task 2: Connection Management

**Files:**
- Modify: `imap-stream-mcp/session.py`
- Modify: `imap-stream-mcp/tests/test_session.py`

**Step 1: Write the failing test**

```python
# Add to tests/test_session.py
import time
from unittest.mock import Mock, patch


class TestConnectionManagement:
    def test_get_connection_creates_new(self):
        """First call creates connection."""
        session = AccountSession("test")
        mock_client = Mock(spec=IMAPClient)

        with patch('session._create_connection', return_value=mock_client) as create:
            conn = session.get_connection()
            assert conn is mock_client
            assert session.connection is mock_client
            create.assert_called_once_with("test")

    def test_get_connection_reuses_existing(self):
        """Second call within timeout reuses connection."""
        session = AccountSession("test")
        mock_client = Mock(spec=IMAPClient)
        session.connection = mock_client
        session.last_activity = time.time()

        with patch('session._create_connection') as create:
            conn = session.get_connection()
            assert conn is mock_client
            create.assert_not_called()

    def test_get_connection_recreates_after_timeout(self):
        """Connection recreated after idle timeout."""
        session = AccountSession("test")
        old_client = Mock(spec=IMAPClient)
        new_client = Mock(spec=IMAPClient)
        session.connection = old_client
        session.last_activity = time.time() - 400  # Older than 300s timeout

        with patch('session._create_connection', return_value=new_client):
            conn = session.get_connection()
            assert conn is new_client
            old_client.logout.assert_called_once()

    def test_get_connection_recreates_on_noop_failure(self):
        """Connection recreated if NOOP fails."""
        session = AccountSession("test")
        old_client = Mock(spec=IMAPClient)
        old_client.noop.side_effect = Exception("Connection lost")
        new_client = Mock(spec=IMAPClient)
        session.connection = old_client
        session.last_activity = time.time()

        with patch('session._create_connection', return_value=new_client):
            conn = session.get_connection()
            assert conn is new_client
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/vre/work/flow-state/.worktrees/imap-caching/imap-stream-mcp && uv run pytest tests/test_session.py::TestConnectionManagement -v`
Expected: FAIL with "AccountSession has no attribute 'get_connection'"

**Step 3: Write minimal implementation**

```python
# Add to session.py after dataclass definitions
import time
from contextlib import contextmanager


CONNECTION_IDLE_TIMEOUT = 300  # 5 minutes


def _create_connection(account: str) -> IMAPClient:
    """Create new IMAP connection for account.

    Args:
        account: Account name for credentials lookup

    Returns:
        Connected IMAPClient instance
    """
    # Import here to avoid circular dependency
    from imap_client import get_credentials

    server, port, username, password = get_credentials(account)
    client = IMAPClient(server, port=int(port), ssl=True)
    client.login(username, password)
    return client


# Update AccountSession dataclass to add methods:
@dataclass
class AccountSession:
    """IMAP session with connection keepalive and caching."""
    account: str
    connection: Optional[IMAPClient] = None
    last_activity: float = 0.0
    folder_cache: Optional[FolderCache] = None
    message_cache: dict[str, MessageListCache] = field(default_factory=dict)

    def get_connection(self) -> IMAPClient:
        """Get or create IMAP connection.

        Reuses existing connection if within timeout and responsive.
        Creates new connection if none exists, timed out, or unresponsive.

        Returns:
            Connected IMAPClient instance
        """
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
            self.connection = _create_connection(self.account)

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
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/vre/work/flow-state/.worktrees/imap-caching/imap-stream-mcp && uv run pytest tests/test_session.py::TestConnectionManagement -v`
Expected: PASS

**Step 5: Commit**

```bash
cd /Users/vre/work/flow-state/.worktrees/imap-caching/imap-stream-mcp
git commit -a -m "Add connection management with keepalive"
```

---

## Task 3: Connection Context Manager

**Files:**
- Modify: `imap-stream-mcp/session.py`
- Modify: `imap-stream-mcp/tests/test_session.py`

**Step 1: Write the failing test**

```python
# Add to tests/test_session.py
import socket
from imapclient.exceptions import IMAPClientError


class TestConnectionContextManager:
    def test_context_manager_yields_connection(self):
        """Context manager yields working connection."""
        session = AccountSession("test")
        mock_client = Mock(spec=IMAPClient)

        with patch('session._create_connection', return_value=mock_client):
            with session.connection_ctx() as conn:
                assert conn is mock_client

    def test_context_manager_updates_activity(self):
        """Context manager updates last_activity on exit."""
        session = AccountSession("test")
        mock_client = Mock(spec=IMAPClient)
        session.connection = mock_client
        session.last_activity = 1000.0

        with session.connection_ctx():
            pass

        assert session.last_activity > 1000.0

    def test_context_manager_closes_on_error_keeps_cache(self):
        """Connection error closes connection but keeps caches."""
        session = AccountSession("test")
        mock_client = Mock(spec=IMAPClient)
        session.connection = mock_client
        session.last_activity = time.time()
        session.folder_cache = FolderCache(folders=[{"name": "INBOX"}], fetched_at=1.0)

        with pytest.raises(IMAPClientError):
            with session.connection_ctx() as conn:
                raise IMAPClientError("Test error")

        assert session.connection is None  # Connection closed
        assert session.folder_cache is not None  # Cache preserved
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/vre/work/flow-state/.worktrees/imap-caching/imap-stream-mcp && uv run pytest tests/test_session.py::TestConnectionContextManager -v`
Expected: FAIL with "AccountSession has no attribute 'connection_ctx'"

**Step 3: Write minimal implementation**

```python
# Add to AccountSession class in session.py
    @contextmanager
    def connection_ctx(self):
        """Context manager for IMAP operations.

        Yields connection for use. On error, closes connection but preserves caches.

        Yields:
            Connected IMAPClient instance
        """
        try:
            conn = self.get_connection()
            yield conn
            self.last_activity = time.time()
        except (IMAPClientError, ConnectionError, socket.error):
            self._close_connection()
            raise
```

Add imports at top:
```python
import socket
from imapclient.exceptions import IMAPClientError
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/vre/work/flow-state/.worktrees/imap-caching/imap-stream-mcp && uv run pytest tests/test_session.py::TestConnectionContextManager -v`
Expected: PASS

**Step 5: Commit**

```bash
cd /Users/vre/work/flow-state/.worktrees/imap-caching/imap-stream-mcp
git commit -a -m "Add connection context manager"
```

---

## Task 4: Folder Caching

**Files:**
- Modify: `imap-stream-mcp/session.py`
- Modify: `imap-stream-mcp/tests/test_session.py`

**Step 1: Write the failing test**

```python
# Add to tests/test_session.py
class TestFolderCaching:
    def test_get_folders_fetches_on_miss(self):
        """First call fetches from server."""
        session = AccountSession("test")
        mock_client = Mock(spec=IMAPClient)
        mock_client.list_folders.return_value = [
            ([b'\\HasNoChildren'], b'/', b'INBOX'),
            ([b'\\Drafts'], b'/', b'Drafts'),
        ]

        with patch('session._create_connection', return_value=mock_client):
            folders = session.get_folders()

        assert len(folders) == 2
        assert folders[0]["name"] == "INBOX"
        assert folders[1]["name"] == "Drafts"
        mock_client.list_folders.assert_called_once()

    def test_get_folders_returns_cached(self):
        """Second call returns cached data."""
        session = AccountSession("test")
        session.folder_cache = FolderCache(
            folders=[{"name": "INBOX", "flags": []}],
            fetched_at=time.time()
        )
        mock_client = Mock(spec=IMAPClient)
        session.connection = mock_client
        session.last_activity = time.time()

        folders = session.get_folders()

        assert folders[0]["name"] == "INBOX"
        mock_client.list_folders.assert_not_called()
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/vre/work/flow-state/.worktrees/imap-caching/imap-stream-mcp && uv run pytest tests/test_session.py::TestFolderCaching -v`
Expected: FAIL with "AccountSession has no attribute 'get_folders'"

**Step 3: Write minimal implementation**

```python
# Add to AccountSession class in session.py
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
            folders=[
                {"name": _to_str(name), "flags": [_to_str(f) for f in flags]}
                for flags, _, name in folders
            ],
            fetched_at=time.time()
        )
        return self.folder_cache.folders


def _to_str(value) -> str:
    """Convert bytes or str to str."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode('utf-8', errors='replace')
    return str(value)
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/vre/work/flow-state/.worktrees/imap-caching/imap-stream-mcp && uv run pytest tests/test_session.py::TestFolderCaching -v`
Expected: PASS

**Step 5: Commit**

```bash
cd /Users/vre/work/flow-state/.worktrees/imap-caching/imap-stream-mcp
git commit -a -m "Add folder caching"
```

---

## Task 5: Message List Caching

**Files:**
- Modify: `imap-stream-mcp/session.py`
- Modify: `imap-stream-mcp/tests/test_session.py`

**Step 1: Write the failing test**

```python
# Add to tests/test_session.py
class TestMessageListCaching:
    def test_get_messages_fetches_on_miss(self):
        """First call fetches from server."""
        session = AccountSession("test")
        mock_client = Mock(spec=IMAPClient)
        mock_client.folder_status.return_value = {
            b'UIDVALIDITY': 12345,
            b'UIDNEXT': 100,
            b'MESSAGES': 50
        }
        mock_client.search.return_value = [1, 2, 3]
        mock_client.fetch.return_value = {
            3: {b'ENVELOPE': Mock(subject=b'Test', from_=[Mock(name=None, mailbox=b'a', host=b'b.com')], date=None), b'FLAGS': []},
            2: {b'ENVELOPE': Mock(subject=b'Test2', from_=[Mock(name=None, mailbox=b'c', host=b'd.com')], date=None), b'FLAGS': []},
        }

        with patch('session._create_connection', return_value=mock_client):
            messages = session.get_messages("Drafts", limit=10)

        assert len(messages) == 2
        assert session.message_cache["Drafts"].uidvalidity == 12345

    def test_get_messages_returns_cached_on_match(self):
        """Returns cache if UIDVALIDITY/UIDNEXT/EXISTS unchanged."""
        session = AccountSession("test")
        session.message_cache["Drafts"] = MessageListCache(
            messages=[{"uid": 1, "subject": "Cached"}],
            uidvalidity=12345,
            uidnext=100,
            exists=50
        )
        mock_client = Mock(spec=IMAPClient)
        mock_client.folder_status.return_value = {
            b'UIDVALIDITY': 12345,
            b'UIDNEXT': 100,
            b'MESSAGES': 50
        }
        session.connection = mock_client
        session.last_activity = time.time()

        messages = session.get_messages("Drafts", limit=10)

        assert messages[0]["subject"] == "Cached"
        mock_client.search.assert_not_called()

    def test_get_messages_refetches_on_uidnext_change(self):
        """Refetches if UIDNEXT changed (new message)."""
        session = AccountSession("test")
        session.message_cache["Drafts"] = MessageListCache(
            messages=[{"uid": 1, "subject": "Old"}],
            uidvalidity=12345,
            uidnext=100,
            exists=50
        )
        mock_client = Mock(spec=IMAPClient)
        mock_client.folder_status.return_value = {
            b'UIDVALIDITY': 12345,
            b'UIDNEXT': 101,  # Changed!
            b'MESSAGES': 51
        }
        mock_client.search.return_value = [1, 2]
        mock_client.fetch.return_value = {
            2: {b'ENVELOPE': Mock(subject=b'New', from_=[Mock(name=None, mailbox=b'a', host=b'b.com')], date=None), b'FLAGS': []},
            1: {b'ENVELOPE': Mock(subject=b'Old', from_=[Mock(name=None, mailbox=b'a', host=b'b.com')], date=None), b'FLAGS': []},
        }
        session.connection = mock_client
        session.last_activity = time.time()

        messages = session.get_messages("Drafts", limit=10)

        mock_client.search.assert_called()  # Refetched
        assert session.message_cache["Drafts"].uidnext == 101
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/vre/work/flow-state/.worktrees/imap-caching/imap-stream-mcp && uv run pytest tests/test_session.py::TestMessageListCaching -v`
Expected: FAIL with "AccountSession has no attribute 'get_messages'"

**Step 3: Write minimal implementation**

```python
# Add to AccountSession class in session.py
    def get_messages(self, folder: str, limit: int = 20) -> list[dict]:
        """Get message list, validating cache with IMAP metadata.

        Args:
            folder: Folder path
            limit: Maximum messages to return

        Returns:
            List of message summaries (newest first)
        """
        conn = self.get_connection()

        # Get cheap metadata for validation
        status = conn.folder_status(folder, ['UIDVALIDITY', 'UIDNEXT', 'MESSAGES'])
        uidvalidity = status[b'UIDVALIDITY']
        uidnext = status[b'UIDNEXT']
        exists = status[b'MESSAGES']

        cached = self.message_cache.get(folder)
        if (cached and
            cached.uidvalidity == uidvalidity and
            cached.uidnext == uidnext and
            cached.exists == exists):
            return cached.messages[:limit]

        # Cache miss - fetch fresh
        conn.select_folder(folder, readonly=True)
        message_ids = conn.search(['ALL'])

        if not message_ids:
            self.message_cache[folder] = MessageListCache(
                messages=[],
                uidvalidity=uidvalidity,
                uidnext=uidnext,
                exists=exists
            )
            return []

        # Get newest messages
        selected_ids = message_ids[-limit:] if len(message_ids) > limit else message_ids
        selected_ids = list(reversed(selected_ids))

        data = conn.fetch(selected_ids, ['ENVELOPE', 'FLAGS', 'RFC822.SIZE'])

        messages = []
        for msg_id in selected_ids:
            if msg_id not in data:
                continue
            msg_data = data[msg_id]
            envelope = msg_data[b'ENVELOPE']

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

            messages.append({
                "id": msg_id,
                "subject": _to_str(envelope.subject) if envelope.subject else "(no subject)",
                "from": from_addr,
                "date": date_str,
                "size": msg_data.get(b'RFC822.SIZE', 0),
                "flags": [_to_str(f).lstrip('\\') for f in msg_data.get(b'FLAGS', [])]
            })

        self.message_cache[folder] = MessageListCache(
            messages=messages,
            uidvalidity=uidvalidity,
            uidnext=uidnext,
            exists=exists
        )
        return messages
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/vre/work/flow-state/.worktrees/imap-caching/imap-stream-mcp && uv run pytest tests/test_session.py::TestMessageListCaching -v`
Expected: PASS

**Step 5: Commit**

```bash
cd /Users/vre/work/flow-state/.worktrees/imap-caching/imap-stream-mcp
git commit -a -m "Add message list caching with validation"
```

---

## Task 6: Session Management Module-Level

**Files:**
- Modify: `imap-stream-mcp/session.py`
- Modify: `imap-stream-mcp/tests/test_session.py`

**Step 1: Write the failing test**

```python
# Add to tests/test_session.py
from session import get_session, invalidate_message_cache, _sessions


class TestSessionManagement:
    def setup_method(self):
        """Clear sessions before each test."""
        _sessions.clear()

    def test_get_session_creates_new(self):
        """Creates session for new account."""
        with patch('session.get_default_account', return_value="default@test.com"):
            session = get_session()
        assert session.account == "default@test.com"

    def test_get_session_reuses_existing(self):
        """Returns same session for same account."""
        with patch('session.get_default_account', return_value="test@test.com"):
            session1 = get_session()
            session2 = get_session()
        assert session1 is session2

    def test_get_session_with_explicit_account(self):
        """Uses explicit account when provided."""
        session = get_session("explicit@test.com")
        assert session.account == "explicit@test.com"

    def test_invalidate_message_cache(self):
        """Invalidates specific folder cache."""
        session = AccountSession("test")
        session.message_cache["Drafts"] = MessageListCache([], 1, 1, 1)
        session.message_cache["INBOX"] = MessageListCache([], 2, 2, 2)
        _sessions["test"] = session

        invalidate_message_cache("test", "Drafts")

        assert "Drafts" not in session.message_cache
        assert "INBOX" in session.message_cache
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/vre/work/flow-state/.worktrees/imap-caching/imap-stream-mcp && uv run pytest tests/test_session.py::TestSessionManagement -v`
Expected: FAIL with "cannot import name 'get_session'"

**Step 3: Write minimal implementation**

```python
# Add to session.py at module level (after imports, before dataclasses)

_sessions: dict[str, 'AccountSession'] = {}


def get_default_account() -> str | None:
    """Get default account name from imap_client."""
    from imap_client import get_default_account as _get_default
    return _get_default()


def get_session(account: str | None = None) -> 'AccountSession':
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
        session.message_cache.pop(folder, None)
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/vre/work/flow-state/.worktrees/imap-caching/imap-stream-mcp && uv run pytest tests/test_session.py::TestSessionManagement -v`
Expected: PASS

**Step 5: Commit**

```bash
cd /Users/vre/work/flow-state/.worktrees/imap-caching/imap-stream-mcp
git commit -a -m "Add session management functions"
```

---

## Task 7: Cache Update on Flag Operations

**Files:**
- Modify: `imap-stream-mcp/session.py`
- Modify: `imap-stream-mcp/tests/test_session.py`

**Step 1: Write the failing test**

```python
# Add to tests/test_session.py
class TestCacheUpdateOnFlags:
    def setup_method(self):
        _sessions.clear()

    def test_update_cached_flags(self):
        """Updates flags in cache without refetch."""
        session = AccountSession("test")
        session.message_cache["Drafts"] = MessageListCache(
            messages=[
                {"id": 1, "subject": "A", "flags": ["Seen"]},
                {"id": 2, "subject": "B", "flags": []},
            ],
            uidvalidity=1, uidnext=3, exists=2
        )
        _sessions["test"] = session

        from session import update_cached_flags
        update_cached_flags("test", "Drafts", 2, ["Seen", "Flagged"])

        assert session.message_cache["Drafts"].messages[1]["flags"] == ["Seen", "Flagged"]
        assert session.message_cache["Drafts"].messages[0]["flags"] == ["Seen"]  # Unchanged

    def test_update_cached_flags_nonexistent_message(self):
        """Does nothing if message not in cache."""
        session = AccountSession("test")
        session.message_cache["Drafts"] = MessageListCache(
            messages=[{"id": 1, "subject": "A", "flags": []}],
            uidvalidity=1, uidnext=2, exists=1
        )
        _sessions["test"] = session

        from session import update_cached_flags
        update_cached_flags("test", "Drafts", 999, ["Seen"])  # No error

        assert session.message_cache["Drafts"].messages[0]["flags"] == []
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/vre/work/flow-state/.worktrees/imap-caching/imap-stream-mcp && uv run pytest tests/test_session.py::TestCacheUpdateOnFlags -v`
Expected: FAIL with "cannot import name 'update_cached_flags'"

**Step 3: Write minimal implementation**

```python
# Add to session.py
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

    cache = session.message_cache.get(folder)
    if not cache:
        return

    for msg in cache.messages:
        if msg.get("id") == message_id:
            msg["flags"] = new_flags
            break
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/vre/work/flow-state/.worktrees/imap-caching/imap-stream-mcp && uv run pytest tests/test_session.py::TestCacheUpdateOnFlags -v`
Expected: PASS

**Step 5: Commit**

```bash
cd /Users/vre/work/flow-state/.worktrees/imap-caching/imap-stream-mcp
git commit -a -m "Add cache update for flag operations"
```

---

## Task 8: Integrate with imap_client.py - list_folders

**Files:**
- Modify: `imap-stream-mcp/imap_client.py`

**Step 1: Update list_folders to use session**

Replace the existing `list_folders` function:

```python
# In imap_client.py, replace list_folders function
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
```

**Step 2: Run existing tests**

Run: `cd /Users/vre/work/flow-state/.worktrees/imap-caching/imap-stream-mcp && uv run pytest -v`
Expected: All tests pass

**Step 3: Commit**

```bash
cd /Users/vre/work/flow-state/.worktrees/imap-caching/imap-stream-mcp
git commit -a -m "Integrate list_folders with session caching"
```

---

## Task 9: Integrate with imap_client.py - list_messages

**Files:**
- Modify: `imap-stream-mcp/imap_client.py`

**Step 1: Update list_messages to use session**

Replace the existing `list_messages` function:

```python
# In imap_client.py, replace list_messages function
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
```

**Step 2: Run existing tests**

Run: `cd /Users/vre/work/flow-state/.worktrees/imap-caching/imap-stream-mcp && uv run pytest -v`
Expected: All tests pass

**Step 3: Commit**

```bash
cd /Users/vre/work/flow-state/.worktrees/imap-caching/imap-stream-mcp
git commit -a -m "Integrate list_messages with session caching"
```

---

## Task 10: Integrate modify_flags with cache update

**Files:**
- Modify: `imap-stream-mcp/imap_client.py`

**Step 1: Update modify_flags to update cache**

Add cache update call to `modify_flags` function after successful operation:

```python
# In imap_client.py, at the end of modify_flags function, before final return
# After the for loop over message_ids, add:

    # Update cache for modified messages
    from session import update_cached_flags, get_session
    session = get_session()

    # Get current flags for successfully modified messages
    for msg_id in message_ids:
        if any(f.get("id") == msg_id for f in result["failed"]):
            continue
        # Fetch current flags from server
        try:
            msg_data = client.fetch([msg_id], ['FLAGS'])
            if msg_id in msg_data:
                current_flags = [normalize_flag_output(to_str(f)) for f in msg_data[msg_id].get(b'FLAGS', [])]
                update_cached_flags(session.account, folder, msg_id, current_flags)
        except Exception:
            pass  # Cache update failure is not critical
```

**Step 2: Run existing tests**

Run: `cd /Users/vre/work/flow-state/.worktrees/imap-caching/imap-stream-mcp && uv run pytest -v`
Expected: All tests pass

**Step 3: Commit**

```bash
cd /Users/vre/work/flow-state/.worktrees/imap-caching/imap-stream-mcp
git commit -a -m "Integrate modify_flags with cache update"
```

---

## Task 11: Integrate create_draft with cache invalidation

**Files:**
- Modify: `imap-stream-mcp/imap_client.py`

**Step 1: Update create_draft to invalidate cache**

Add cache invalidation at the end of `create_draft` function:

```python
# At the end of create_draft, before return statement
    from session import invalidate_message_cache, get_session
    session = get_session()
    invalidate_message_cache(session.account, drafts_folder)
```

**Step 2: Run existing tests**

Run: `cd /Users/vre/work/flow-state/.worktrees/imap-caching/imap-stream-mcp && uv run pytest -v`
Expected: All tests pass

**Step 3: Commit**

```bash
cd /Users/vre/work/flow-state/.worktrees/imap-caching/imap-stream-mcp
git commit -a -m "Integrate create_draft with cache invalidation"
```

---

## Task 12: Integrate modify_draft with cache invalidation

**Files:**
- Modify: `imap-stream-mcp/imap_client.py`

**Step 1: Update modify_draft to invalidate cache**

Add cache invalidation at the end of `modify_draft` function:

```python
# At the end of modify_draft, before return statement
    from session import invalidate_message_cache, get_session
    session = get_session()
    invalidate_message_cache(session.account, folder)  # Original folder
    if drafts_folder != folder:
        invalidate_message_cache(session.account, drafts_folder)
```

**Step 2: Run existing tests**

Run: `cd /Users/vre/work/flow-state/.worktrees/imap-caching/imap-stream-mcp && uv run pytest -v`
Expected: All tests pass

**Step 3: Commit**

```bash
cd /Users/vre/work/flow-state/.worktrees/imap-caching/imap-stream-mcp
git commit -a -m "Integrate modify_draft with cache invalidation"
```

---

## Task 13: Remove old imap_connection context manager usage

**Files:**
- Modify: `imap-stream-mcp/imap_client.py`

**Step 1: Update remaining functions to use session**

Functions still using `imap_connection()`:
- `read_message` - keep using connection directly (not cached)
- `download_attachment` - keep using connection directly (not cached)
- `search_messages` - keep using connection directly (not cached)

Update these to use `session.connection_ctx()`:

```python
# In read_message, replace:
#   with imap_connection() as client:
# with:
    from session import get_session
    session = get_session(account)
    with session.connection_ctx() as client:

# Same for download_attachment and search_messages
```

Add `account: str = None` parameter to these functions.

**Step 2: Run existing tests**

Run: `cd /Users/vre/work/flow-state/.worktrees/imap-caching/imap-stream-mcp && uv run pytest -v`
Expected: All tests pass

**Step 3: Commit**

```bash
cd /Users/vre/work/flow-state/.worktrees/imap-caching/imap-stream-mcp
git commit -a -m "Update remaining functions to use session connection"
```

---

## Task 14: Update Documentation

**Files:**
- Modify: `imap-stream-mcp/CHANGELOG.md`
- Modify: `imap-stream-mcp/TODO.md`
- Modify: `imap-stream-mcp/pyproject.toml`
- Modify: `.claude-plugin/marketplace.json`

**Step 1: Update CHANGELOG.md**

```markdown
## [0.4.0] - 2026-01-27

### Added
- Connection keepalive (5 min idle timeout) reduces connection overhead
- Folder list caching (persists until MCP shutdown)
- Message list caching with IMAP metadata validation (UIDVALIDITY, UIDNEXT, EXISTS)
- Cache automatically updated on flag operations
- Cache invalidated on draft create/modify operations
```

**Step 2: Update TODO.md**

Mark caching as done:
```markdown
- [x] Cache - Folder listing/message caching
```

**Step 3: Update version in pyproject.toml**

```toml
version = "0.4.0"
```

**Step 4: Update version in marketplace.json**

Update the imap-stream-mcp version to "0.4.0"

**Step 5: Commit**

```bash
cd /Users/vre/work/flow-state/.worktrees/imap-caching/imap-stream-mcp
git add -A
git commit -m "Update docs for v0.4.0 caching"
```

---

## Task 15: Manual Testing

**Step 1: Test folder caching**

```bash
claude -p "list my email folders, then list them again"
```

Expect: Second list noticeably faster.

**Step 2: Test message list caching**

```bash
claude -p "list messages in my Drafts folder, then list them again"
```

Expect: Second list returns instantly.

**Step 3: Test cache invalidation**

```bash
claude -p "create a draft to test@example.com with subject 'Cache Test', then list Drafts"
```

Expect: New draft appears in list.

**Step 4: Test flag cache update**

```bash
claude -p "list Drafts, mark the first message as flagged, then list Drafts again"
```

Expect: Flag appears without full refetch.

---

## Task 16: Final Review and Merge

**Step 1: Run all tests**

```bash
cd /Users/vre/work/flow-state/.worktrees/imap-caching/imap-stream-mcp && uv run pytest -v
```

**Step 2: Review changes**

```bash
git diff main..feature/imap-caching --stat
```

**Step 3: Merge to main**

```bash
cd /Users/vre/work/flow-state
git checkout main
git pull --rebase
git merge --squash .worktrees/imap-caching
git commit -m "Add session caching for imap-stream-mcp (v0.4.0)"
```

**Step 4: Cleanup worktree**

```bash
git worktree remove .worktrees/imap-caching
git branch -d feature/imap-caching
```
