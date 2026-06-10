from __future__ import annotations

import asyncio

import firefoxctl_daemon


def test_healthy_response_rejects_error_payload():
    assert firefoxctl_daemon._is_healthy_response({"targets": []}) is True
    assert firefoxctl_daemon._is_healthy_response({"error": "boom"}) is False


def test_daemon_context_restarts_on_error_response(monkeypatch, tmp_path):
    socket_path = tmp_path / "firefoxctl.sock"
    socket_path.write_text("")

    calls = {"unlink": 0, "popen": 0, "wait": 0}

    async def fake_send_command(req, socket_path=None):
        return {"error": "ConnectionResetError: Cannot write to closing transport"}

    async def fake_wait_for_socket(path, timeout, port):
        calls["wait"] += 1

    class FakeProc:
        pass

    def fake_exists(path):
        return path == str(socket_path) or path == firefoxctl_daemon.FIREFOXCTL

    def fake_unlink(path):
        calls["unlink"] += 1

    def fake_popen(*args, **kwargs):
        calls["popen"] += 1
        return FakeProc()

    monkeypatch.setattr(firefoxctl_daemon, "send_command", fake_send_command)
    monkeypatch.setattr(firefoxctl_daemon, "_wait_for_socket", fake_wait_for_socket)
    monkeypatch.setattr(firefoxctl_daemon.os.path, "exists", fake_exists)
    monkeypatch.setattr(firefoxctl_daemon.os, "unlink", fake_unlink)
    monkeypatch.setattr(firefoxctl_daemon.subprocess, "Popen", fake_popen)

    ctx = firefoxctl_daemon.daemon_context(str(socket_path))
    result = asyncio.run(ctx.__aenter__())

    assert result == str(socket_path)
    assert calls == {"unlink": 1, "popen": 1, "wait": 1}
