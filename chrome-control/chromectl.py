#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "aiohttp>=3.9",
# ]
# ///
"""chromectl — control Chrome via CDP from the command line.

Connects to your running Chrome session via DevToolsActivePort
(chrome://inspect/#remote-debugging). All tabs, cookies, and logins accessible.

Commands:
  start                Connect to Chrome daemon on Unix socket
  stop                 Stop daemon and/or launched Chrome instances
  send <cmd>           Send command to running daemon
  list                 List open tabs/targets
  open <url>           Open a new tab, print its targetId
  eval  --id <id>  -e <js>         Evaluate JavaScript in a target
  screenshot --id <id> [-o file]   Capture a PNG screenshot
  console-tail --id <id> [--for S] Stream console/log messages
  launch               Launch a separate Chrome instance (legacy)
"""

import argparse
import asyncio
import base64
import json
import os
import platform
import sys
import time
from typing import Any

import aiohttp

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9222


def default_chrome_user_data_dir() -> str:
    """Return the default Chrome user data directory for the current platform."""
    system = platform.system()
    if system == "Darwin":
        return os.path.expanduser("~/Library/Application Support/Google/Chrome")
    elif system == "Linux":
        return os.path.expanduser("~/.config/google-chrome")
    elif system == "Windows":
        return os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "User Data")
    return ""


def read_devtools_active_port(user_data_dir: str) -> tuple[int, str]:
    """Read DevToolsActivePort file. Returns (port, ws_path)."""
    port_file = os.path.join(user_data_dir, "DevToolsActivePort")
    with open(port_file) as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]
    if len(lines) < 2:
        raise CDPError(f"Invalid DevToolsActivePort content in {port_file}")
    port = int(lines[0])
    ws_path = lines[1]
    return port, ws_path


class CDPError(RuntimeError):
    pass


class BrowserConnection:
    """Browser-level CDP connection via WebSocket (M144+ auto-connect).

    Uses Target.attachToTarget with flatten=True to multiplex page sessions
    over the single browser WebSocket — M144 blocks direct page WS URLs.
    """

    def __init__(self, host: str, port: int, ws_path: str):
        self.ws_url = f"ws://{host}:{port}{ws_path}"
        self._conn: CDPConnection | None = None

    async def __aenter__(self):
        self._conn = CDPConnection(self.ws_url)
        await self._conn.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._conn:
            await self._conn.__aexit__(exc_type, exc, tb)

    async def list_targets(self) -> list[dict]:
        assert self._conn
        result = await self._conn.send("Target.getTargets")
        return result.get("targetInfos", [])

    async def create_target(self, url: str) -> dict:
        assert self._conn
        result = await self._conn.send("Target.createTarget", {"url": url})
        target_id = result.get("targetId", "")
        return {"id": target_id, "url": url}

    async def attach_to_target(self, target_id: str) -> "FlatSession":
        """Attach to a page target using flatten=True, returning a FlatSession."""
        assert self._conn
        result = await self._conn.send(
            "Target.attachToTarget",
            {
                "targetId": target_id,
                "flatten": True,
            },
        )
        session_id = result.get("sessionId", "")
        if not session_id:
            raise CDPError(f"Failed to attach to target {target_id}")
        return FlatSession(self._conn, session_id)


class FlatSession:
    """A page-level CDP session multiplexed over the browser WebSocket."""

    def __init__(self, conn: "CDPConnection", session_id: str):
        self._conn = conn
        self._session_id = session_id

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass

    async def send(self, method: str, params: dict[str, Any] | None = None) -> Any:
        return await self._conn.send_session(method, self._session_id, params)

    def set_event_handler(self, handler):
        self._conn.set_session_event_handler(self._session_id, handler)


async def http_get_json(session: aiohttp.ClientSession, url: str) -> Any:
    async with session.get(url) as resp:
        resp.raise_for_status()
        return await resp.json()


async def list_targets_http(host: str, port: int) -> Any:
    async with aiohttp.ClientSession() as session:
        async with session.get(f"http://{host}:{port}/json") as resp:
            resp.raise_for_status()
            return await resp.json()


