"""Tests for session caching."""

import threading
import time
from unittest.mock import Mock, patch

import pytest
from imap_client import ConnectionFailure
from imapclient import IMAPClient
from imapclient.exceptions import IMAPClientError, LoginError
from session import (
    AccountSession,
    FolderCache,
    MessageListCache,
    _create_connection,
    _sessions,
    get_session,
    invalidate_message_cache,
    update_cached_flags,
)


class TestDataStructures:
    def test_folder_cache_creation(self):
        cache = FolderCache(folders=[{"name": "INBOX", "flags": ["\\HasNoChildren"]}], fetched_at=1000.0)
        assert cache.folders[0]["name"] == "INBOX"
        assert cache.fetched_at == 1000.0

    def test_message_list_cache_creation(self):
        cache = MessageListCache(messages=[{"id": 1, "subject": "Test"}], uidvalidity=12345, uidnext=100, exists=50)
        assert cache.uidvalidity == 12345
        assert cache.uidnext == 100
        assert cache.exists == 50

    def test_account_session_initial_state(self):
        session = AccountSession("test@example.com")
        assert session.account == "test@example.com"
        assert session.connection is None
        assert session.folder_cache is None
        assert session.message_cache == {}


class TestConnectionManagement:
    def test_get_connection_creates_new(self):
        """First call creates connection."""
        session = AccountSession("test")
        mock_client = Mock(spec=IMAPClient)

        with patch("session._create_connection", return_value=mock_client) as create:
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

        with patch("session._create_connection") as create:
            conn = session.get_connection()
            assert conn is mock_client
            create.assert_not_called()

    def test_get_connection_recreates_after_timeout(self):
        """Connection replaced past the idle threshold, discarded not logged out.

        Changed in cut 2: the threshold moved 300s -> 60s, and a connection
        believed dead is dropped with shutdown(), because LOGOUT is itself an
        IMAP command and blocks for the full socket timeout on a dead socket.
        """
        session = AccountSession("test")
        old_client = Mock(spec=IMAPClient)
        new_client = Mock(spec=IMAPClient)
        session.connection = old_client
        session.last_activity = time.time() - 61  # older than CONNECTION_MAX_IDLE

        with patch("session._create_connection", return_value=new_client):
            conn = session.get_connection()
            assert conn is new_client
            old_client.shutdown.assert_called_once()
            old_client.logout.assert_not_called()

    def test_get_connection_recreates_on_noop_failure(self):
        """Connection recreated if the probe fails on the transport.

        Changed in cut 2: a bare Exception from noop() no longer forces a
        reconnect. Only a transport-shaped failure does; anything else is a
        real error and is raised rather than hidden behind a new connection.
        """
        session = AccountSession("test")
        old_client = Mock(spec=IMAPClient)
        old_client.noop.side_effect = TimeoutError("Connection lost")
        new_client = Mock(spec=IMAPClient)
        session.connection = old_client
        session.last_activity = time.time()

        with patch("session._create_connection", return_value=new_client):
            conn = session.get_connection()
            assert conn is new_client


class TestConnectionContextManager:
    def test_context_manager_yields_connection(self):
        """Context manager yields working connection."""
        session = AccountSession("test")
        mock_client = Mock(spec=IMAPClient)

        with patch("session._create_connection", return_value=mock_client):
            with session.connection_ctx() as conn:
                assert conn is mock_client

    def test_context_manager_updates_activity(self):
        """Context manager updates last_activity on exit."""
        session = AccountSession("test")
        mock_client = Mock(spec=IMAPClient)
        session.connection = mock_client
        old_time = time.time() - 10  # 10 seconds ago, within timeout
        session.last_activity = old_time

        with session.connection_ctx():
            pass

        assert session.last_activity > old_time

    def test_context_manager_discards_on_transport_error_keeps_cache(self):
        """A transport failure discards the connection but keeps caches.

        Changed in cut 2: the trigger is a transport failure, not any
        IMAPClientError. A rejected command means the server answered, so the
        connection is alive and must not be thrown away.
        """
        session = AccountSession("test")
        mock_client = Mock(spec=IMAPClient)
        session.connection = mock_client
        session.last_activity = time.time()
        session.folder_cache = FolderCache(folders=[{"name": "INBOX"}], fetched_at=1.0)

        with pytest.raises(ConnectionFailure), session.connection_ctx():
            raise TimeoutError("Test error")

        assert session.connection is None  # discarded
        assert session.folder_cache is not None  # cache preserved

    def test_context_manager_keeps_connection_on_command_error(self):
        """A rejected command leaves the connection in place."""
        session = AccountSession("test")
        mock_client = Mock(spec=IMAPClient)
        session.connection = mock_client
        session.last_activity = time.time()

        with pytest.raises(IMAPClientError), session.connection_ctx():
            raise IMAPClientError("Test error")

        assert session.connection is mock_client
        mock_client.shutdown.assert_not_called()


