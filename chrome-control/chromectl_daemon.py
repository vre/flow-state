"""Chromectl daemon lifecycle: start if needed, stop when done.

Usage as context manager:

    async with daemon_context(socket_path) as sock:
        # daemon is running, sock == socket_path
        ...
    # daemon stopped (if we started it)
"""

import asyncio
import json
import os
import subprocess
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMECTL = os.path.join(SCRIPT_DIR, "chromectl.py")

STARTUP_TIMEOUT = 15  # seconds to wait for socket


def _default_socket_path() -> str:
    return f"/tmp/chromectl-{os.getuid()}.sock"


_STREAM_LIMIT = 16 * 1024 * 1024  # 16MB — large eval results (e.g. full DOM snapshots)


def _is_healthy_response(resp: dict) -> bool:
    """Return True when a daemon response indicates a usable connection."""
    return "error" not in resp


async def send_command(req: dict, socket_path: str | None = None) -> dict:
    """Send one JSON command to the chromectl daemon."""
    socket_path = socket_path or _default_socket_path()
    reader, writer = await asyncio.open_unix_connection(socket_path, limit=_STREAM_LIMIT)
    try:
        writer.write(json.dumps(req).encode() + b"\n")
        await writer.drain()
        response = await asyncio.wait_for(reader.readline(), timeout=60)
    finally:
        writer.close()
        await writer.wait_closed()
    return json.loads(response.decode())


async def _send_quit(socket_path: str) -> None:
    """Send quit command to daemon."""
    try:
        await asyncio.wait_for(send_command({"cmd": "quit"}, socket_path=socket_path), timeout=5)
    except Exception:
        pass


async def _wait_for_socket(socket_path: str, timeout: float) -> None:
    """Poll until Unix socket appears."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if os.path.exists(socket_path):
            # Verify it accepts connections
            try:
                resp = await asyncio.wait_for(send_command({"cmd": "list"}, socket_path=socket_path), timeout=10)
                if _is_healthy_response(resp):
                    return
            except Exception:
                pass
        await asyncio.sleep(0.3)
    raise RuntimeError(
        f"Daemon did not start within {timeout}s. "
        "Check that Chrome is running with remote debugging enabled "
        "(chrome://inspect/#remote-debugging)."
    )


async def ensure_daemon_running(socket_path: str | None = None, timeout: float = STARTUP_TIMEOUT) -> str:
    """Ensure a daemon is running at socket_path. Starts one if needed.

    Returns the socket path. Idempotent — safe to call multiple times.
    Useful for mid-run recovery when daemon process dies.

    The started process is not tracked by this caller (orphaned); the caller is
    expected to use this for recovery within a daemon_context that didn't start
    the original daemon, OR to live with a leftover process until manual cleanup.
    """
    socket_path = socket_path or _default_socket_path()

    if os.path.exists(socket_path):
        try:
            resp = await asyncio.wait_for(send_command({"cmd": "list"}, socket_path=socket_path), timeout=5)
            if _is_healthy_response(resp):
                return socket_path
        except Exception:
            pass

        try:
            os.unlink(socket_path)
        except OSError:
            pass

    if not os.path.exists(CHROMECTL):
        raise RuntimeError(f"chromectl not found at {CHROMECTL}")

    subprocess.Popen(
        ["uv", "run", CHROMECTL, "start"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    await _wait_for_socket(socket_path, timeout)
    return socket_path


class daemon_context:
    """Async context manager: ensures chromectl daemon is running.

    Starts daemon if socket doesn't exist, stops it on exit if we started it.
    """

    def __init__(self, socket_path: str | None = None):
        self.socket_path = socket_path or _default_socket_path()
        self._proc: subprocess.Popen | None = None
        self._we_started = False

    async def __aenter__(self) -> str:
        if os.path.exists(self.socket_path):
            # Daemon already running — verify it responds
            try:
                resp = await asyncio.wait_for(send_command({"cmd": "list"}, socket_path=self.socket_path), timeout=5)
                if _is_healthy_response(resp):
                    return self.socket_path
            except Exception:
                pass

            # Stale socket or dead daemon — remove and start fresh
            try:
                os.unlink(self.socket_path)
            except OSError:
                pass

        if not os.path.exists(CHROMECTL):
            print(
                f"Error: chromectl not found at {CHROMECTL}",
                file=sys.stderr,
            )
            sys.exit(1)

        self._proc = subprocess.Popen(
            ["uv", "run", CHROMECTL, "start"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self._we_started = True

        await _wait_for_socket(self.socket_path, STARTUP_TIMEOUT)
        return self.socket_path

    async def __aexit__(self, exc_type, exc, tb):
        if self._we_started and os.path.exists(self.socket_path):
            await _send_quit(self.socket_path)
            if self._proc:
                try:
                    await asyncio.wait_for(asyncio.to_thread(self._proc.wait), timeout=5)
                except (asyncio.TimeoutError, subprocess.TimeoutExpired):
                    self._proc.kill()
