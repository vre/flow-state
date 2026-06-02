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
  start                   Connect to Chrome daemon on Unix socket
  stop                    Stop daemon and/or launched Chrome instances
  list                    List open tabs
  open <url>              Open a new tab
  status                  Daemon connection status
  <id> <cmd> [args]       Run command on a target (eval, click, type, ...)
  helpers                 List DOM helper commands
  launch                  Launch a separate Chrome instance (legacy)
"""

import argparse
import asyncio
import base64
import json
import os
import platform
import signal
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
    """Browser-level CDP connection via WebSocket.

    Since Chrome M144 (January 2026), direct page WebSocket URLs are blocked.
    Uses Target.attachToTarget with flatten=True to multiplex page sessions
    over a single browser-level WebSocket.
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
        self._recv_task.cancel()
        try:
            await self._recv_task
        except asyncio.CancelledError:
            pass
        if self._ws is not None:
            await self._ws.close()
        await self._http_session.close()

    async def _recv_loop(self):
        assert self._ws is not None
        try:
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
        finally:
            for fut in self._pending.values():
                if not fut.done():
                    fut.set_exception(ConnectionError("WebSocket closed"))

    async def send(self, method: str, params: dict[str, Any] | None = None) -> Any:
        self._id += 1
        msg: dict[str, Any] = {"id": self._id, "method": method}
        if params is not None:
            msg["params"] = params
        loop = asyncio.get_running_loop()
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
        if params is not None:
            msg["params"] = params
        loop = asyncio.get_running_loop()
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
        if handler is None:
            self._session_event_handlers.pop(session_id, None)
        else:
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


# --- Helper JS generation ---


def _js(s: str) -> str:
    """Escape a Python string as a JS string literal."""
    return json.dumps(s)


_WAIT_COMMANDS = {"wait-for", "wait-text", "wait-url", "wait-hidden"}

_HELPER_COMMANDS = {
    "click",
    "check",
    "uncheck",
    "highlight",
    "submit",
    "clear",
    "type",
    "fill",
    "select",
    "get-text",
    "get-html",
    "get-value",
    "get-attr",
    "exists",
    "count",
    "get-texts",
    "scroll-to",
    "scroll-up",
    "scroll-down",
    "scroll-top",
    "scroll-bottom",
    "scroll-by",
    "back",
    "forward",
    "get-title",
    "get-url",
    "inject-css",
}


