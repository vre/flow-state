"""navigate must survive Firefox replacing the browsing context — without guessing.

A navigation can succeed while destroying the context it was given: BiDi reports
"Browsing context got discarded" and the page loads under a new id. Treating that as
a failure loses a page that loaded fine. Adopting the wrong new context is worse: it
is how a scheduled job ended up driving a tab a human was reading.

The known cause is a container switch (Firefox Multi-Account Containers and the like):
a context cannot change userContext in place, so the browser builds a new one. That
matters for the tests below — the replacement lands at the *requested* address, in the
*same window*, so both are checkable.
"""

from __future__ import annotations

import asyncio
import time

import firefoxctl
import pytest

TARGET = "https://example.com/feed.json"
DISCARDED = "browsingContext.navigate: unknown error — Error: Browsing context got discarded"
WIN = "window-1"
OTHER_WIN = "window-2"


class FakeConn:
    """Minimal BiDiConnection stand-in: one scripted reply for navigate."""

    def __init__(self, navigate_result=None, navigate_error=None):
        self._result = navigate_result
        self._error = navigate_error

    async def send(self, method, params=None):
        if self._error is not None:
            raise self._error
        return self._result


def _tab(context, url, window=WIN):
    return {"context": context, "url": url, "clientWindow": window}


BLANK = _tab("old", "about:blank")


def _patch_list(monkeypatch, sequence):
    """Make cmd_list return each snapshot in turn, repeating the last."""
    calls = {"n": 0}

    async def fake_cmd_list(conn):
        i = min(calls["n"], len(sequence) - 1)
        calls["n"] += 1
        return sequence[i]

    monkeypatch.setattr(firefoxctl, "cmd_list", fake_cmd_list)


def _discarding_conn():
    return FakeConn(navigate_error=firefoxctl.BiDiError(DISCARDED))


def _run(conn, **kwargs):
    return asyncio.run(firefoxctl.cmd_navigate(conn, "old", TARGET, **kwargs))


# --- adoption ---


def test_replacement_at_the_target_url_in_our_window_is_adopted(monkeypatch):
    _patch_list(monkeypatch, [[BLANK], [BLANK, _tab("new", TARGET)]])
    result = _run(_discarding_conn())
    assert result["context"] == "new"
    assert result["context_swapped"] is True
    assert result["url"] == TARGET


def test_a_bare_origin_matches_its_root_path(monkeypatch):
    """The one normalisation Firefox actually performs: "" and "/" are one path."""
    root = "https://example.com"
    _patch_list(monkeypatch, [[BLANK], [BLANK, _tab("new", root + "/")]])
    result = asyncio.run(firefoxctl.cmd_navigate(_discarding_conn(), "old", root))
    assert result["context"] == "new"


def test_a_different_path_spelling_is_not_the_same_resource(monkeypatch):
    """`/feed.json/` may be a different server resource; do not assume otherwise."""
    _patch_list(monkeypatch, [[BLANK], [BLANK, _tab("new", TARGET + "/")]])
    with pytest.raises(firefoxctl.BiDiError):
        _run(_discarding_conn(), swap_timeout=0.6)


def test_a_fragment_is_part_of_the_address(monkeypatch):
    _patch_list(monkeypatch, [[BLANK], [BLANK, _tab("new", TARGET + "#other")]])
    with pytest.raises(firefoxctl.BiDiError):
        _run(_discarding_conn(), swap_timeout=0.6)


def test_the_real_replacement_wins_over_a_tab_the_user_opened_meanwhile(monkeypatch):
    """The race that matters: an unrelated new tab must not displace the replacement."""
    _patch_list(
        monkeypatch,
        [
            [BLANK],
            [BLANK, _tab("users-tab", "https://news.example.org/"), _tab("new", TARGET)],
        ],
    )
    assert _run(_discarding_conn())["context"] == "new"


# --- refusal ---


def test_a_new_context_in_another_window_is_not_our_replacement(monkeypatch):
    """The swap preserves clientWindow, so a hit elsewhere is somebody else's tab."""
    _patch_list(
        monkeypatch,
        [[BLANK], [BLANK, _tab("elsewhere", TARGET, window=OTHER_WIN)]],
    )
    with pytest.raises(firefoxctl.BiDiError):
        _run(_discarding_conn(), swap_timeout=0.6)


def test_a_redirect_is_refused(monkeypatch):
    """A container swap re-issues the same request; a different address is not it."""
    _patch_list(
        monkeypatch,
        [[BLANK], [BLANK, _tab("new", "https://example.com/login?next=/feed")]],
    )
    with pytest.raises(firefoxctl.BiDiError):
        _run(_discarding_conn(), swap_timeout=0.6)


def test_a_user_tab_elsewhere_on_the_target_origin_is_refused(monkeypatch):
    _patch_list(
        monkeypatch,
        [[BLANK], [BLANK, _tab("users-tab", "https://example.com/some/page")]],
    )
    with pytest.raises(firefoxctl.BiDiError):
        _run(_discarding_conn(), swap_timeout=0.6)


