"""Firefoxctl daemon lifecycle: start if needed, stop when done.

Usage as context manager:

    async with daemon_context(port=9223) as sock:
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
FIREFOXCTL = os.path.join(SCRIPT_DIR, "firefoxctl.py")

DEFAULT_PORT = 9222
STARTUP_TIMEOUT = 15


def _default_socket_path() -> str:
    return f"/tmp/firefoxctl-{os.getuid()}.sock"


_STREAM_LIMIT = 16 * 1024 * 1024


async def send_command(req: dict, socket_path: str | None = None) -> dict:
    """Send one JSON command to the firefoxctl daemon."""
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


async def _wait_for_socket(socket_path: str, timeout: float, port: int) -> None:
    """Poll until Unix socket appears and responds."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if os.path.exists(socket_path):
            try:
                await asyncio.wait_for(send_command({"cmd": "list"}, socket_path=socket_path), timeout=10)
                return
            except Exception:
                pass
        await asyncio.sleep(0.3)
    raise RuntimeError(
        f"Daemon did not start within {timeout}s. Check that Firefox is running with: firefox --remote-debugging-port {port}"
    )


async def ensure_daemon_running(
    socket_path: str | None = None,
    port: int = DEFAULT_PORT,
    timeout: float = STARTUP_TIMEOUT,
) -> str:
    """Ensure a daemon is running at socket_path. Starts one if needed.

    Returns the socket path. Idempotent — safe to call multiple times.
    """
    socket_path = socket_path or _default_socket_path()

    if os.path.exists(socket_path):
        try:
            await asyncio.wait_for(send_command({"cmd": "list"}, socket_path=socket_path), timeout=5)
            return socket_path
        except Exception:
            try:
                os.unlink(socket_path)
            except OSError:
                pass

    if not os.path.exists(FIREFOXCTL):
        raise RuntimeError(f"firefoxctl not found at {FIREFOXCTL}")

    subprocess.Popen(
        ["uv", "run", FIREFOXCTL, "--port", str(port), "start"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    await _wait_for_socket(socket_path, timeout, port)
    return socket_path


class daemon_context:
    """Async context manager: ensures firefoxctl daemon is running.

    Starts daemon if socket doesn't exist, stops it on exit if we started it.
    """

    def __init__(self, socket_path: str | None = None, port: int = DEFAULT_PORT):
        self.socket_path = socket_path or _default_socket_path()
        self.port = port
        self._proc: subprocess.Popen | None = None
        self._we_started = False

    async def __aenter__(self) -> str:
        if os.path.exists(self.socket_path):
            try:
                await asyncio.wait_for(send_command({"cmd": "list"}, socket_path=self.socket_path), timeout=5)
                return self.socket_path
            except Exception:
                try:
                    os.unlink(self.socket_path)
                except OSError:
                    pass

        if not os.path.exists(FIREFOXCTL):
            print(
                f"Error: firefoxctl not found at {FIREFOXCTL}",
                file=sys.stderr,
            )
            sys.exit(1)

        self._proc = subprocess.Popen(
            ["uv", "run", FIREFOXCTL, "--port", str(self.port), "start"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self._we_started = True

        await _wait_for_socket(self.socket_path, STARTUP_TIMEOUT, self.port)
        return self.socket_path

    async def __aexit__(self, exc_type, exc, tb):
        if self._we_started and os.path.exists(self.socket_path):
            await _send_quit(self.socket_path)
            if self._proc:
                try:
                    await asyncio.wait_for(asyncio.to_thread(self._proc.wait), timeout=5)
                except (asyncio.TimeoutError, subprocess.TimeoutExpired):
                    self._proc.kill()