def _build_helper_js(cmd: str, req: dict) -> str | None:
    """Build JS expression for a helper command. Returns None if not a helper."""
    sel = req.get("selector", "")
    s = _js(sel)

    if cmd == "click":
        return f"(()=>{{const e=document.querySelector({s});if(!e)throw new Error('No element: '+{s});e.click();return true}})()"
    if cmd == "check":
        return f"(()=>{{const e=document.querySelector({s});if(!e)throw new Error('No element: '+{s});if(!e.checked)e.click();return e.checked}})()"
    if cmd == "uncheck":
        return f"(()=>{{const e=document.querySelector({s});if(!e)throw new Error('No element: '+{s});if(e.checked)e.click();return!e.checked}})()"
    if cmd == "highlight":
        return f"(()=>{{const a=document.querySelectorAll({s});if(!a.length)throw new Error('No elements: '+{s});a.forEach(e=>e.style.outline='2px solid red');return a.length}})()"
    if cmd == "submit":
        return f"(()=>{{const e=document.querySelector({s});if(!e)throw new Error('No form: '+{s});e.submit();return true}})()"
    if cmd == "clear":
        return f"(()=>{{const e=document.querySelector({s});if(!e)throw new Error('No form: '+{s});e.reset();return true}})()"
    if cmd == "type":
        t = _js(req.get("text", ""))
        return f"(()=>{{const e=document.querySelector({s});if(!e)throw new Error('No element: '+{s});e.focus();e.value={t};e.dispatchEvent(new InputEvent('input',{{bubbles:true}}));e.dispatchEvent(new Event('change',{{bubbles:true}}));return e.value}})()"
    if cmd == "fill":
        t = _js(req.get("value", ""))
        return f"(()=>{{const e=document.querySelector({s});if(!e)throw new Error('No element: '+{s});e.focus();e.value={t};e.dispatchEvent(new InputEvent('input',{{bubbles:true}}));e.dispatchEvent(new Event('change',{{bubbles:true}}));return e.value}})()"
    if cmd == "select":
        v = _js(req.get("value", ""))
        return f"(()=>{{const e=document.querySelector({s});if(!e)throw new Error('No element: '+{s});e.value={v};e.dispatchEvent(new Event('change',{{bubbles:true}}));return e.value}})()"
    if cmd == "get-text":
        return f"(()=>{{const e=document.querySelector({s});if(!e)throw new Error('No element: '+{s});return e.innerText}})()"
    if cmd == "get-html":
        return f"(()=>{{const e=document.querySelector({s});if(!e)throw new Error('No element: '+{s});return e.innerHTML}})()"
    if cmd == "get-value":
        return f"(()=>{{const e=document.querySelector({s});if(!e)throw new Error('No element: '+{s});return e.value}})()"
    if cmd == "get-attr":
        a = _js(req.get("attr", ""))
        return f"(()=>{{const e=document.querySelector({s});if(!e)throw new Error('No element: '+{s});return e.getAttribute({a})}})()"
    if cmd == "exists":
        return f"document.querySelector({s})!==null"
    if cmd == "count":
        return f"document.querySelectorAll({s}).length"
    if cmd == "get-texts":
        return f"[...document.querySelectorAll({s})].map(e=>e.innerText)"
    if cmd == "scroll-to":
        return f"(()=>{{const e=document.querySelector({s});if(!e)throw new Error('No element: '+{s});e.scrollIntoView({{behavior:'smooth',block:'center'}});return true}})()"
    if cmd == "scroll-up":
        try:
            px = int(req["pixels"]) if "pixels" in req else None
        except (ValueError, TypeError):
            return None
        return f"window.scrollBy(0,-{px})" if px else "window.scrollBy(0,-window.innerHeight)"
    if cmd == "scroll-down":
        try:
            px = int(req["pixels"]) if "pixels" in req else None
        except (ValueError, TypeError):
            return None
        return f"window.scrollBy(0,{px})" if px else "window.scrollBy(0,window.innerHeight)"
    if cmd == "scroll-top":
        return "window.scrollTo(0,0)"
    if cmd == "scroll-bottom":
        return "window.scrollTo(0,document.body.scrollHeight)"
    if cmd == "scroll-by":
        try:
            x, y = int(req.get("x", 0)), int(req.get("y", 0))
        except (ValueError, TypeError):
            return None
        return f"window.scrollBy({x},{y})"
    if cmd == "back":
        return "history.back()"
    if cmd == "forward":
        return "history.forward()"
    if cmd == "get-title":
        return "document.title"
    if cmd == "get-url":
        return "location.href"
    if cmd == "inject-css":
        c = _js(req.get("css", ""))
        return f"(()=>{{const s=document.createElement('style');s.textContent={c};document.head.appendChild(s);return true}})()"
    return None


def _build_wait_js(cmd: str, req: dict) -> str:
    """Build JS check expression for a wait command."""
    sel = req.get("selector", "")
    s = _js(sel)

    if cmd == "wait-for":
        return f"document.querySelector({s})!==null"
    if cmd == "wait-hidden":
        return f"(()=>{{const e=document.querySelector({s});return!e||e.offsetParent===null||getComputedStyle(e).display==='none'}})()"
    if cmd == "wait-text":
        t = _js(req.get("text", ""))
        return f"(()=>{{const e=document.querySelector({s});return e&&e.innerText.includes({t})}})()"
    if cmd == "wait-url":
        p = _js(req.get("pattern", ""))
        return f"location.href.includes({p})"
    return "false"


# --- Dispatcher ---