async def new_tab_http(host: str, port: int, url: str) -> Any:
    async with aiohttp.ClientSession() as session:
        async with session.put(f"http://{host}:{port}/json/new?{url}") as resp:
            resp.raise_for_status()
            return await resp.json()


class CDPConnection:
    def __init__(self, ws_url: str):
        self.ws_url = ws_url
        self._id = 0
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._pending: dict[int, asyncio.Future] = {}
        self._event_handler = None
        self._session_event_handlers: dict[str, Any] = {}

    async def __aenter__(self):
        self._http_session = aiohttp.ClientSession()
        self._ws = await self._http_session.ws_connect(self.ws_url, autoclose=True, autoping=True)
        self._recv_task = asyncio.create_task(self._recv_loop())
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._ws is not None:
            await self._ws.close()
        await self._http_session.close()

    async def _recv_loop(self):
        assert self._ws is not None
        async for msg in self._ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                data = json.loads(msg.data)
                if "id" in data:
                    fut = self._pending.pop(data["id"], None)
                    if fut and not fut.done():
                        fut.set_result(data)
                elif "method" in data:
                    session_id = data.get("sessionId")
                    if session_id and session_id in self._session_event_handlers:
                        await self._session_event_handlers[session_id](data)
                    elif self._event_handler:
                        await self._event_handler(data)
            elif msg.type == aiohttp.WSMsgType.ERROR:
                break

    async def send(self, method: str, params: dict[str, Any] | None = None) -> Any:
        self._id += 1
        msg: dict[str, Any] = {"id": self._id, "method": method}
        if params:
            msg["params"] = params
        loop = asyncio.get_event_loop()
        fut = loop.create_future()
        self._pending[self._id] = fut
        assert self._ws is not None
        await self._ws.send_json(msg)
        resp = await fut
        if "error" in resp:
            raise CDPError(f"{method} error: {resp['error']}")
        return resp.get("result", {})

    async def send_session(self, method: str, session_id: str, params: dict[str, Any] | None = None) -> Any:
        """Send a CDP command scoped to a flat session."""
        self._id += 1
        msg: dict[str, Any] = {"id": self._id, "method": method, "sessionId": session_id}
        if params:
            msg["params"] = params
        loop = asyncio.get_event_loop()
        fut = loop.create_future()
        self._pending[self._id] = fut
        assert self._ws is not None
        await self._ws.send_json(msg)
        resp = await fut
        if "error" in resp:
            raise CDPError(f"{method} error: {resp['error']}")
        return resp.get("result", {})

    def set_event_handler(self, handler):
        self._event_handler = handler

    def set_session_event_handler(self, session_id: str, handler):
        self._session_event_handlers[session_id] = handler


def resolve_connection(args) -> tuple[str, int, str | None]:
    """Resolve connection parameters. Returns (host, port, ws_path_or_none).

    ws_path is set when using auto-connect (DevToolsActivePort or fallback).
    ws_path is None when using traditional HTTP-based CDP.
    """
    if getattr(args, "auto_connect", False):
        user_data_dir = getattr(args, "user_data_dir", None) or default_chrome_user_data_dir()
        try:
            port, ws_path = read_devtools_active_port(user_data_dir)
            return args.host, port, ws_path
        except FileNotFoundError:
            # DevToolsActivePort missing — try direct /devtools/browser (no GUID needed)
            port = args.port
            ws_path = "/devtools/browser"
            return args.host, port, ws_path
        except Exception as e:
            raise CDPError(f"Failed to read DevToolsActivePort: {e}")
    return args.host, args.port, None


async def find_ws_for_target_http(host: str, port: int, target_id: str) -> str:
    """Traditional: lookup page WS URL via HTTP /json."""
    targets = await list_targets_http(host, port)
    for t in targets:
        if t.get("id") == target_id:
            return t["webSocketDebuggerUrl"]
    raise CDPError(f"Target {target_id} not found. Use `chromectl list`.")


class _AutoConnectSession:
    """Context manager wrapping BrowserConnection + FlatSession for auto-connect."""

    def __init__(self, host: str, port: int, ws_path: str, target_id: str):
        self._bc = BrowserConnection(host, port, ws_path)
        self._target_id = target_id
        self._session: FlatSession | None = None

    async def __aenter__(self):
        await self._bc.__aenter__()
        self._session = await self._bc.attach_to_target(self._target_id)
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        await self._bc.__aexit__(exc_type, exc, tb)