class TestFolderCaching:
    def test_get_folders_fetches_on_miss(self):
        """First call fetches from server."""
        session = AccountSession("test")
        mock_client = Mock(spec=IMAPClient)
        mock_client.list_folders.return_value = [
            ([b"\\HasNoChildren"], b"/", b"INBOX"),
            ([b"\\Drafts"], b"/", b"Drafts"),
        ]

        with patch("session._create_connection", return_value=mock_client):
            folders = session.get_folders()

        assert len(folders) == 2
        assert folders[0]["name"] == "INBOX"
        assert folders[1]["name"] == "Drafts"
        mock_client.list_folders.assert_called_once()

    def test_get_folders_returns_cached(self):
        """Second call returns cached data."""
        session = AccountSession("test")
        session.folder_cache = FolderCache(folders=[{"name": "INBOX", "flags": []}], fetched_at=time.time())
        mock_client = Mock(spec=IMAPClient)
        session.connection = mock_client
        session.last_activity = time.time()

        folders = session.get_folders()

        assert folders[0]["name"] == "INBOX"
        mock_client.list_folders.assert_not_called()


class TestMessageListCaching:
    def test_get_messages_fetches_on_miss(self):
        """First call fetches from server."""
        session = AccountSession("test")
        mock_client = Mock(spec=IMAPClient)
        mock_client.select_folder.return_value = {b"UIDVALIDITY": 12345, b"UIDNEXT": 100, b"EXISTS": 50}
        mock_client.search.return_value = [1, 2, 3]
        mock_client.fetch.return_value = {
            3: {
                b"ENVELOPE": Mock(subject=b"Test", from_=[Mock(name=None, mailbox=b"a", host=b"b.com")], date=None),
                b"FLAGS": [],
                b"BODYSTRUCTURE": None,
            },
            2: {
                b"ENVELOPE": Mock(subject=b"Test2", from_=[Mock(name=None, mailbox=b"c", host=b"d.com")], date=None),
                b"FLAGS": [],
                b"BODYSTRUCTURE": None,
            },
        }

        with patch("session._create_connection", return_value=mock_client):
            messages = session.get_messages("Drafts", limit=10)

        assert len(messages) == 2
        assert session.message_cache["Drafts"].uidvalidity == 12345

    def test_get_messages_returns_cached_on_match(self):
        """Returns cache if UIDVALIDITY/UIDNEXT/EXISTS unchanged."""
        session = AccountSession("test")
        session.message_cache["Drafts"] = MessageListCache(
            messages=[{"uid": 1, "subject": "Cached"}], uidvalidity=12345, uidnext=100, exists=50
        )
        mock_client = Mock(spec=IMAPClient)
        mock_client.select_folder.return_value = {b"UIDVALIDITY": 12345, b"UIDNEXT": 100, b"EXISTS": 50}
        session.connection = mock_client
        session.last_activity = time.time()

        messages = session.get_messages("Drafts", limit=10)

        assert messages[0]["subject"] == "Cached"
        mock_client.search.assert_not_called()

    def test_get_messages_refetches_on_uidnext_change(self):
        """Refetches if UIDNEXT changed (new message)."""
        session = AccountSession("test")
        session.message_cache["Drafts"] = MessageListCache(
            messages=[{"uid": 1, "subject": "Old"}], uidvalidity=12345, uidnext=100, exists=50
        )
        mock_client = Mock(spec=IMAPClient)
        mock_client.select_folder.return_value = {
            b"UIDVALIDITY": 12345,
            b"UIDNEXT": 101,  # Changed!
            b"EXISTS": 51,
        }
        mock_client.search.return_value = [1, 2]
        mock_client.fetch.return_value = {
            2: {
                b"ENVELOPE": Mock(subject=b"New", from_=[Mock(name=None, mailbox=b"a", host=b"b.com")], date=None),
                b"FLAGS": [],
                b"BODYSTRUCTURE": None,
            },
            1: {
                b"ENVELOPE": Mock(subject=b"Old", from_=[Mock(name=None, mailbox=b"a", host=b"b.com")], date=None),
                b"FLAGS": [],
                b"BODYSTRUCTURE": None,
            },
        }
        session.connection = mock_client
        session.last_activity = time.time()

        session.get_messages("Drafts", limit=10)

        mock_client.search.assert_called()  # Refetched
        assert session.message_cache["Drafts"].uidnext == 101