class Dispatcher:
    """Shared command dispatch for daemon and direct modes.

    Handles reconnection to Chrome when the browser WS drops.
    """

    DISPATCH_TIMEOUT = 30
    RECONNECT_DELAY = 1
    MAX_RECONNECT = 5
    IDLE_TIMEOUT = int(os.environ.get("CHROMECTL_IDLE_TIMEOUT", 300))

    def __init__(self, host: str, port: int, ws_path: str | None, bc: BrowserConnection | None, user_data_dir: str | None = None):
        self.host = host
        self.port = port
        self.ws_path = ws_path
        self.bc = bc
        self.sessions: dict[str, FlatSession] = {}
        self._session_lock = asyncio.Lock()
        self._user_data_dir = user_data_dir
        self._connected = bc is not None
        self._last_success = time.time()
        self._last_request = time.time()
        self._dead = False

    async def close(self):
        for session in self.sessions.values():
            if isinstance(session, CDPConnection):
                try:
                    await session.__aexit__(None, None, None)
                except Exception:
                    pass
        self.sessions.clear()

    async def _reconnect(self) -> bool:
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
        async with self._session_lock:
            if self.ws_path and self.bc:
                if target_id not in self.sessions:
                    self.sessions[target_id] = await self.bc.attach_to_target(target_id)
                return self.sessions[target_id]
            if target_id not in self.sessions:
                ws_url = await find_ws_for_target_http(self.host, self.port, target_id)
                conn = CDPConnection(ws_url)
                await conn.__aenter__()
                self.sessions[target_id] = conn
            return self.sessions[target_id]

    async def _resolve_target(self, partial_id: str) -> str:
        """Resolve partial target ID prefix to full 32-char ID."""
        if len(partial_id) >= 32:
            return partial_id.upper()
        partial_upper = partial_id.upper()
        if self.ws_path and self.bc:
            targets = await self.bc.list_targets()
            matches = [t["targetId"] for t in targets if t["targetId"].startswith(partial_upper)]
        else:
            targets = await list_targets_http(self.host, self.port)
            matches = [t["id"] for t in targets if t["id"].startswith(partial_upper)]
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise CDPError(f"No target matching '{partial_id}'")
        raise CDPError(f"Ambiguous: '{partial_id}' matches {len(matches)} targets")

    async def dispatch_safe(self, req: dict) -> dict:
        cmd = req.get("cmd", "")
        timeout = self.DISPATCH_TIMEOUT
        if cmd in _WAIT_COMMANDS:
            timeout = float(req.get("timeout", 10)) + 5
        elif cmd == "console-tail":
            timeout = float(req.get("for", 10)) + 5
        try:
            result = await asyncio.wait_for(self.dispatch(req), timeout=timeout)
            self._last_success = time.time()
            return result
        except (asyncio.TimeoutError, CDPError, aiohttp.ClientError, ConnectionError, OSError) as e:
            err_type = type(e).__name__
            if isinstance(e, asyncio.TimeoutError) or "close" in str(e).lower() or "connect" in str(e).lower():
                self.sessions.clear()
                if await self._reconnect():
                    try:
                        result = await asyncio.wait_for(self.dispatch(req), timeout=timeout)
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

        # --- No target needed ---

        if cmd in ("list", "targets"):
            return await self._dispatch_list(req, cmd)
        if cmd == "open":
            return await self._dispatch_open(req)
        if cmd == "status":
            return self._dispatch_status()
        if cmd == "cdp":
            return await self._dispatch_cdp(req)

        # --- Target commands ---

        raw_id = req.get("id")
        if not raw_id:
            return {"error": "Missing target ID"}
        try:
            target_id = await self._resolve_target(raw_id)
        except CDPError as e:
            return {"error": str(e)}

        if cmd == "eval":
            return await self._dispatch_eval(req, target_id)
        if cmd == "screenshot":
            return await self._dispatch_screenshot(req, target_id)
        if cmd == "console-tail":
            return await self._dispatch_console_tail(req, target_id)
        if cmd == "worker-eval":
            return await self._dispatch_worker_eval(req, target_id)
        if cmd == "navigate":
            return await self._dispatch_navigate(req, target_id)
        if cmd == "reload":
            return await self._dispatch_reload(target_id)
        if cmd in _WAIT_COMMANDS:
            return await self._dispatch_wait(req, target_id)
        if cmd in _HELPER_COMMANDS:
            js = _build_helper_js(cmd, req)
            if js is not None:
                return await self._eval_helper(target_id, js)
            return {"error": f"Invalid arguments for {cmd}"}

        return {"error": f"Unknown command: {cmd}. Run 'chromectl helpers' for available commands."}

    # --- Dispatch methods ---

    async def _dispatch_list(self, req: dict, cmd: str) -> dict:
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

    async def _dispatch_open(self, req: dict) -> dict:
        url = req.get("url", "about:blank")
        if self.ws_path and self.bc:
            return await self.bc.create_target(url)
        res = await new_tab_http(self.host, self.port, url)
        return {"id": res.get("id"), "url": res.get("url")}

    def _dispatch_status(self) -> dict:
        return {
            "connected": self._connected,
            "mode": "auto-connect" if self.ws_path else "http",
            "port": self.port,
            "sessions": len(self.sessions),
            "pid": os.getpid(),
        }

    async def _dispatch_cdp(self, req: dict) -> dict:
        method = req.get("method", "")
        params = req.get("params")
        if not method:
            return {"error": "Missing 'method'"}
        if self.bc and self.bc._conn:
            result = await self.bc._conn.send(method, params)
            return {"result": result}
        return {"error": "No browser connection (auto-connect only)"}

    async def _dispatch_eval(self, req: dict, target_id: str) -> dict:
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

    async def _dispatch_screenshot(self, req: dict, target_id: str) -> dict:
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
        if req.get("full_page"):
            await session.send("Emulation.clearDeviceMetricsOverride")
        b64 = result.get("data")
        if not b64:
            return {"error": "No screenshot data"}
        out = req.get("output", f"screenshot_{target_id}.png")
        data = base64.b64decode(b64)
        with open(out, "wb") as f:
            f.write(data)
        return {"file": out, "bytes": len(data)}

    async def _dispatch_console_tail(self, req: dict, target_id: str) -> dict:
        duration = float(req.get("for", 10))
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
                messages.append({"t": tdelta, "level": entry.get("level"), "source": entry.get("source"), "text": entry.get("text")})
            elif method == "Runtime.consoleAPICalled":
                vals = [a.get("value", a.get("description", a.get("type"))) for a in params.get("args", [])]
                messages.append({"t": tdelta, "console": params.get("type"), "args": vals})

        session.set_event_handler(console_handler)
        await asyncio.sleep(duration)
        session.set_event_handler(None)
        return {"messages": messages}

    async def _dispatch_worker_eval(self, req: dict, target_id: str) -> dict:
        expr = req.get("expr", "")
        if not self.bc or not self.bc._conn:
            return {"error": "No browser connection"}
        async with self._session_lock:
            if target_id not in self.sessions:
                result = await self.bc._conn.send(
                    "Target.attachToTarget",
                    {"targetId": target_id, "flatten": True},
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

    async def _dispatch_navigate(self, req: dict, target_id: str) -> dict:
        url = req.get("url", "")
        if not url:
            return {"error": "Missing URL"}
        session = await self.get_session(target_id)
        await session.send("Page.enable")
        result = await session.send("Page.navigate", {"url": url})
        return {"value": {"frameId": result.get("frameId"), "url": url}}

    async def _dispatch_reload(self, target_id: str) -> dict:
        session = await self.get_session(target_id)
        await session.send("Page.enable")
        await session.send("Page.reload")
        return {"value": True}

    async def _eval_helper(self, target_id: str, js_expr: str) -> dict:
        session = await self.get_session(target_id)
        await session.send("Runtime.enable")
        result = await session.send(
            "Runtime.evaluate",
            {
                "expression": js_expr,
                "returnByValue": True,
                "awaitPromise": True,
                "replMode": True,
            },
        )
        if "exceptionDetails" in result:
            return {"error": result["exceptionDetails"]}
        r = result.get("result", {})
        return {"value": r["value"]} if "value" in r else {"result": r}

    async def _dispatch_wait(self, req: dict, target_id: str) -> dict:
        timeout = float(req.get("timeout", 10))
        check_js = _build_wait_js(req["cmd"], req)
        session = await self.get_session(target_id)
        await session.send("Runtime.enable")
        start = time.time()
        while time.time() - start < timeout:
            result = await session.send(
                "Runtime.evaluate",
                {"expression": check_js, "returnByValue": True},
            )
            if "exceptionDetails" in result:
                return {"error": f"Evaluation failed (page may have navigated): {result['exceptionDetails']}", "command": req["cmd"]}
            r = result.get("result", {})
            if r.get("value"):
                return {"value": True, "elapsed": round(time.time() - start, 2)}
            await asyncio.sleep(0.25)
        return {"error": f"Timeout after {timeout}s", "command": req["cmd"]}


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


# --- CLI commands ---


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


SOCKET_PATH = f"/tmp/chromectl-{os.getuid()}.sock"


async def cmd_stop(args):
    import subprocess

    stopped_anything = False

    if os.path.exists(SOCKET_PATH):
        try:
            reader, writer = await asyncio.open_unix_connection(SOCKET_PATH)
            writer.write(b'{"cmd":"quit"}\n')
            await writer.drain()
            await asyncio.wait_for(reader.readline(), timeout=5)
            writer.close()
            await writer.wait_closed()
            print("Daemon stopped")
            stopped_anything = True
        except Exception as e:
            print(f"Warning: could not stop daemon: {e}", file=sys.stderr)

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


async def cmd_start(args):
    """Connect to Chrome and listen on Unix socket."""
    args.auto_connect = True
    dispatcher, bc = await make_dispatcher(args)

    if os.path.exists(SOCKET_PATH):
        os.unlink(SOCKET_PATH)

    async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            data = await asyncio.wait_for(reader.readline(), timeout=30)
            if not data:
                return
            line = data.decode().strip()
            if not line:
                return
            try:
                req = json.loads(line)
            except json.JSONDecodeError as e:
                writer.write(json.dumps({"error": f"Invalid JSON: {e}"}).encode() + b"\n")
                await writer.drain()
                return

            if req.get("cmd") == "quit":
                writer.write(json.dumps({"status": "bye"}).encode() + b"\n")
                await writer.drain()
                server.close()
                return

            dispatcher._last_request = time.time()
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
            await writer.wait_closed()

    server = await asyncio.start_unix_server(handle_client, path=SOCKET_PATH, limit=_STREAM_LIMIT)
    os.chmod(SOCKET_PATH, 0o600)
    print(f"chromectl daemon listening on {SOCKET_PATH} (PID {os.getpid()})", flush=True)
    print(f'Usage: echo \'{{"cmd":"list"}}\' | nc -U {SOCKET_PATH}', flush=True)

    async def idle_watchdog():
        liveness_counter = 0
        while True:
            await asyncio.sleep(5)
            if dispatcher._dead:
                print("CDP connection lost, shutting down", flush=True)
                server.close()
                return
            idle = time.time() - dispatcher._last_request
            if idle > dispatcher.IDLE_TIMEOUT:
                print(f"idle {idle:.0f}s, shutting down", flush=True)
                server.close()
                return
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

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, server.close)

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