def attach_to_target(host: str, port: int, target_id: str, ws_path: str | None = None):
    """Return an async context manager yielding a session (CDPConnection or FlatSession)."""
    if ws_path:
        return _AutoConnectSession(host, port, ws_path, target_id)

    # Traditional: direct page WS connection
    async def _make():
        ws_url = await find_ws_for_target_http(host, port, target_id)
        return CDPConnection(ws_url)

    return _TraditionalSession(_make)


class _TraditionalSession:
    """Async context manager for traditional direct page WS connection."""

    def __init__(self, factory):
        self._factory = factory
        self._conn: CDPConnection | None = None

    async def __aenter__(self):
        self._conn = await self._factory()
        await self._conn.__aenter__()
        return self._conn

    async def __aexit__(self, exc_type, exc, tb):
        if self._conn:
            await self._conn.__aexit__(exc_type, exc, tb)


# --- Commands ---


async def cmd_launch(args):
    chrome_app = args.chrome_app or "Google Chrome"
    user_data_dir = args.user_data_dir or os.path.expanduser("~/chromectl-profile")
    os.makedirs(user_data_dir, exist_ok=True)
    port = args.port

    chrome_bin = f"/Applications/{chrome_app}.app/Contents/MacOS/{chrome_app}"
    if not os.path.exists(chrome_bin):
        raise CDPError(f"Chrome binary not found at: {chrome_bin}")

    extra = [
        "--remote-allow-origins=*",
        f"--remote-debugging-port={port}",
        f"--user-data-dir={user_data_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-features=PrivacySandboxSettings4",
    ]
    if args.headless:
        extra.append("--headless=new")
        extra.append("--window-size=1280,800")

    cmd = [chrome_bin, *extra]
    print("Launching:", " ".join(cmd))
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
    print(f"Chrome launched (PID: {proc.pid}) with remote debugging on port {port}")
    print(f"Profile directory: {user_data_dir}")


async def cmd_list(args):
    host, port, ws_path = resolve_connection(args)
    if ws_path:
        async with BrowserConnection(host, port, ws_path) as bc:
            targets = await bc.list_targets()
            for t in targets:
                if t.get("type") not in ("page", "webview"):
                    continue
                print(
                    json.dumps(
                        {
                            "id": t.get("targetId"),
                            "type": t.get("type"),
                            "title": t.get("title"),
                            "url": t.get("url"),
                            "attached": t.get("attached"),
                        },
                        ensure_ascii=False,
                    )
                )
    else:
        targets = await list_targets_http(host, port)
        for t in targets:
            print(
                json.dumps(
                    {
                        "id": t.get("id"),
                        "type": t.get("type"),
                        "title": t.get("title"),
                        "url": t.get("url"),
                        "attached": t.get("attached"),
                    },
                    ensure_ascii=False,
                )
            )


async def cmd_open(args):
    host, port, ws_path = resolve_connection(args)
    if ws_path:
        async with BrowserConnection(host, port, ws_path) as bc:
            res = await bc.create_target(args.url)
            print(json.dumps(res, ensure_ascii=False))
    else:
        res = await new_tab_http(host, port, args.url)
        print(json.dumps({"id": res.get("id"), "url": res.get("url")}, ensure_ascii=False))


async def cmd_eval(args):
    host, port, ws_path = resolve_connection(args)
    async with attach_to_target(host, port, args.id, ws_path) as conn:
        await conn.send("Runtime.enable")
        result = await conn.send(
            "Runtime.evaluate",
            {
                "expression": args.expr,
                "returnByValue": True,
                "awaitPromise": True,
                "replMode": True,
            },
        )
        if "exceptionDetails" in result:
            print(json.dumps(result["exceptionDetails"], ensure_ascii=False))
            sys.exit(2)
        r = result.get("result", {})
        if r.get("type") == "object" and "value" in r:
            print(json.dumps(r["value"], ensure_ascii=False))
        elif "value" in r:
            print(json.dumps(r["value"], ensure_ascii=False))
        else:
            print(json.dumps(r, ensure_ascii=False))


