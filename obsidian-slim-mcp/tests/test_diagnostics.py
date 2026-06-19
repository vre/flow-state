"""Tests for connection/setup diagnostics: _is_endpoint_error and explain_error."""

import httpx
import obsidian_client as api
import pytest

NO_KEY = RuntimeError("OBSIDIAN_API_KEY not set. Export it: export OBSIDIAN_API_KEY=your-key-here")


def _status_error(code: int, url: str = "http://127.0.0.1:27123/vault/x.md") -> httpx.HTTPStatusError:
    request = httpx.Request("GET", url)
    response = httpx.Response(code, request=request)
    return httpx.HTTPStatusError(f"HTTP {code}", request=request, response=response)


# --- _is_endpoint_error: endpoint-wide vs per-file ---


def test_missing_key_is_endpoint_error():
    """Missing API key affects every request, so it must propagate."""
    assert api._is_endpoint_error(NO_KEY) is True


def test_401_is_endpoint_error():
    """A 401 is endpoint-wide (auth), not a per-file problem."""
    assert api._is_endpoint_error(_status_error(401)) is True


def test_403_is_endpoint_error():
    """A 403 is endpoint-wide (auth), not a per-file problem."""
    assert api._is_endpoint_error(_status_error(403)) is True


def test_404_is_not_endpoint_error():
    """A missing file must stay a per-path error, not poison a whole batch."""
    assert api._is_endpoint_error(_status_error(404)) is False


def test_connect_error_is_endpoint_error():
    """A connection failure means the whole endpoint is unreachable."""
    assert api._is_endpoint_error(httpx.ConnectError("refused")) is True


def test_value_error_is_not_endpoint_error():
    """A payload/validation error is not an endpoint problem."""
    assert api._is_endpoint_error(ValueError("bad payload")) is False


# --- explain_error: each state maps to its actionable message ---


@pytest.mark.asyncio
async def test_no_key_reachable(monkeypatch):
    """No key but server up: tell the user to just set the key."""
    monkeypatch.setenv("OBSIDIAN_API_URL", "http://127.0.0.1:27123")

    async def _reachable():
        return True

    monkeypatch.setattr(api, "_server_reachable", _reachable)
    msg = await api.explain_error(NO_KEY)
    assert "reachable at http://127.0.0.1:27123" in msg
    assert "Obsidian setup for this MCP" in msg  # SETUP_GUIDE appended


@pytest.mark.asyncio
async def test_no_key_unreachable(monkeypatch):
    """No key and no server: report both problems."""
    monkeypatch.setenv("OBSIDIAN_API_URL", "http://127.0.0.1:27123")

    async def _reachable():
        return False

    monkeypatch.setattr(api, "_server_reachable", _reachable)
    msg = await api.explain_error(NO_KEY)
    assert "nothing is answering" in msg
    assert "OBSIDIAN_API_URL" in msg


@pytest.mark.asyncio
async def test_unauthed_names_both_causes(monkeypatch):
    """401 must name both causes (wrong key vs wrong vault) and the pair rule."""
    monkeypatch.setenv("OBSIDIAN_API_URL", "http://127.0.0.1:27123")
    msg = await api.explain_error(_status_error(401))
    assert "401" in msg
    assert "DIFFERENT vault" in msg
    assert "pair" in msg


@pytest.mark.asyncio
async def test_no_server_on_http_port(monkeypatch):
    """Connect failure on the HTTP port flags the disabled-HTTP-port trap."""
    monkeypatch.setenv("OBSIDIAN_API_URL", "http://127.0.0.1:27123")
    msg = await api.explain_error(httpx.ConnectError("Connection refused"))
    assert "Nothing is answering" in msg
    assert "DISABLED" in msg


@pytest.mark.asyncio
async def test_http_to_https_port(monkeypatch):
    """HTTP pointed at 27124 should explain the HTTPS-port mismatch."""
    monkeypatch.setenv("OBSIDIAN_API_URL", "http://127.0.0.1:27124")
    msg = await api.explain_error(httpx.ConnectError("boom"))
    assert "HTTPS" in msg
    assert "27124" in msg


@pytest.mark.asyncio
async def test_https_cert_error(monkeypatch):
    """An https transport error points at the cert / HTTP-fallback fix."""
    monkeypatch.setenv("OBSIDIAN_API_URL", "https://127.0.0.1:27124")
    msg = await api.explain_error(httpx.ConnectError("SSL: CERTIFICATE_VERIFY_FAILED"))
    assert "certificate" in msg.lower()


@pytest.mark.asyncio
async def test_operation_error_passes_through(monkeypatch):
    """A 404 is a normal operation error — explain_error declines (returns None)."""
    monkeypatch.setenv("OBSIDIAN_API_URL", "http://127.0.0.1:27123")
    assert await api.explain_error(_status_error(404)) is None