# --- Request routing ---


HELPERS_TEXT = """\
Shorthands for common eval patterns. Selectors are CSS.

  click/check/uncheck/highlight SELECTOR
  submit/clear FORM
  type/fill SELECTOR TEXT
  select SELECTOR VALUE
  get-text/get-html/get-value/exists/count/get-texts SELECTOR
  get-attr SELECTOR ATTR
  scroll-to/wait-for/wait-hidden SELECTOR
  wait-text SELECTOR TEXT
  navigate URL
  wait-url PATTERN
  scroll-up/scroll-down [PIXELS]
  scroll-by X Y
  inject-css CSS
  reload/back/forward/get-title/get-url/scroll-top/scroll-bottom

  Wait: --timeout N (default 10s)

  For anything not covered:
    chromectl ABC123 eval "document.querySelector('x').doSomething()"

  Example: chromectl ABC123 click "button.submit"\
"""


_STREAM_LIMIT = 16 * 1024 * 1024  # 16MB — large eval results


def _format_output(result: dict) -> None:
    """Print daemon response in human-readable format."""
    if "error" in result:
        print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(2)
    if "targets" in result:
        for t in result["targets"]:
            print(f"{t.get('id', '')}  {t.get('url', '')}  {t.get('title', '')}")
    elif "file" in result:
        print(f"Saved {result.get('bytes', '?')} bytes to {result['file']}")
    elif "messages" in result:
        for m in result["messages"]:
            print(f"{m.get('t', '')}  {m.get('level', m.get('console', ''))}  {m.get('text', m.get('args', ''))}")
        print(f"({len(result['messages'])} messages)")
    elif "connected" in result:
        for k, v in result.items():
            print(f"{k}: {v}")
    elif "id" in result and "url" in result:
        print(f"{result['id']}  {result['url']}")
    elif "value" in result:
        val = result["value"]
        if isinstance(val, dict | list):
            print(json.dumps(val, indent=2, ensure_ascii=False))
        else:
            print(val)
    elif "result" in result:
        val = result["result"]
        if isinstance(val, dict | list):
            print(json.dumps(val, indent=2, ensure_ascii=False))
        else:
            print(val)
    elif "status" in result:
        print(result["status"])
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))