async def cmd_screenshot(args):
    host, port, ws_path = resolve_connection(args)
    async with attach_to_target(host, port, args.id, ws_path) as conn:
        await conn.send("Page.enable")
        if args.full_page:
            lm = await conn.send("Page.getLayoutMetrics")
            content_size = lm["contentSize"]
            width, height = int(content_size["width"]), int(content_size["height"])
            await conn.send(
                "Emulation.setDeviceMetricsOverride",
                {
                    "width": width,
                    "height": height,
                    "deviceScaleFactor": 1,
                    "mobile": False,
                },
            )
        await conn.send("Page.bringToFront")
        result = await conn.send("Page.captureScreenshot", {"format": "png", "fromSurface": True})
        b64 = result.get("data")
        if not b64:
            raise CDPError("No screenshot data returned")
        data = base64.b64decode(b64)
        out = args.output or f"screenshot_{args.id}.png"
        with open(out, "wb") as f:
            f.write(data)
        print(out)


async def cmd_console_tail(args):
    host, port, ws_path = resolve_connection(args)
    async with attach_to_target(host, port, args.id, ws_path) as conn:
        await conn.send("Runtime.enable")
        await conn.send("Log.enable")

        start_ts = time.time()

        async def handler(evt):
            method = evt.get("method")
            params = evt.get("params", {})
            now = time.time()
            tdelta = f"+{now - start_ts:0.3f}s"
            if method == "Log.entryAdded":
                entry = params.get("entry", {})
                level = entry.get("level")
                text = entry.get("text")
                source = entry.get("source")
                print(json.dumps({"t": tdelta, "level": level, "source": source, "text": text}, ensure_ascii=False))
            elif method == "Runtime.consoleAPICalled":
                typ = params.get("type")
                console_args = params.get("args", [])
                vals = []
                for a in console_args:
                    if "value" in a:
                        vals.append(a["value"])
                    else:
                        vals.append(a.get("description") or a.get("type"))
                print(json.dumps({"t": tdelta, "console": typ, "args": vals}, ensure_ascii=False))

        conn.set_event_handler(handler)
        duration = float(args.for_seconds)
        await asyncio.sleep(duration)


SOCKET_PATH = f"/tmp/chromectl-{os.getuid()}.sock"


async def cmd_stop(args):
    import signal
    import subprocess

    stopped_anything = False

    # Stop daemon if running
    if os.path.exists(SOCKET_PATH):
        try:
            reader, writer = await asyncio.open_unix_connection(SOCKET_PATH)
            writer.write(b'{"cmd":"quit"}\n')
            await writer.drain()
            await asyncio.wait_for(reader.readline(), timeout=5)
            writer.close()
            print("Daemon stopped")
            stopped_anything = True
        except Exception:
            pass

    # Kill chromectl-launched Chrome instances
    try:
        result = subprocess.run(["ps", "aux"], capture_output=True, text=True, check=True)

        pids_to_kill = []
        for line in result.stdout.splitlines():
            if "Google Chrome" in line and "chromectl" in line:
                parts = line.split()
                if len(parts) > 1:
                    try:
                        pid = int(parts[1])
                        pids_to_kill.append((pid, line))
                    except ValueError:
                        continue

        for pid, _line in pids_to_kill:
            print(f"Stopping Chrome instance (PID: {pid})")
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                print(f"  Process {pid} already stopped")
            except PermissionError:
                print(f"  Permission denied to stop process {pid}")

        if pids_to_kill:
            time.sleep(1)
            print(f"Stopped {len(pids_to_kill)} Chrome instance(s)")
            stopped_anything = True
    except Exception as e:
        print(f"Error stopping Chrome: {e}", file=sys.stderr)
        sys.exit(1)

    if not stopped_anything:
        print("Nothing to stop (no daemon, no chromectl Chrome instances)")


