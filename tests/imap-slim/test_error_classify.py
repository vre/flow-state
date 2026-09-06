"""Tests for connection-failure classification (cut 2, AC7-AC9, AC12).

The predicate answers "should this be discarded"; the boundary answers "what do
we tell the caller". They are deliberately different questions: a rejected login
is a connection-stage failure that must NOT discard, because nothing connected.
"""

import errno

import pytest
from imap_client import ConnectionFailure, IMAPError, is_transport_failure
from imapclient.exceptions import IMAPClientAbortError, IMAPClientError, LoginError
from render import classify_connection_error


class TestTransportPredicate:
    """AC7: what counts as the transport dying."""

    @pytest.mark.parametrize(
        "exc",
        [
            TimeoutError("timed out"),
            ConnectionResetError("reset by peer"),
            BrokenPipeError("broken pipe"),
            IMAPClientAbortError("connection aborted"),
            OSError(errno.ENOTCONN, "not connected"),
            OSError(errno.EHOSTUNREACH, "no route to host"),
        ],
    )
    def test_transport_shaped_exceptions(self, exc):
        assert is_transport_failure(exc, stage="command")

    @pytest.mark.parametrize(
        "exc",
        [
            IMAPClientError("command rejected"),
            LoginError("Invalid credentials"),
            PermissionError(errno.EACCES, "permission denied"),
            OSError(errno.ENOSPC, "no space left on device"),
            ValueError("not a connection problem at all"),
        ],
    )
    def test_non_transport_exceptions(self, exc):
        assert not is_transport_failure(exc, stage="command")

    def test_walks_the_cause_chain(self):
        """IMAPError is a plain Exception, so the outer type tells us nothing."""
        try:
            try:
                raise TimeoutError("timed out")
            except TimeoutError as inner:
                raise IMAPError("Cannot open folder 'INBOX'") from inner
        except IMAPError as wrapped:
            assert is_transport_failure(wrapped, stage="command")

    def test_walks_the_context_chain(self):
        try:
            try:
                raise ConnectionResetError("reset")
            except ConnectionResetError:
                raise IMAPError("wrapped without from")  # noqa: B904 - the point is __context__, not __cause__
        except IMAPError as wrapped:
            assert is_transport_failure(wrapped, stage="command")

    def test_a_plain_wrapper_over_nothing_transport_is_not_transport(self):
        try:
            try:
                raise ValueError("bad input")
            except ValueError as inner:
                raise IMAPError("Cannot parse") from inner
        except IMAPError as wrapped:
            assert not is_transport_failure(wrapped, stage="command")


class TestBoundaryClassification:
    """AC8/AC9/AC12: what the caller is told."""

    def _connection_failure(self, cause, stage="command", elapsed=1.5):
        try:
            raise cause
        except type(cause) as inner:
            failure = ConnectionFailure(stage, elapsed)
            failure.__cause__ = inner
            return failure

    def test_quota_rejection_is_named(self):
        failure = self._connection_failure(LoginError("Maximum number of connections exceeded"), stage="connect")
        message = classify_connection_error(failure)
        assert message is not None
        assert "connection limit" in message.lower()
        assert "thunderbird" in message.lower() or "mail client" in message.lower() or "session" in message.lower()

    def test_too_many_connections_variant(self):
        failure = self._connection_failure(LoginError("NO [LIMIT] Too many connections"), stage="connect")
        assert "connection limit" in classify_connection_error(failure).lower()

    def test_maximum_login_attempts_is_not_a_quota_message(self):
        failure = self._connection_failure(LoginError("Maximum login attempts exceeded"), stage="connect")
        message = classify_connection_error(failure)
        assert message is not None
        assert "connection limit" not in message.lower()
        assert "rejected" in message.lower()

    def test_login_rejection_does_not_assert_bad_credentials(self):
        failure = self._connection_failure(LoginError("Invalid credentials"), stage="connect")
        message = classify_connection_error(failure)
        assert "rejected" in message.lower()
        assert "Invalid credentials" in message

    def test_transport_loss_is_named(self):
        failure = self._connection_failure(TimeoutError("timed out"), stage="command", elapsed=30.0)
        message = classify_connection_error(failure)
        assert "connection" in message.lower() and "lost" in message.lower()

    def test_stage_and_elapsed_are_read_off_the_exception(self):
        connect = self._connection_failure(TimeoutError("timed out"), stage="connect", elapsed=30.0)
        command = self._connection_failure(TimeoutError("timed out"), stage="command", elapsed=2.5)
        assert "connect" in classify_connection_error(connect)
        assert "30" in classify_connection_error(connect)
        assert "command" in classify_connection_error(command)
        assert "2.5" in classify_connection_error(command)

    def test_wrapped_imap_error_still_classifies(self):
        """except IMAPError precedes except Exception, so this must classify there too."""
        try:
            try:
                raise TimeoutError("timed out")
            except TimeoutError as inner:
                raise IMAPError("Cannot open folder 'INBOX'") from inner
        except IMAPError as wrapped:
            assert classify_connection_error(wrapped) is not None

    def test_unrelated_errors_are_not_classified(self):
        assert classify_connection_error(ValueError("nope")) is None
        assert classify_connection_error(IMAPError("Message 5 not found in 'INBOX'")) is None

    def test_not_configured_is_left_to_the_setup_guide(self):
        assert classify_connection_error(IMAPError("IMAP credentials not configured")) is None