async def _daemon_request(req: dict, json_output: bool = False):
    """Send JSON request to daemon socket, print response."""
    reader, writer = await asyncio.open_unix_connection(SOCKET_PATH, limit=_STREAM_LIMIT)
    writer.write(json.dumps(req).encode() + b"\n")
    await writer.drain()
    resp = await asyncio.wait_for(reader.readline(), timeout=60)
    writer.close()
    await writer.wait_closed()

    if json_output:
        raw = resp.decode().strip()
        print(raw)
        if '"error"' in raw:
            sys.exit(2)
        return

    result = json.loads(resp.decode())
    _format_output(result)


async def _route_request(args, req: dict):
    """Route request to daemon socket."""
    if os.path.exists(SOCKET_PATH):
        json_output = getattr(args, "json_output", False)
        await _daemon_request(req, json_output=json_output)
        return
    print(f"No daemon running ({SOCKET_PATH} not found). Start with: chromectl start", file=sys.stderr)
    sys.exit(1)


async def _cmd_eval(args):
    await _route_request(args, {"cmd": "eval", "id": args.target_id, "expr": args.expression})


async def _cmd_worker_eval(args):
    await _route_request(args, {"cmd": "worker-eval", "id": args.target_id, "expr": args.expression})


async def _cmd_screenshot(args):
    req = {"cmd": "screenshot", "id": args.target_id, "output": args.output}
    if args.full_page:
        req["full_page"] = True
    await _route_request(args, req)