class Dispatcher:
    """Shared command dispatch for shell and daemon modes.

    Handles reconnection to Chrome when the browser WS drops.
    """

    DISPATCH_TIMEOUT = 30  # seconds per command
    RECONNECT_DELAY = 1  # seconds between reconnect attempts
    MAX_RECONNECT = 5  # max consecutive reconnect attempts
    IDLE_TIMEOUT = 300  # 5 min — shut down daemon if no commands

    def __init__(self, host: str, port: int, ws_path: str | None, bc: BrowserConnection | None, user_data_dir: str | None = None):
        self.host = host
        self.port = port
        self.ws_path = ws_path
        self.bc = bc
        self.sessions: dict[str, FlatSession] = {}
        self._user_data_dir = user_data_dir
        self._connected = bc is not None
        self._last_success = time.time()
        self._dead = False  # set when CDP connection is permanently lost

    async def _reconnect(self) -> bool:
        """Reconnect to Chrome by re-reading DevToolsActivePort or fallback."""
        if not self._user_data_dir:
            return False
        for attempt in range(1, self.MAX_RECONNECT + 1):
            try:
                if self.bc:
                    try:
                        await self.bc.__aexit__(None, None, None)
                    except Exception:
                        pass
                try:
                    port, ws_path = read_devtools_active_port(self._user_data_dir)
                except FileNotFoundError:
                    port, ws_path = self.port, "/devtools/browser"
                self.port = port
                self.ws_path = ws_path
                self.bc = BrowserConnection(self.host, port, ws_path)
                await self.bc.__aenter__()
                self.sessions.clear()
                self._connected = True
                print(f"reconnected to Chrome (attempt {attempt})", flush=True)
                return True
            except Exception as e:
                print(f"reconnect attempt {attempt}/{self.MAX_RECONNECT} failed: {e}", flush=True)
                if attempt < self.MAX_RECONNECT:
                    await asyncio.sleep(self.RECONNECT_DELAY)
        self._connected = False
        return False

    async def get_session(self, target_id: str):
        if self.ws_path and self.bc:
            if target_id not in self.sessions:
                self.sessions[target_id] = await self.bc.attach_to_target(target_id)
            return self.sessions[target_id]
        ws_url = await find_ws_for_target_http(self.host, self.port, target_id)
        conn = CDPConnection(ws_url)
        await conn.__aenter__()
        return conn

    async def dispatch_safe(self, req: dict) -> dict:
        """Dispatch with timeout and auto-reconnect on failure."""
        try:
            result = await asyncio.wait_for(self.dispatch(req), timeout=self.DISPATCH_TIMEOUT)
            self._last_success = time.time()
            return result
        except (asyncio.TimeoutError, CDPError, aiohttp.ClientError, ConnectionError, OSError) as e:
            err_type = type(e).__name__
            if isinstance(e, asyncio.TimeoutError) or "close" in str(e).lower() or "connect" in str(e).lower():
                self.sessions.clear()
                if await self._reconnect():
                    try:
                        result = await asyncio.wait_for(self.dispatch(req), timeout=self.DISPATCH_TIMEOUT)
                        self._last_success = time.time()
                        return result
                    except Exception as e2:
                        self._dead = True
                        return {"error": f"{type(e2).__name__}: {e2} (after reconnect)"}
                else:
                    self._dead = True
            return {"error": f"{err_type}: {e}"}

    async def dispatch(self, req: dict) -> dict:
        cmd = req.get("cmd", "")

        if cmd in ("list", "targets"):
            if self.ws_path and self.bc:
                targets = await self.bc.list_targets()
                results = []
                for t in targets:
                    if cmd == "list" and t.get("type") not in ("page", "webview"):
                        continue
                    results.append(
                        {
                            "id": t.get("targetId"),
                            "type": t.get("type"),
                            "title": t.get("title"),
                            "url": t.get("url"),
                        }
                    )
            else:
                targets = await list_targets_http(self.host, self.port)
                results = [{"id": t.get("id"), "type": t.get("type"), "title": t.get("title"), "url": t.get("url")} for t in targets]
            return {"targets": results}

        elif cmd == "open":
            url = req.get("url", "about:blank")
            if self.ws_path and self.bc:
                return await self.bc.create_target(url)
            res = await new_tab_http(self.host, self.port, url)
            return {"id": res.get("id"), "url": res.get("url")}

        elif cmd == "eval":
            target_id = req.get("id")
            if not target_id:
                return {"error": "Missing 'id'"}
            session = await self.get_session(target_id)
            await session.send("Runtime.enable")
            result = await session.send(
                "Runtime.evaluate",
                {
                    "expression": req.get("expr", ""),
                    "returnByValue": True,
                    "awaitPromise": True,
                    "replMode": True,
                },
            )
            if "exceptionDetails" in result:
                return {"error": result["exceptionDetails"]}
            r = result.get("result", {})
            return {"value": r["value"]} if "value" in r else {"result": r}

        elif cmd == "screenshot":
            target_id = req.get("id")
            if not target_id:
                return {"error": "Missing 'id'"}
            session = await self.get_session(target_id)
            await session.send("Page.enable")
            if req.get("full_page"):
                lm = await session.send("Page.getLayoutMetrics")
                cs = lm["contentSize"]
                await session.send(
                    "Emulation.setDeviceMetricsOverride",
                    {
                        "width": int(cs["width"]),
                        "height": int(cs["height"]),
                        "deviceScaleFactor": 1,
                        "mobile": False,
                    },
                )
            await session.send("Page.bringToFront")
            result = await session.send("Page.captureScreenshot", {"format": "png", "fromSurface": True})
            b64 = result.get("data")
            if not b64:
                return {"error": "No screenshot data"}
            out = req.get("output", f"screenshot_{target_id}.png")
            with open(out, "wb") as f:
                f.write(base64.b64decode(b64))
            return {"file": out}

        elif cmd == "console-tail":
            target_id = req.get("id")
            if not target_id:
                return {"error": "Missing 'id'"}
            duration = float(req.get("for", 5))
            session = await self.get_session(target_id)
            await session.send("Runtime.enable")
            await session.send("Log.enable")
            messages: list[dict] = []
            start_ts = time.time()

            async def console_handler(evt):
                method = evt.get("method")
                params = evt.get("params", {})
                tdelta = f"+{time.time() - start_ts:0.3f}s"
                if method == "Log.entryAdded":
                    entry = params.get("entry", {})
                    messages.append({"t": tdelta, "level": entry.get("level"), "text": entry.get("text")})
                elif method == "Runtime.consoleAPICalled":
                    vals = [a.get("value", a.get("description", a.get("type"))) for a in params.get("args", [])]
                    messages.append({"t": tdelta, "console": params.get("type"), "args": vals})

            session.set_event_handler(console_handler)
            await asyncio.sleep(duration)
            session.set_event_handler(None)
            return {"messages": messages}

        elif cmd == "cdp":
            # Raw CDP command via browser connection
            method = req.get("method", "")
            params = req.get("params")
            if not method:
                return {"error": "Missing 'method'"}
            if self.bc and self.bc._conn:
                result = await self.bc._conn.send(method, params)
                return {"result": result}
            return {"error": "No browser connection (auto-connect only)"}

        elif cmd == "worker-eval":
            # Eval inside a worker target via flat session
            target_id = req.get("id")
            expr = req.get("expr", "")
            if not target_id:
                return {"error": "Missing 'id'"}
            if not self.bc or not self.bc._conn:
                return {"error": "No browser connection"}
            # Attach to worker
            if target_id not in self.sessions:
                result = await self.bc._conn.send(
                    "Target.attachToTarget",
                    {
                        "targetId": target_id,
                        "flatten": True,
                    },
                )
                sid = result.get("sessionId", "")
                if not sid:
                    return {"error": f"Failed to attach to {target_id}"}
                self.sessions[target_id] = FlatSession(self.bc._conn, sid)
            session = self.sessions[target_id]
            await session.send("Runtime.enable")
            result = await session.send(
                "Runtime.evaluate",
                {
                    "expression": expr,
                    "returnByValue": True,
                    "awaitPromise": True,
                },
            )
            if "exceptionDetails" in result:
                return {"error": result["exceptionDetails"]}
            r = result.get("result", {})
            return {"value": r["value"]} if "value" in r else {"result": r}

        elif cmd == "status":
            return {
                "connected": self._connected,
                "mode": "auto-connect" if self.ws_path else "http",
                "port": self.port,
                "sessions": len(self.sessions),
                "pid": os.getpid(),
            }

        else:
            return {"error": f"Unknown command: {cmd}. Try: list, eval, screenshot, open, console-tail, status, quit"}