class TestSessionManagement:
    def setup_method(self):
        """Clear sessions before each test."""
        _sessions.clear()

    def test_get_session_creates_new(self):
        """Creates session for new account."""
        with patch("session.get_default_account", return_value="default@test.com"):
            session = get_session()
        assert session.account == "default@test.com"

    def test_get_session_reuses_existing(self):
        """Returns same session for same account."""
        with patch("session.get_default_account", return_value="test@test.com"):
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
            uidvalidity=1,
            uidnext=3,
            exists=2,
        )
        _sessions["test"] = session

        update_cached_flags("test", "Drafts", 2, ["Seen", "Flagged"])

        assert session.message_cache["Drafts"].messages[1]["flags"] == ["Seen", "Flagged"]
        assert session.message_cache["Drafts"].messages[0]["flags"] == ["Seen"]  # Unchanged

    def test_update_cached_flags_nonexistent_message(self):
        """Does nothing if message not in cache."""
        session = AccountSession("test")
        session.message_cache["Drafts"] = MessageListCache(
            messages=[{"id": 1, "subject": "A", "flags": []}], uidvalidity=1, uidnext=2, exists=1
        )
        _sessions["test"] = session

        update_cached_flags("test", "Drafts", 999, ["Seen"])  # No error

        assert session.message_cache["Drafts"].messages[0]["flags"] == []


class TestDiscardVsClose:
    """AC1: a suspected-dead connection is discarded, never logged out."""

    def test_discard_uses_shutdown_not_logout(self):
        session = AccountSession("test")
        client = Mock(spec=IMAPClient)
        session.connection = client

        session._discard_connection()

        client.shutdown.assert_called_once()
        client.logout.assert_not_called()
        assert session.connection is None

    def test_healthy_close_uses_logout(self):
        session = AccountSession("test")
        client = Mock(spec=IMAPClient)
        session.connection = client

        session._close_connection()

        client.logout.assert_called_once()
        assert session.connection is None

    def test_discard_survives_a_raising_shutdown(self):
        session = AccountSession("test")
        client = Mock(spec=IMAPClient)
        client.shutdown.side_effect = OSError("already gone")
        session.connection = client

        session._discard_connection()

        assert session.connection is None


class TestIdleThreshold:
    """AC2: a long-idle connection is replaced without probing."""

    def test_long_idle_is_discarded_without_probe(self):
        session = AccountSession("test")
        old = Mock(spec=IMAPClient)
        session.connection = old
        session.last_activity = time.time() - 61
        new = Mock(spec=IMAPClient)

        with patch("session._create_connection", return_value=new):
            result = session.get_connection()

        old.noop.assert_not_called()
        old.shutdown.assert_called_once()
        old.logout.assert_not_called()
        assert result is new

    def test_exactly_at_threshold_takes_the_recent_path(self):
        session = AccountSession("test")
        client = Mock(spec=IMAPClient)
        session.connection = client
        # Pinned clock: with a live one the elapsed time is 60.0001s by the time
        # the comparison runs, so the boundary case could never be tested.
        now = 1000.0
        session.last_activity = now - 60

        with patch("session.time.time", return_value=now):
            result = session.get_connection()

        client.noop.assert_called_once()
        client.shutdown.assert_not_called()
        assert result is client