async def _cmd_console_tail(args):
    await _route_request(args, {"cmd": "console-tail", "id": args.target_id, "for": args.for_seconds})


async def _cmd_navigate(args):
    await _route_request(args, {"cmd": "navigate", "id": args.target_id, "url": args.url})


async def _cmd_reload(args):
    await _route_request(args, {"cmd": "reload", "id": args.target_id})


async def _cmd_dom_helper(args):
    req = {"cmd": args.helper_name, "id": args.target_id}
    for field in ("selector", "value", "text", "attr", "css", "pixels", "x", "y"):
        val = getattr(args, field, None)
        if val is not None:
            req[field] = val
    await _route_request(args, req)


async def _cmd_wait_helper(args):
    req = {"cmd": args.helper_name, "id": args.target_id}
    for field in ("selector", "text", "pattern"):
        val = getattr(args, field, None)
        if val is not None:
            req[field] = val
    if args.timeout:
        req["timeout"] = args.timeout
    await _route_request(args, req)


async def cmd_helpers(args):
    print(HELPERS_TEXT)


async def cmd_list_top(args):
    await _route_request(args, {"cmd": "list"})


async def cmd_open_top(args):
    await _route_request(args, {"cmd": "open", "url": args.url})


async def cmd_status_top(args):
    await _route_request(args, {"cmd": "status"})


async def cmd_targets_top(args):
    await _route_request(args, {"cmd": "targets"})


async def cmd_cdp_top(args):
    req = {"cmd": "cdp", "method": args.cdp_method}
    if args.params:
        req["params"] = json.loads(args.params)
    await _route_request(args, req)