async def make_dispatcher(args) -> tuple[Dispatcher, BrowserConnection | None]:
    host, port, ws_path = resolve_connection(args)
    user_data_dir = None
    if getattr(args, "auto_connect", False):
        user_data_dir = getattr(args, "user_data_dir", None) or default_chrome_user_data_dir()
    bc = None
    if ws_path:
        bc = BrowserConnection(host, port, ws_path)
        await bc.__aenter__()
    return Dispatcher(host, port, ws_path, bc, user_data_dir), bc


async def cmd_start(args):
    """Connect to Chrome and listen on Unix socket. netcat-compatible.

    Usage:  chromectl start
            chromectl send list
            chromectl stop
    """
    args.auto_connect = True
    dispatcher, bc = await make_dispatcher(args)

    # Clean stale socket
    if os.path.exists(SOCKET_PATH):
        os.unlink(SOCKET_PATH)

    async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            data = await asyncio.wait_for(reader.readline(), timeout=30)
            if not data:
                writer.close()
                return
            line = data.decode().strip()
            if not line:
                writer.close()
                return
            try:
                req = json.loads(line)
            except json.JSONDecodeError as e:
                writer.write(json.dumps({"error": f"Invalid JSON: {e}"}).encode() + b"\n")
                await writer.drain()
                writer.close()
                return

            if req.get("cmd") == "quit":
                writer.write(json.dumps({"status": "bye"}).encode() + b"\n")
                await writer.drain()
                writer.close()
                # Stop the server
                server.close()
                return

            result = await dispatcher.dispatch_safe(req)
            writer.write(json.dumps(result, ensure_ascii=False).encode() + b"\n")
            await writer.drain()
        except Exception as e:
            try:
                writer.write(json.dumps({"error": f"{type(e).__name__}: {e}"}).encode() + b"\n")
                await writer.drain()
            except Exception:
                pass
        finally:
            writer.close()

    server = await asyncio.start_unix_server(handle_client, path=SOCKET_PATH)
    os.chmod(SOCKET_PATH, 0o600)
    print(f"chromectl daemon listening on {SOCKET_PATH} (PID {os.getpid()})", flush=True)
    print(f'Usage: echo \'{{"cmd":"list"}}\' | nc -U {SOCKET_PATH}', flush=True)

    # Watchdog: shutdown if CDP connection is dead OR idle too long
    async def idle_watchdog():
        liveness_counter = 0
        while True:
            await asyncio.sleep(5)
            if dispatcher._dead:
                print("CDP connection lost, shutting down", flush=True)
                server.close()
                return
            idle = time.time() - dispatcher._last_success
            if idle > dispatcher.IDLE_TIMEOUT:
                print(f"idle {idle:.0f}s > {dispatcher.IDLE_TIMEOUT}s, shutting down", flush=True)
                server.close()
                return
            # Proactive liveness probe every 30s when idle, to detect dead CDP
            # connections before the next client request arrives.
            liveness_counter += 1
            if liveness_counter >= 6 and idle > 10 and dispatcher.bc:
                liveness_counter = 0
                try:
                    await asyncio.wait_for(dispatcher.bc.list_targets(), timeout=5)
                except Exception as e:
                    print(f"liveness probe failed: {type(e).__name__}: {e}, shutting down", flush=True)
                    server.close()
                    return

    watchdog = asyncio.create_task(idle_watchdog())

    try:
        await server.serve_forever()
    except asyncio.CancelledError:
        pass
    finally:
        watchdog.cancel()
        if os.path.exists(SOCKET_PATH):
            os.unlink(SOCKET_PATH)
        if bc:
            await bc.__aexit__(None, None, None)
        print("daemon stopped", flush=True)