class TestProbe:
    """AC3: recent connections are probed; a transport probe failure recovers silently."""

    def test_recent_connection_is_probed_and_reused(self):
        session = AccountSession("test")
        client = Mock(spec=IMAPClient)
        session.connection = client
        session.last_activity = time.time() - 5

        result = session.get_connection()

        client.noop.assert_called_once()
        assert result is client

    def test_transport_probe_failure_is_recovered_silently(self):
        session = AccountSession("test")
        old = Mock(spec=IMAPClient)
        old.noop.side_effect = TimeoutError("timed out")
        session.connection = old
        session.last_activity = time.time() - 5
        new = Mock(spec=IMAPClient)

        with patch("session._create_connection", return_value=new):
            result = session.get_connection()

        old.shutdown.assert_called_once()
        assert result is new

    def test_non_transport_probe_error_does_not_discard(self):
        session = AccountSession("test")
        client = Mock(spec=IMAPClient)
        client.noop.side_effect = IMAPClientError("command rejected")
        session.connection = client
        session.last_activity = time.time() - 5

        with pytest.raises(IMAPClientError):
            session.get_connection()

        client.shutdown.assert_not_called()
        assert session.connection is client


class TestDeadSocketIsCheap:
    """AC4: nothing is sent to a socket already believed dead."""

    def test_no_noop_and_no_logout_reach_a_dead_connection(self, connected_to_silent):
        server, build = connected_to_silent
        session = AccountSession("test")
        session.connection = build()
        session.last_activity = time.time() - 61
        server.commands.clear()

        with patch("session._create_connection", side_effect=lambda _account: build()):
            started = time.monotonic()
            session.get_connection()
            elapsed = time.monotonic() - started

        assert not server.received("NOOP"), f"NOOP was sent: {server.commands}"
        assert not server.received("LOGOUT"), f"LOGOUT was sent: {server.commands}"
        assert elapsed < 1.0, f"took {elapsed:.2f}s against a 3s socket timeout"


class TestLeaseSerialisation:
    """AC5a/AC5b/AC6: one operation at a time, and failures do not cross callers."""

    def test_two_healthy_callers_do_not_overlap(self):
        session = AccountSession("test")
        created = []

        def factory(_account):
            client = Mock(spec=IMAPClient)
            created.append(client)
            return client

        barrier = threading.Barrier(2)
        intervals = []
        lock = threading.Lock()

        def worker():
            barrier.wait(timeout=5)
            with session.connection_ctx():
                start = time.monotonic()
                time.sleep(0.05)
                with lock:
                    intervals.append((start, time.monotonic()))

        with patch("session._create_connection", side_effect=factory):
            threads = [threading.Thread(target=worker) for _ in range(2)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=10)

        assert len(created) == 1, "the connection factory ran more than once"
        first, second = sorted(intervals)
        assert first[1] <= second[0], f"operations overlapped: {intervals}"

    def test_a_failing_caller_discards_only_its_own_connection(self):
        session = AccountSession("test")
        created = []

        def factory(_account):
            client = Mock(spec=IMAPClient)
            created.append(client)
            return client

        with patch("session._create_connection", side_effect=factory):
            with pytest.raises(ConnectionFailure):
                with session.connection_ctx():
                    raise TimeoutError("died mid-command")
            with session.connection_ctx() as second:
                pass

        assert len(created) == 2, "the replacement connection was not created"
        assert second is created[1]
        assert second is not created[0]

    def test_get_folders_runs_inside_the_lease(self):
        session = AccountSession("test")
        client = Mock(spec=IMAPClient)
        client.list_folders.side_effect = TimeoutError("died")

        with patch("session._create_connection", return_value=client):
            with pytest.raises(ConnectionFailure):
                session.get_folders()

        client.shutdown.assert_called_once()
        assert session.connection is None

    def test_cached_folders_need_no_connection(self):
        session = AccountSession("test")
        session.folder_cache = FolderCache(folders=[{"name": "INBOX", "flags": []}], fetched_at=1000.0)

        with patch("session._create_connection", side_effect=AssertionError("must not connect")):
            assert session.get_folders()[0]["name"] == "INBOX"


class TestFreshConnectionIsNotBornStale:
    """AC10: last_activity is stamped after the slow work, not before."""

    def test_slow_probe_and_login_do_not_age_the_replacement(self):
        session = AccountSession("test")
        old = Mock(spec=IMAPClient)
        old.noop.side_effect = TimeoutError("timed out")
        session.connection = old

        clock = {"now": 1000.0}

        def slow_create(_account):
            clock["now"] += 31.0  # 30s probe + 1s login
            return Mock(spec=IMAPClient)

        with patch("session.time.time", lambda: clock["now"]), patch("session._create_connection", side_effect=slow_create):
            session.last_activity = clock["now"] - 5
            first = session.get_connection()
            clock["now"] += 5
            second = session.get_connection()

        assert second is first, "the replacement was discarded as stale after only 5s"