# --- Parser ---


def build_parser():
    p = argparse.ArgumentParser(prog="chromectl", description="Control Chrome via DevTools Protocol (CDP).")
    p.add_argument("--host", default=DEFAULT_HOST)
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--auto-connect", action="store_true", help="Connect via DevToolsActivePort (Chrome M144+)")
    p.add_argument("--user-data-dir", default=None, help="Chrome user data directory")
    p.add_argument("--json", action="store_true", dest="json_output", help="Output raw JSON")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("start", help="Connect to Chrome, listen on Unix socket").set_defaults(func=cmd_start)
    sub.add_parser("stop", help="Stop daemon and Chrome instances").set_defaults(func=cmd_stop)
    sub.add_parser("list", help="List open tabs").set_defaults(func=cmd_list_top)

    sp = sub.add_parser("open", help="Open new tab")
    sp.add_argument("url", help="URL to open")
    sp.set_defaults(func=cmd_open_top)

    sub.add_parser("status", help="Daemon connection status").set_defaults(func=cmd_status_top)
    sub.add_parser("targets", help="List all targets (pages, workers, iframes)").set_defaults(func=cmd_targets_top)
    sub.add_parser("helpers", help="List DOM helper commands").set_defaults(func=cmd_helpers)

    sp = sub.add_parser("cdp", help="Send raw CDP command (browser-level)")
    sp.add_argument("cdp_method", metavar="METHOD", help="CDP method, e.g. Browser.getVersion")
    sp.add_argument("--params", help="Method params as JSON")
    sp.set_defaults(func=cmd_cdp_top)

    # Target commands
    sp = sub.add_parser("eval", help="Evaluate JavaScript")
    sp.add_argument("target_id", metavar="TARGET", help="Target ID from list/open (prefix match OK)")
    sp.add_argument("expression", metavar="EXPR", help="JavaScript expression")
    sp.set_defaults(func=_cmd_eval)

    sp = sub.add_parser("worker-eval", help="Evaluate JavaScript in service worker")
    sp.add_argument("target_id", metavar="TARGET", help="Worker target ID")
    sp.add_argument("expression", metavar="EXPR", help="JavaScript expression")
    sp.set_defaults(func=_cmd_worker_eval)

    sp = sub.add_parser("screenshot", help="Capture PNG screenshot")
    sp.add_argument("target_id", metavar="TARGET", help="Target ID from list/open (prefix match OK)")
    sp.add_argument("-o", "--output", default="screenshot.png", help="Output file (default: screenshot.png)")
    sp.add_argument("--full-page", action="store_true", help="Full-page screenshot")
    sp.set_defaults(func=_cmd_screenshot)

    sp = sub.add_parser("console-tail", help="Stream console messages")
    sp.add_argument("target_id", metavar="TARGET", help="Target ID from list/open (prefix match OK)")
    sp.add_argument("--for", dest="for_seconds", type=float, default=10, help="Duration in seconds (default: 10)")
    sp.set_defaults(func=_cmd_console_tail)

    sp = sub.add_parser("navigate", help="Navigate to URL")
    sp.add_argument("target_id", metavar="TARGET", help="Target ID from list/open (prefix match OK)")
    sp.add_argument("url", metavar="URL", help="URL to navigate to")
    sp.set_defaults(func=_cmd_navigate)

    sp = sub.add_parser("reload", help="Reload page")
    sp.add_argument("target_id", metavar="TARGET", help="Target ID from list/open (prefix match OK)")
    sp.set_defaults(func=_cmd_reload)

    # DOM helper subcommands
    _SELECTOR_ONLY = {
        "click",
        "check",
        "uncheck",
        "highlight",
        "submit",
        "clear",
        "get-text",
        "get-html",
        "get-value",
        "exists",
        "count",
        "get-texts",
        "scroll-to",
    }
    for helper in sorted(_HELPER_COMMANDS):
        sp = sub.add_parser(helper, help=f"DOM: {helper}")
        sp.add_argument("target_id", metavar="TARGET", help="Target ID from list/open (prefix match OK)")
        if helper in _SELECTOR_ONLY:
            sp.add_argument("selector", metavar="SELECTOR", help="CSS selector")
        elif helper == "fill":
            sp.add_argument("selector", metavar="SELECTOR", help="CSS selector")
            sp.add_argument("value", metavar="VALUE", help="Value to set")
        elif helper == "type":
            sp.add_argument("selector", metavar="SELECTOR", help="CSS selector")
            sp.add_argument("text", metavar="TEXT", help="Text to type")
        elif helper == "select":
            sp.add_argument("selector", metavar="SELECTOR", help="CSS selector")
            sp.add_argument("value", metavar="VALUE", help="Option value")
        elif helper == "get-attr":
            sp.add_argument("selector", metavar="SELECTOR", help="CSS selector")
            sp.add_argument("attr", metavar="ATTR", help="Attribute name")
        elif helper in ("scroll-up", "scroll-down"):
            sp.add_argument("pixels", nargs="?", type=int, default=None, help="Pixels (default: viewport)")
        elif helper == "scroll-by":
            sp.add_argument("x", type=int, help="Horizontal pixels")
            sp.add_argument("y", type=int, help="Vertical pixels")
        elif helper == "inject-css":
            sp.add_argument("css", metavar="CSS", help="CSS text to inject")
        sp.set_defaults(func=_cmd_dom_helper, helper_name=helper)

    # Wait commands
    for helper in sorted(_WAIT_COMMANDS):
        sp = sub.add_parser(helper, help=f"Wait: {helper}")
        sp.add_argument("target_id", metavar="TARGET", help="Target ID from list/open (prefix match OK)")
        if helper in ("wait-for", "wait-hidden"):
            sp.add_argument("selector", metavar="SELECTOR", help="CSS selector")
        elif helper == "wait-text":
            sp.add_argument("selector", metavar="SELECTOR", help="CSS selector")
            sp.add_argument("text", metavar="TEXT", help="Text to wait for")
        elif helper == "wait-url":
            sp.add_argument("pattern", metavar="PATTERN", help="URL substring")
        sp.add_argument("--timeout", type=float, default=10, help="Timeout in seconds (default: 10)")
        sp.set_defaults(func=_cmd_wait_helper, helper_name=helper)

    sp = sub.add_parser("launch", help="Launch separate Chrome instance (legacy)")
    sp.add_argument("--chrome-app", default="Google Chrome", help="macOS app name")
    sp.add_argument("--user-data-dir", default=None, help="Custom Chrome profile directory")
    sp.add_argument("--port", type=int, default=DEFAULT_PORT, help="Remote debugging port")
    sp.add_argument("--headless", action="store_true", help="Launch with --headless=new")
    sp.set_defaults(func=cmd_launch)

    return p