async def cmd_send(args):
    """Send a single command to running daemon. For quick CLI use."""
    if not os.path.exists(SOCKET_PATH):
        print(f"No daemon running ({SOCKET_PATH} not found). Start with: chromectl start", file=sys.stderr)
        sys.exit(1)
    # Build request from subcommand args
    req: dict = {"cmd": args.send_cmd}
    if hasattr(args, "send_id") and args.send_id:
        req["id"] = args.send_id
    if hasattr(args, "send_expr") and args.send_expr:
        req["expr"] = args.send_expr
    if hasattr(args, "send_url") and args.send_url:
        req["url"] = args.send_url
    if hasattr(args, "send_output") and args.send_output:
        req["output"] = args.send_output
    if hasattr(args, "send_full_page") and args.send_full_page:
        req["full_page"] = True
    if hasattr(args, "send_for") and args.send_for:
        req["for"] = float(args.send_for)

    reader, writer = await asyncio.open_unix_connection(SOCKET_PATH)
    writer.write(json.dumps(req).encode() + b"\n")
    await writer.drain()
    resp = await reader.readline()
    print(resp.decode().strip())
    writer.close()


def build_parser():
    p = argparse.ArgumentParser(prog="chromectl", description="Operate Chrome via DevTools Protocol (CDP) from the CLI.")
    p.add_argument("--host", default=DEFAULT_HOST)
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument(
        "--auto-connect", action="store_true", help="Connect via DevToolsActivePort file (Chrome M144+, chrome://inspect/#remote-debugging)"
    )
    p.add_argument("--user-data-dir", default=None, help="Chrome user data directory (default: auto-detected for platform)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("start", help="Connect to running Chrome and listen on Unix socket")
    sp.set_defaults(func=cmd_start)

    sp = sub.add_parser("stop", help="Stop daemon and/or launched Chrome instances")
    sp.set_defaults(func=cmd_stop)

    sp = sub.add_parser("send", help="Send command to running daemon")
    sp.add_argument("send_cmd", metavar="CMD", help="Command: list, eval, screenshot, open, console-tail")
    sp.add_argument("--id", dest="send_id", help="Target id")
    sp.add_argument("-e", "--expr", dest="send_expr", help="JS expression (for eval)")
    sp.add_argument("--url", dest="send_url", help="URL (for open)")
    sp.add_argument("-o", "--output", dest="send_output", help="Output file (for screenshot)")
    sp.add_argument("--full-page", dest="send_full_page", action="store_true")
    sp.add_argument("--for", dest="send_for", help="Duration in seconds (for console-tail)")
    sp.set_defaults(func=cmd_send)

    sp = sub.add_parser("list", help="List open tabs/targets")
    sp.set_defaults(func=cmd_list)

    sp = sub.add_parser("open", help="Open a new tab at URL and print its targetId")
    sp.add_argument("url", help="URL to open, e.g., https://example.com")
    sp.set_defaults(func=cmd_open)

    sp = sub.add_parser("eval", help="Evaluate JavaScript in a target")
    sp.add_argument("--id", required=True, help="Target id from `chromectl list` or `chromectl open`")
    sp.add_argument("-e", "--expr", required=True, help="JavaScript expression to evaluate")
    sp.set_defaults(func=cmd_eval)

    sp = sub.add_parser("screenshot", help="Capture a PNG screenshot")
    sp.add_argument("--id", required=True, help="Target id to capture")
    sp.add_argument("-o", "--output", help="Output PNG path")
    sp.add_argument("--full-page", action="store_true", help="Full-page capture")
    sp.set_defaults(func=cmd_screenshot)

    sp = sub.add_parser("console-tail", help="Stream console/log entries for a target")
    sp.add_argument("--id", required=True, help="Target id to attach to")
    sp.add_argument("--for", dest="for_seconds", default="10", help="Seconds to stream (default: 10)")
    sp.set_defaults(func=cmd_console_tail)

    sp = sub.add_parser("launch", help="Launch a separate Chrome instance with its own profile (legacy)")
    sp.add_argument("--chrome-app", default="Google Chrome", help="macOS app name")
    sp.add_argument("--user-data-dir", default=None, help="Custom Chrome profile directory")
    sp.add_argument("--port", type=int, default=DEFAULT_PORT, help="Remote debugging port")
    sp.add_argument("--headless", action="store_true", help="Launch with --headless=new")
    sp.set_defaults(func=cmd_launch)

    return p


async def amain():
    parser = build_parser()
    args = parser.parse_args()
    try:
        await args.func(args)
    except CDPError as e:
        print(f"CDP error: {e}", file=sys.stderr)
        sys.exit(2)
    except aiohttp.ClientError as e:
        print(f"HTTP/WS error: {e}", file=sys.stderr)
        sys.exit(2)


def main():
    asyncio.run(amain())


if __name__ == "__main__":
    main()