def test_two_candidates_at_the_target_refuse_rather_than_guess(monkeypatch):
    both = [BLANK, _tab("a", TARGET), _tab("b", TARGET)]
    _patch_list(monkeypatch, [[BLANK], both])
    with pytest.raises(firefoxctl.BiDiError):
        _run(_discarding_conn(), swap_timeout=0.6)


def test_a_genuine_failure_is_not_converted_into_success_by_a_stray_tab(monkeypatch):
    """If the context really was closed, an unrelated new tab must not stand in."""
    _patch_list(
        monkeypatch,
        [[BLANK], [BLANK, _tab("users-tab", "https://news.example.org/")]],
    )
    with pytest.raises(firefoxctl.BiDiError):
        _run(_discarding_conn(), swap_timeout=0.6)


def test_a_context_that_existed_before_is_never_adopted(monkeypatch):
    pre_existing = [BLANK, _tab("users-own-tab", TARGET)]
    _patch_list(monkeypatch, [pre_existing, pre_existing])
    with pytest.raises(firefoxctl.BiDiError):
        _run(_discarding_conn(), swap_timeout=0.6)


def test_a_blank_new_tab_is_not_mistaken_for_the_replacement(monkeypatch):
    _patch_list(monkeypatch, [[BLANK], [BLANK, _tab("blank", "about:newtab")]])
    with pytest.raises(firefoxctl.BiDiError):
        _run(_discarding_conn(), swap_timeout=0.6)


def test_known_residual_risk_a_user_tab_at_the_exact_target_in_our_window(monkeypatch):
    """The one hole left, deliberately accepted.

    A context that is new, at the exact requested address, and in the same window as
    the one we navigated is indistinguishable from the real replacement — BiDi exposes
    no replacement relation. Closing it needs a window nothing else can open tabs in.
    Accepted because the user would have to open that precise URL, in that window,
    inside the wait window.

    If this ever needs to be closed, change the design; do not loosen the assertion.
    """
    _patch_list(monkeypatch, [[BLANK], [BLANK, _tab("users-tab", TARGET)]])
    assert _run(_discarding_conn())["context"] == "users-tab"


# --- degradation and bounds ---


def test_an_absent_window_refuses_rather_than_comparing_two_absences(monkeypatch):
    """Two missing ids are not a match — the browser may have several windows.

    A Firefox that does not report clientWindow leaves the window unknowable, so
    recovery is declined and the discard propagates: the behaviour from before this
    recovery existed, never something silently wrong.
    """
    blank = {"context": "old", "url": "about:blank"}
    _patch_list(monkeypatch, [[blank], [blank, {"context": "new", "url": TARGET}]])
    with pytest.raises(firefoxctl.BiDiError):
        _run(_discarding_conn(), swap_timeout=0.6)


def test_a_candidate_with_a_window_we_cannot_match_is_refused(monkeypatch):
    """Our window unknown but the candidate has one: that is a mismatch, not a pass."""
    blank = {"context": "old", "url": "about:blank"}
    _patch_list(monkeypatch, [[blank], [blank, _tab("new", TARGET)]])
    with pytest.raises(firefoxctl.BiDiError):
        _run(_discarding_conn(), swap_timeout=0.6)


def test_without_a_swap_the_original_context_is_kept(monkeypatch):
    conn = FakeConn(navigate_result={"navigation": "nav-1", "url": TARGET})
    _patch_list(monkeypatch, [[BLANK]])
    result = _run(conn)
    assert result["context"] == "old"
    assert "context_swapped" not in result
    assert result["navigation"] == "nav-1"


def test_a_real_navigation_failure_still_raises(monkeypatch):
    conn = FakeConn(navigate_error=firefoxctl.BiDiError("browsingContext.navigate: unknown error — Error: NS_ERROR_UNKNOWN_HOST"))
    _patch_list(monkeypatch, [[BLANK]])
    with pytest.raises(firefoxctl.BiDiError, match="NS_ERROR_UNKNOWN_HOST"):
        _run(conn)


def test_a_non_positive_poll_is_rejected():
    async def go():
        return await firefoxctl._await_swapped_context(None, set(), TARGET, WIN, 1.0, poll=0)

    with pytest.raises(ValueError):
        asyncio.run(go())


def test_a_non_positive_timeout_is_rejected():
    async def go():
        return await firefoxctl._await_swapped_context(None, set(), TARGET, WIN, 0.0)

    with pytest.raises(ValueError):
        asyncio.run(go())


def test_a_stalled_context_list_gives_up_within_the_stated_timeout(monkeypatch):
    """An unresponsive getTree must not extend the wait past what the caller asked."""

    async def never_returns(conn):
        await asyncio.sleep(30)

    monkeypatch.setattr(firefoxctl, "cmd_list", never_returns)

    async def go():
        return await firefoxctl._await_swapped_context(None, set(), TARGET, WIN, 0.3)

    started = time.monotonic()
    assert asyncio.run(go()) is None
    assert time.monotonic() - started < 1.0