class TestLoginRejectionCleanup:
    """AC11: a rejected login does not leak its client."""

    def test_login_failure_shuts_down_the_client(self):
        client = Mock(spec=IMAPClient)
        client.login.side_effect = LoginError("Invalid credentials")

        with (
            patch("session.IMAPClient", return_value=client),
            patch("imap_client.get_credentials", return_value=("host", "993", "u", "p")),
        ):
            with pytest.raises(ConnectionFailure) as exc:
                _create_connection("test")

        client.shutdown.assert_called_once()
        assert isinstance(exc.value.__cause__, LoginError)
        assert exc.value.stage == "connect"

    def test_a_raising_shutdown_does_not_mask_the_login_error(self):
        client = Mock(spec=IMAPClient)
        client.login.side_effect = LoginError("Invalid credentials")
        client.shutdown.side_effect = OSError("socket already gone")

        with (
            patch("session.IMAPClient", return_value=client),
            patch("imap_client.get_credentials", return_value=("host", "993", "u", "p")),
        ):
            with pytest.raises(ConnectionFailure) as exc:
                _create_connection("test")

        assert isinstance(exc.value.__cause__, LoginError)


class TestRetryOnlyWhereItIsSafe:
    """Cut 2 deferred this: a context manager cannot re-run its `with` body, so
    an operation that wants a retry hands its body over as a callable."""

    def test_a_read_operation_is_retried_once_on_a_fresh_connection(self):
        session = AccountSession("test")
        created = []

        def factory(_account):
            client = Mock(spec=IMAPClient)
            created.append(client)
            return client

        attempts = []

        def operation(conn):
            attempts.append(conn)
            if len(attempts) == 1:
                raise TimeoutError("died mid-command")
            return "second attempt result"

        with patch("session._create_connection", side_effect=factory):
            assert session.run_op(operation, retry=True) == "second attempt result"

        assert len(attempts) == 2, "the operation must run again"
        assert attempts[0] is not attempts[1], "the retry must use a fresh connection"
        assert len(created) == 2

    def test_without_retry_the_operation_runs_once_and_the_failure_propagates(self):
        session = AccountSession("test")
        attempts = []

        def operation(conn):
            attempts.append(conn)
            raise TimeoutError("died mid-command")

        with patch("session._create_connection", return_value=Mock(spec=IMAPClient)):
            with pytest.raises(ConnectionFailure):
                session.run_op(operation)

        assert len(attempts) == 1, "replaying a write would duplicate it; default must not retry"

    def test_a_second_failure_propagates(self):
        session = AccountSession("test")
        attempts = []

        def operation(conn):
            attempts.append(conn)
            raise TimeoutError("still dead")

        with patch("session._create_connection", side_effect=lambda _a: Mock(spec=IMAPClient)):
            with pytest.raises(ConnectionFailure):
                session.run_op(operation, retry=True)

        assert len(attempts) == 2, "one retry, not a loop"

    def test_a_non_transport_error_is_not_retried(self):
        """A rejected command means the server answered; running it again just
        gets the same rejection."""
        session = AccountSession("test")
        attempts = []

        def operation(conn):
            attempts.append(conn)
            raise IMAPClientError("command rejected")

        with patch("session._create_connection", return_value=Mock(spec=IMAPClient)):
            with pytest.raises(IMAPClientError):
                session.run_op(operation, retry=True)

        assert len(attempts) == 1

    def test_the_writing_paths_do_not_opt_in(self):
        """create, replace and flag must never replay: an appended message would
        be duplicated, and an expunge cannot be undone."""
        import ast
        from pathlib import Path

        source = (Path(__file__).resolve().parent.parent.parent / "imap-slim" / "imap_client.py").read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name in {"create_draft", "modify_draft", "modify_flags"}:
                body = ast.get_source_segment(source, node) or ""
                assert "run_op" not in body, f"{node.name} must not use the retrying runner"