_KNOWN_COMMANDS = (
    {
        "start",
        "stop",
        "list",
        "open",
        "status",
        "targets",
        "helpers",
        "cdp",
        "launch",
        "eval",
        "worker-eval",
        "screenshot",
        "console-tail",
        "navigate",
        "reload",
    }
    | _HELPER_COMMANDS
    | _WAIT_COMMANDS
)
_FLAGS_WITH_VALUE = {"--host", "--port", "--user-data-dir"}


def _preprocess_argv():
    """If first positional arg isn't a known command, rewrite for TARGET COMMAND shorthand."""
    argv = sys.argv[1:]
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in _FLAGS_WITH_VALUE:
            i += 2
        elif arg.startswith("-"):
            i += 1
        else:
            if arg not in _KNOWN_COMMANDS:
                if i + 1 < len(argv) and argv[i + 1] in _KNOWN_COMMANDS:
                    target = argv[i]
                    cmd = argv[i + 1]
                    rest = argv[i + 2 :]
                    argv = argv[:i] + [cmd, target] + rest
            break
    sys.argv = [sys.argv[0]] + argv


async def amain():
    _preprocess_argv()
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
    except asyncio.TimeoutError:
        print("Timeout waiting for CDP response", file=sys.stderr)
        sys.exit(2)


def main():
    asyncio.run(amain())


if __name__ == "__main__":
    main()