# --- contracts the recovery depends on ---


def test_cmd_list_reports_the_window_each_context_belongs_to():
    """_await_swapped_context filters on this field; cmd_list must carry it."""

    class TreeConn:
        async def send(self, method, params=None):
            return {"contexts": [{"context": "c1", "url": TARGET, "clientWindow": WIN}]}

    tabs = asyncio.run(firefoxctl.cmd_list(TreeConn()))
    assert tabs == [{"context": "c1", "url": TARGET, "clientWindow": WIN}]


def test_a_cancelled_send_does_not_leak_its_pending_future():
    """wait_for cancels send() on timeout; the reply slot must not accumulate."""

    class FakeWS:
        async def send_json(self, msg):
            return None

    async def go():
        conn = firefoxctl.BiDiConnection("localhost", 9223)
        conn._ws = FakeWS()
        task = asyncio.create_task(conn.send("browsingContext.getTree", {}))
        await asyncio.sleep(0)
        assert conn._pending, "send() should have registered a pending reply"
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        return conn._pending

    assert asyncio.run(go()) == {}


def test_a_stalled_preflight_does_not_hang_navigate(monkeypatch):
    """The snapshot is an enhancement, not a precondition — it must not add a hang."""

    async def never_returns(conn):
        await asyncio.sleep(30)

    monkeypatch.setattr(firefoxctl, "cmd_list", never_returns)
    started = time.monotonic()
    with pytest.raises(firefoxctl.BiDiError):
        _run(_discarding_conn(), swap_timeout=0.3)
    assert time.monotonic() - started < 2.0


def test_a_send_cancelled_while_writing_does_not_leak_its_future():
    """Cancellation can land inside the socket write, before the reply is awaited."""

    class BlockingWS:
        async def send_json(self, msg):
            await asyncio.sleep(30)

    async def go():
        conn = firefoxctl.BiDiConnection("localhost", 9223)
        conn._ws = BlockingWS()
        task = asyncio.create_task(conn.send("browsingContext.getTree", {}))
        await asyncio.sleep(0)
        assert conn._pending, "send() should have registered a pending reply"
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        return conn._pending

    assert asyncio.run(go()) == {}


# --- open ---
#
# `open` creates a tab and navigates it, so its navigation is always a *first*
# navigation — exactly the one a container assignment replaces. It must follow the
# swap for the same reason `navigate` does, and hand back a context that is alive.


class OpenConn:
    """Scripted BiDi: create returns a fixed id, navigate replies or raises."""

    def __init__(self, navigate_error=None):
        self._navigate_error = navigate_error
        self.navigated = []

    async def send(self, method, params=None):
        if method == "browsingContext.create":
            return {"context": "old"}
        if method == "browsingContext.navigate":
            self.navigated.append(params)
            if self._navigate_error is not None:
                raise self._navigate_error
            return {"navigation": "nav-1", "url": params["url"]}
        raise AssertionError(f"unexpected method {method}")


def test_open_follows_a_swap_and_returns_the_live_context(monkeypatch):
    _patch_list(monkeypatch, [[BLANK], [BLANK, _tab("new", TARGET)]])
    conn = OpenConn(navigate_error=firefoxctl.BiDiError(DISCARDED))
    result = asyncio.run(firefoxctl.cmd_open(conn, TARGET))
    assert result["context"] == "new"
    assert result["context_swapped"] is True


def test_open_without_a_swap_returns_the_tab_it_created(monkeypatch):
    _patch_list(monkeypatch, [[BLANK]])
    conn = OpenConn()
    result = asyncio.run(firefoxctl.cmd_open(conn, TARGET))
    assert result["context"] == "old"
    assert result["url"] == TARGET
    assert "context_swapped" not in result
    # Pin what was actually asked of the browser, not just the shape of the reply.
    assert conn.navigated == [{"context": "old", "url": TARGET, "wait": "complete"}]


def test_open_still_raises_on_a_genuine_navigation_failure(monkeypatch):
    _patch_list(monkeypatch, [[BLANK]])
    conn = OpenConn(navigate_error=firefoxctl.BiDiError("browsingContext.navigate: unknown error — Error: NS_ERROR_UNKNOWN_HOST"))
    with pytest.raises(firefoxctl.BiDiError, match="NS_ERROR_UNKNOWN_HOST"):
        asyncio.run(firefoxctl.cmd_open(conn, TARGET))


def test_open_with_no_url_does_not_navigate(monkeypatch):
    _patch_list(monkeypatch, [[BLANK]])
    conn = OpenConn()
    result = asyncio.run(firefoxctl.cmd_open(conn, ""))
    assert result["context"] == "old"
    assert conn.navigated == []
