#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "aiohttp>=3.9",
# ]
# ///
# Copyright (c) 2026 Ville Reijonen. All rights reserved.
# Licensed under the MIT License. See LICENSE file for details.
"""firefoxctl — control Firefox via WebDriver BiDi from the command line.

⚠️  TEST TOOL — Firefox sets navigator.webdriver=true on any remote debugging
session (Bug 1719505, Firefox 101+). Every anti-bot system can detect this.
Mozilla painted themselves into a corner: no extension-based automation API
(unlike Chrome's chrome.debugger), no runtime enable (must launch with flag),
and the webdriver flag. This tool proves BiDi works. For production agent
workflows, use chromectl instead.

Requires Firefox launched with: firefox --remote-debugging-port <port>
Daemon starts automatically on first command (no explicit 'start' needed).

Commands:
  list                    List open tabs
  eval <ctx> <expr>       Evaluate JavaScript in a browsing context
  screenshot <ctx> [-o f] Capture viewport screenshot
  navigate <ctx> <url>    Navigate to URL
  30+ DOM helpers         click, type, scroll, wait, and more (run 'helpers')
  bidi <method> [params]  Send raw BiDi command
"""

import argparse
import asyncio
import base64
import json
import os
import signal
import subprocess
import sys
import time
from typing import Any

import aiohttp
from injection_defense import sanitize_result

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9222


class BiDiError(RuntimeError):
    pass


class BiDiConnection:
    """WebDriver BiDi connection over WebSocket.

    Firefox speaks BiDi natively — no geckodriver needed.
    Connect to ws://host:port/session, send session.new, go.
    """

    def __init__(self, host: str, port: int):
        self.ws_url = f"ws://{host}:{port}/session"
        self._id = 0
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._http_session: aiohttp.ClientSession | None = None
        self._pending: dict[int, asyncio.Future] = {}
        self._event_handlers: dict[str, list] = {}
        self._recv_task: asyncio.Task | None = None
        self._session_id: str | None = None

    async def __aenter__(self):
        self._http_session = aiohttp.ClientSession()
        try:
            self._ws = await self._http_session.ws_connect(self.ws_url, autoclose=True, autoping=True)
        except aiohttp.ClientError as e:
            await self._http_session.close()
            raise BiDiError(
                f"Cannot connect to Firefox at {self.ws_url}\n"
                f"Start Firefox with: firefox --remote-debugging-port {DEFAULT_PORT}\n"
                f"Error: {e}"
            ) from e
        self._recv_task = asyncio.create_task(self._recv_loop())

        try:
            result = await asyncio.wait_for(self.send("session.new", {"capabilities": {}}), timeout=10)
            self._session_id = result.get("sessionId")
        except BiDiError as e:
            if "already started" in str(e).lower():
                await self._http_session.close()
                raise BiDiError(
                    "Firefox has a zombie BiDi session from a previous connection.\n"
                    "Restart Firefox to clear it:\n"
                    f"  pkill -f firefox && firefox --remote-debugging-port {DEFAULT_PORT}"
                ) from e
            raise
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._session_id and self._ws and not self._ws.closed:
            try:
                await self.send("session.end", {})
            except Exception:
                pass
        if self._recv_task:
            self._recv_task.cancel()
            try:
                await self._recv_task
            except asyncio.CancelledError:
                pass
        if self._ws and not self._ws.closed:
            await self._ws.close()
        if self._http_session:
            await self._http_session.close()

    async def _recv_loop(self):
        assert self._ws is not None
        try:
            async for msg in self._ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    msg_id = data.get("id")
                    if msg_id is not None and msg_id in self._pending:
                        fut = self._pending.pop(msg_id)
                        if not fut.done():
                            fut.set_result(data)
                    elif data.get("type") == "event":
                        method = data.get("method", "")
                        for handler in self._event_handlers.get(method, []):
                            try:
                                await handler(data)
                            except Exception:
                                pass
                elif msg.type in (aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSED):
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
        if resp.get("type") == "error":
            err = resp.get("error", "unknown")
            err_msg = resp.get("message", "")
            raise BiDiError(f"{method}: {err} — {err_msg}")
        return resp.get("result", {})

    def on_event(self, method: str, handler):
        self._event_handlers.setdefault(method, []).append(handler)

    async def subscribe(self, events: list[str]):
        await self.send("session.subscribe", {"events": events})


# --- Commands ---


async def cmd_list(conn: BiDiConnection) -> list[dict]:
    result = await conn.send("browsingContext.getTree", {})
    contexts = result.get("contexts", [])
    tabs = []
    for ctx in contexts:
        tabs.append({"context": ctx.get("context", ""), "url": ctx.get("url", "")})
    return tabs


def format_tabs(tabs: list[dict]) -> str:
    lines = []
    for t in tabs:
        ctx = t["context"]
        url = t.get("url", "")
        lines.append(f"{ctx}  {url}")
    return "\n".join(lines)


async def cmd_eval(conn: BiDiConnection, context: str, expression: str) -> Any:
    result = await conn.send(
        "script.evaluate",
        {
            "expression": expression,
            "target": {"context": context},
            "awaitPromise": True,
            "resultOwnership": "none",
            "serializationOptions": {"maxObjectDepth": 5, "maxDomDepth": 0},
        },
    )
    return _unpack_value(result.get("result", {}))


async def cmd_screenshot(conn: BiDiConnection, context: str) -> bytes:
    result = await conn.send(
        "browsingContext.captureScreenshot",
        {
            "context": context,
        },
    )
    data = result.get("data", "")
    return base64.b64decode(data)


async def cmd_navigate(conn: BiDiConnection, context: str, url: str) -> dict:
    result = await conn.send(
        "browsingContext.navigate",
        {
            "context": context,
            "url": url,
            "wait": "complete",
        },
    )
    return result


async def cmd_open(conn: BiDiConnection, url: str) -> dict:
    """Open a new tab, optionally navigating to url."""
    result = await conn.send("browsingContext.create", {"type": "tab"})
    context = result.get("context", "")
    if url and url != "about:blank":
        await conn.send(
            "browsingContext.navigate",
            {"context": context, "url": url, "wait": "complete"},
        )
    return {"context": context, "url": url}


def _js(s: str) -> str:
    """Escape a Python string as a JS string literal."""
    return json.dumps(s)


# Keep in sync with chrome-control/chromectl.py
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

# Keep in sync with chrome-control/chromectl.py
_WAIT_COMMANDS = {"wait-for", "wait-text", "wait-url", "wait-hidden"}

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


def _build_helper_js(cmd: str, req: dict) -> str | None:
    # Keep in sync with chrome-control/chromectl.py
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
    # Keep in sync with chrome-control/chromectl.py
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


async def cmd_dom_helper(conn: BiDiConnection, context: str, helper: str, req: dict) -> Any:
    """Run a DOM helper via script.evaluate."""
    expr = _build_helper_js(helper, req)
    if expr is None:
        raise BiDiError(f"Unknown helper: {helper}")
    return await cmd_eval(conn, context, expr)


async def cmd_wait_helper(conn: BiDiConnection, context: str, helper: str, req: dict, timeout: float = 10) -> bool:
    """Poll a wait condition until true or timeout."""
    check_js = _build_wait_js(helper, req)
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = await cmd_eval(conn, context, check_js)
        if result:
            return True
        await asyncio.sleep(0.25)
    raise BiDiError(f"Timeout after {timeout}s waiting for {helper}")


async def cmd_bidi_raw(conn: BiDiConnection, method: str, params_json: str | None) -> Any:
    params = json.loads(params_json) if params_json else {}
    return await conn.send(method, params)


# --- Value unpacking ---


def _unpack_value(val: dict) -> Any:
    """Convert BiDi typed value to Python native."""
    vtype = val.get("type", "")
    if vtype in ("undefined", "null"):
        return None
    if vtype in ("string", "boolean"):
        return val.get("value")
    if vtype == "number":
        v = val.get("value")
        if v == "NaN":
            return float("nan")
        if v == "Infinity":
            return float("inf")
        if v == "-Infinity":
            return float("-inf")
        if v == "-0":
            return -0.0
        return v
    if vtype == "bigint":
        return int(val.get("value", "0"))
    if vtype == "array":
        return [_unpack_value(item) for item in val.get("value", [])]
    if vtype == "object":
        return {_unpack_value(kv[0]) if isinstance(kv[0], dict) else kv[0]: _unpack_value(kv[1]) for kv in val.get("value", [])}
    if vtype == "map":
        return {_unpack_value(kv[0]) if isinstance(kv[0], dict) else kv[0]: _unpack_value(kv[1]) for kv in val.get("value", [])}
    if vtype == "set":
        return [_unpack_value(item) for item in val.get("value", [])]
    if vtype == "node":
        return val.get("value", val)
    if vtype == "window":
        return val.get("value", val)
    if vtype == "regexp":
        return val.get("value", val)
    if vtype == "date":
        return val.get("value", "")
    if vtype == "error":
        return {"error": val.get("value", val)}
    return val


# --- Daemon ---


SOCKET_PATH = f"/tmp/firefoxctl-{os.getuid()}.sock"
_STREAM_LIMIT = 16 * 1024 * 1024
IDLE_TIMEOUT = int(os.environ.get("FIREFOXCTL_IDLE_TIMEOUT", 300))


async def _resolve_context(conn: BiDiConnection, partial: str) -> str:
    """Resolve partial context ID prefix to full UUID."""
    if "-" in partial and len(partial) >= 36:
        return partial
    result = await conn.send("browsingContext.getTree", {})
    contexts = [ctx.get("context", "") for ctx in result.get("contexts", [])]
    matches = [c for c in contexts if c.startswith(partial)]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise BiDiError(f"No context matching '{partial}'")
    raise BiDiError(f"Ambiguous: '{partial}' matches {len(matches)} contexts")


async def _dispatch(conn: BiDiConnection, req: dict) -> dict:
    """Route a JSON request to the appropriate command."""
    cmd = req.get("cmd", "")

    if cmd == "list":
        tabs = await cmd_list(conn)
        return {"contexts": tabs}

    if cmd == "bidi":
        method = req.get("method")
        if not method:
            return {"error": "Missing 'method'"}
        result = await cmd_bidi_raw(conn, method, req.get("params"))
        return {"result": result}

    if cmd == "open":
        url = req.get("url", "about:blank")
        return await cmd_open(conn, url)

    if cmd == "status":
        port = conn.ws_url.split(":")[2].split("/")[0] if conn.ws_url else 0
        return {
            "connected": True,
            "port": int(port),
            "session_id": conn._session_id,
            "pid": os.getpid(),
        }

    if cmd == "targets":
        result = await conn.send("browsingContext.getTree", {})
        flat: list[dict] = []

        def flatten(ctx: dict, depth: int = 0) -> None:
            flat.append(
                {
                    "context": ctx.get("context", ""),
                    "url": ctx.get("url", ""),
                    "type": "tab" if depth == 0 else "iframe",
                }
            )
            for child in ctx.get("children", []):
                flatten(child, depth + 1)

        for ctx in result.get("contexts", []):
            flatten(ctx)
        return {"targets": flat}

    # All remaining commands need a context
    raw_context = req.get("context")
    if not raw_context:
        return {"error": "Missing context ID"}
    context = await _resolve_context(conn, raw_context)

    if cmd == "console-tail":
        duration = float(req.get("for", 10))
        messages: list[dict] = []
        start_ts = time.time()

        async def _log_handler(data: dict) -> None:
            params = data.get("params", {})
            tdelta = f"+{time.time() - start_ts:0.3f}s"
            entry = params.get("entry", params)
            messages.append(
                {
                    "t": tdelta,
                    "level": entry.get("level", ""),
                    "text": entry.get("text", ""),
                }
            )

        conn.on_event("log.entryAdded", _log_handler)
        await conn.subscribe(["log.entryAdded"])
        try:
            await asyncio.sleep(duration)
        finally:
            handlers = conn._event_handlers.get("log.entryAdded", [])
            if _log_handler in handlers:
                handlers.remove(_log_handler)
        return {"messages": messages}

    if cmd == "eval":
        result = await cmd_eval(conn, context, req.get("expr", ""))
        return {"result": result}

    if cmd == "screenshot":
        data = await cmd_screenshot(conn, context)
        out = req.get("output", f"screenshot_{context[:8]}.png")
        with open(out, "wb") as f:
            f.write(data)
        return {"file": out, "bytes": len(data)}

    if cmd == "navigate":
        url = req.get("url", "")
        if not url:
            return {"error": "Missing URL"}
        result = await cmd_navigate(conn, context, url)
        return result

    if cmd == "reload":
        await conn.send("browsingContext.reload", {"context": context, "wait": "complete"})
        return {"result": True}

    if cmd in _HELPER_COMMANDS:
        result = await cmd_dom_helper(conn, context, cmd, req)
        return {"result": result}

    if cmd in _WAIT_COMMANDS:
        timeout = req.get("timeout", 10)
        result = await cmd_wait_helper(conn, context, cmd, req, timeout)
        return {"result": result}

    return {"error": f"Unknown command: {cmd}"}


async def _dispatch_safe(conn: BiDiConnection, req: dict) -> dict:
    cmd = req.get("cmd", "")
    timeout = 30
    if cmd in _WAIT_COMMANDS:
        timeout = float(req.get("timeout", 10)) + 5
    try:
        return await asyncio.wait_for(_dispatch(conn, req), timeout=timeout)
    except BiDiError as e:
        return {"error": f"BiDi: {e}"}
    except asyncio.TimeoutError:
        return {"error": "Timeout"}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


async def cmd_start(args):
    """Start daemon: persistent BiDi connection, Unix socket interface."""
    host, port = args.host, args.port

    if os.path.exists(SOCKET_PATH):
        try:
            r, w = await asyncio.wait_for(asyncio.open_unix_connection(SOCKET_PATH), timeout=5)
            w.write(b'{"cmd":"status"}\n')
            await w.drain()
            await asyncio.wait_for(r.readline(), timeout=2)
            w.close()
            await w.wait_closed()
            print(f"Daemon already running on {SOCKET_PATH}", file=sys.stderr)
            sys.exit(1)
        except Exception:
            print(f"Removing stale socket {SOCKET_PATH}", flush=True)
            os.unlink(SOCKET_PATH)

    conn = BiDiConnection(host, port)
    await conn.__aenter__()

    last_request = time.time()
    _dead = False
    _reconnect_lock = asyncio.Lock()

    async def _reconnect() -> bool:
        nonlocal conn, _dead
        async with _reconnect_lock:
            try:
                await conn.__aexit__(None, None, None)
            except Exception:
                pass
            for attempt in range(1, 6):
                try:
                    conn = BiDiConnection(host, port)
                    await conn.__aenter__()
                    print(f"reconnected to Firefox (attempt {attempt})", flush=True)
                    return True
                except BiDiError as e:
                    if "already started" in str(e).lower():
                        print("zombie BiDi session — restart Firefox", flush=True)
                        _dead = True
                        return False
                    print(f"reconnect attempt {attempt}/5 failed: {e}", flush=True)
                except Exception as e:
                    print(f"reconnect attempt {attempt}/5 failed: {e}", flush=True)
                if attempt < 5:
                    await asyncio.sleep(1)
            _dead = True
            return False

    async def _dispatch_safe_daemon(req: dict) -> dict:
        nonlocal _dead
        cmd = req.get("cmd", "")
        timeout = 30
        if cmd in _WAIT_COMMANDS:
            timeout = float(req.get("timeout", 10)) + 5
        elif cmd == "console-tail":
            timeout = float(req.get("for", 10)) + 5
        try:
            result = await asyncio.wait_for(_dispatch(conn, req), timeout=timeout)
            return sanitize_result(result)
        except (aiohttp.ClientError, ConnectionError, OSError) as e:
            print(f"transport error: {type(e).__name__}: {e}", flush=True)
            if await _reconnect():
                try:
                    result = await asyncio.wait_for(_dispatch(conn, req), timeout=timeout)
                    return sanitize_result(result)
                except Exception as e2:
                    _dead = True
                    return sanitize_result({"error": f"{type(e2).__name__}: {e2} (after reconnect)"})
            return sanitize_result({"error": f"BiDi connection lost: {type(e).__name__}: {e}"})
        except BiDiError as e:
            return sanitize_result({"error": f"BiDi: {e}"})
        except asyncio.TimeoutError:
            return {"error": "Timeout"}
        except Exception as e:
            return sanitize_result({"error": f"{type(e).__name__}: {e}"})

    async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        nonlocal last_request
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

            last_request = time.time()
            result = await _dispatch_safe_daemon(req)
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
    print(f"firefoxctl daemon listening on {SOCKET_PATH} (PID {os.getpid()})", flush=True)
    print(f'Usage: echo \'{{"cmd":"list"}}\' | nc -U {SOCKET_PATH}', flush=True)
    print("⚠️  Reminder: navigator.webdriver=true in this Firefox session", flush=True)

    async def idle_watchdog():
        nonlocal _dead
        liveness_counter = 0
        while True:
            await asyncio.sleep(5)
            if _dead:
                print("BiDi connection lost, shutting down", flush=True)
                server.close()
                return
            if not os.path.exists(SOCKET_PATH):
                print("socket removed, shutting down", flush=True)
                server.close()
                return
            idle = time.time() - last_request
            if idle > IDLE_TIMEOUT:
                print(f"idle {idle:.0f}s, shutting down", flush=True)
                server.close()
                return
            liveness_counter += 1
            if liveness_counter >= 6 and idle > 10:
                liveness_counter = 0
                try:
                    await asyncio.wait_for(conn.send("session.status", {}), timeout=5)
                except Exception as e:
                    print(f"liveness probe failed: {type(e).__name__}: {e}", flush=True)
                    if not await _reconnect():
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
        try:
            await conn.__aexit__(None, None, None)
        except Exception:
            pass
        print("daemon stopped", flush=True)


async def cmd_stop(args):
    """Stop the daemon."""
    if not os.path.exists(SOCKET_PATH):
        print("No daemon running")
        return
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_unix_connection(SOCKET_PATH), timeout=5)
        writer.write(b'{"cmd":"quit"}\n')
        await writer.drain()
        await asyncio.wait_for(reader.readline(), timeout=5)
        writer.close()
        await writer.wait_closed()
        print("Daemon stopped")
    except Exception:
        print("Daemon not responding, removing stale socket", file=sys.stderr)
        os.unlink(SOCKET_PATH)


async def _send_to_daemon(req: dict) -> dict:
    """Send a command to the running daemon via Unix socket."""
    reader, writer = await asyncio.wait_for(asyncio.open_unix_connection(SOCKET_PATH, limit=_STREAM_LIMIT), timeout=5)
    try:
        writer.write(json.dumps(req).encode() + b"\n")
        await writer.drain()
        response = await asyncio.wait_for(reader.readline(), timeout=60)
    finally:
        writer.close()
        await writer.wait_closed()
    return json.loads(response.decode())


def _daemon_running() -> bool:
    return os.path.exists(SOCKET_PATH)


async def _auto_start_daemon(args):
    """Fork a daemon process and wait for socket to appear."""
    script = os.path.abspath(__file__)
    cmd = ["uv", "run", script, "--host", args.host, "--port", str(args.port), "start"]
    print(f"Starting daemon on port {args.port}...", file=sys.stderr, flush=True)
    log = os.path.join(os.path.dirname(SOCKET_PATH), f"firefoxctl-{os.getuid()}.log")
    with open(log, "w") as log_fh:
        proc = subprocess.Popen(cmd, stdout=log_fh, stderr=log_fh, start_new_session=True)
        for _ in range(20):
            await asyncio.sleep(0.5)
            if proc.poll() is not None:
                break
            if os.path.exists(SOCKET_PATH):
                try:
                    r, w = await asyncio.wait_for(asyncio.open_unix_connection(SOCKET_PATH), timeout=5)
                    w.write(b'{"cmd":"status"}\n')
                    await w.drain()
                    await asyncio.wait_for(r.readline(), timeout=2)
                    w.close()
                    await w.wait_closed()
                    return
                except Exception:
                    continue
    with open(log) as f:
        print(f.read(), file=sys.stderr, end="")
    print("Daemon failed to start within 10s", file=sys.stderr)
    sys.exit(1)


async def _route_request(args, req: dict):
    """Route request to daemon. Auto-starts daemon if needed."""
    if not _daemon_running():
        await _auto_start_daemon(args)

    result = await _send_to_daemon(req)

    json_output = getattr(args, "json_output", False)
    if json_output:
        print(json.dumps(result, ensure_ascii=False))
        if "error" in result:
            sys.exit(2)
        return

    if "error" in result:
        print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(2)

    # Format output
    if "contexts" in result:
        print(format_tabs(result["contexts"]))
    elif "targets" in result:
        for t in result["targets"]:
            print(f"{t.get('context', '')}  {t.get('type', '')}  {t.get('url', '')}")
    elif "file" in result:
        print(f"Saved {result.get('bytes', '?')} bytes to {result['file']}")
    elif "messages" in result:
        for m in result["messages"]:
            print(f"{m.get('t', '')}  {m.get('level', '')}  {m.get('text', '')}")
        print(f"({len(result['messages'])} messages)")
    elif "connected" in result:
        for k, v in result.items():
            print(f"{k}: {v}")
    elif "context" in result and "url" in result:
        print(f"{result['context']}  {result['url']}")
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


# --- CLI ---


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
    firefoxctl CONTEXT eval "document.querySelector('x').doSomething()"

  Example: firefoxctl CONTEXT click "button.submit"\
"""


def build_parser():
    p = argparse.ArgumentParser(
        prog="firefoxctl",
        description=(
            "Control Firefox via WebDriver BiDi.\n\n"
            "⚠️  TEST TOOL: Firefox sets navigator.webdriver=true on remote\n"
            "debugging sessions. For production agent work, use chromectl."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--host", default=DEFAULT_HOST)
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--json", action="store_true", dest="json_output", help="Output raw JSON")

    sub = p.add_subparsers(dest="cmd", required=True)

    # Global commands
    sub.add_parser("start", help="Start daemon (persistent BiDi connection)").set_defaults(func=_cmd_start)
    sub.add_parser("stop", help="Stop daemon").set_defaults(func=_cmd_stop)
    sub.add_parser("list", help="List open tabs").set_defaults(func=_cmd_list)

    sp = sub.add_parser("open", help="Open new tab")
    sp.add_argument("url", metavar="URL", help="URL to open")
    sp.set_defaults(func=_cmd_open)

    sub.add_parser("status", help="Daemon connection status").set_defaults(func=_cmd_status)
    sub.add_parser("targets", help="List all targets (tabs, iframes)").set_defaults(func=_cmd_targets)
    sub.add_parser("helpers", help="List DOM helper commands").set_defaults(func=_cmd_helpers)

    sp = sub.add_parser("bidi", help="Send raw BiDi command")
    sp.add_argument("method", metavar="METHOD", help="BiDi method (e.g. browser.getClientWindows)")
    sp.add_argument("--params", help="Method params as JSON")
    sp.set_defaults(func=_cmd_bidi)

    # Target commands
    sp = sub.add_parser("eval", help="Evaluate JavaScript")
    sp.add_argument("context", metavar="CONTEXT", help="Browsing context ID from list")
    sp.add_argument("expression", metavar="EXPR", help="JavaScript expression")
    sp.set_defaults(func=_cmd_eval)

    sp = sub.add_parser("screenshot", help="Capture viewport screenshot")
    sp.add_argument("context", metavar="CONTEXT", help="Browsing context ID from list")
    sp.add_argument("-o", "--output", default="screenshot.png", help="Output file (default: screenshot.png)")
    sp.set_defaults(func=_cmd_screenshot)

    sp = sub.add_parser("console-tail", help="Stream console messages")
    sp.add_argument("context", metavar="CONTEXT", help="Browsing context ID")
    sp.add_argument("--for", dest="for_seconds", type=float, default=10, help="Duration in seconds (default: 10)")
    sp.set_defaults(func=_cmd_console_tail)

    sp = sub.add_parser("navigate", help="Navigate to URL")
    sp.add_argument("context", metavar="CONTEXT", help="Browsing context ID from list")
    sp.add_argument("url", metavar="URL", help="URL to navigate to")
    sp.set_defaults(func=_cmd_navigate)

    sp = sub.add_parser("reload", help="Reload page")
    sp.add_argument("context", metavar="CONTEXT", help="Browsing context ID from list")
    sp.set_defaults(func=_cmd_reload)

    # DOM helper subcommands
    for helper in sorted(_HELPER_COMMANDS):
        sp = sub.add_parser(helper, help=f"DOM: {helper}")
        sp.add_argument("context", metavar="CONTEXT", help="Browsing context ID")
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
        sp.add_argument("context", metavar="CONTEXT", help="Browsing context ID")
        if helper in ("wait-for", "wait-hidden"):
            sp.add_argument("selector", metavar="SELECTOR", help="CSS selector")
        elif helper == "wait-text":
            sp.add_argument("selector", metavar="SELECTOR", help="CSS selector")
            sp.add_argument("text", metavar="TEXT", help="Text to wait for")
        elif helper == "wait-url":
            sp.add_argument("pattern", metavar="PATTERN", help="URL substring")
        sp.add_argument("--timeout", type=float, default=10, help="Timeout in seconds (default: 10)")
        sp.set_defaults(func=_cmd_wait_helper, helper_name=helper)

    return p


# Shorthand: firefoxctl <context> <command> ... → insert into subcommand form
_KNOWN_COMMANDS = (
    {"start", "stop", "list", "eval", "screenshot", "navigate", "reload", "bidi", "helpers", "open", "status", "targets", "console-tail"}
    | _HELPER_COMMANDS
    | _WAIT_COMMANDS
)
_FLAGS_WITH_VALUE = {"--host", "--port"}


def _preprocess_argv():
    """If first positional arg isn't a known command, rewrite for <context> <command> shorthand."""
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
                # argv[i] is context, argv[i+1] should be command
                if i + 1 < len(argv) and argv[i + 1] in _KNOWN_COMMANDS:
                    ctx = argv[i]
                    cmd = argv[i + 1]
                    rest = argv[i + 2 :]
                    argv = argv[:i] + [cmd, ctx] + rest
            break
    sys.argv = [sys.argv[0]] + argv


# --- Command handlers ---


async def _cmd_start(args):
    await cmd_start(args)


async def _cmd_stop(args):
    await cmd_stop(args)


async def _cmd_list(args):
    await _route_request(args, {"cmd": "list"})


async def _cmd_eval(args):
    await _route_request(args, {"cmd": "eval", "context": args.context, "expr": args.expression})


async def _cmd_screenshot(args):
    await _route_request(args, {"cmd": "screenshot", "context": args.context, "output": args.output})


async def _cmd_navigate(args):
    await _route_request(args, {"cmd": "navigate", "context": args.context, "url": args.url})


async def _cmd_reload(args):
    await _route_request(args, {"cmd": "reload", "context": args.context})


async def _cmd_bidi(args):
    req = {"cmd": "bidi", "method": args.method}
    if args.params:
        req["params"] = args.params
    await _route_request(args, req)


async def _cmd_open(args):
    await _route_request(args, {"cmd": "open", "url": args.url})


async def _cmd_status(args):
    if not _daemon_running():
        print("No daemon running")
        return
    await _route_request(args, {"cmd": "status"})


async def _cmd_targets(args):
    await _route_request(args, {"cmd": "targets"})


async def _cmd_console_tail(args):
    await _route_request(args, {"cmd": "console-tail", "context": args.context, "for": args.for_seconds})


async def _cmd_dom_helper(args):
    req = {"cmd": args.helper_name, "context": args.context}
    for field in ("selector", "value", "text", "attr", "css", "pixels", "x", "y"):
        v = getattr(args, field, None)
        if v is not None:
            req[field] = v
    await _route_request(args, req)


async def _cmd_wait_helper(args):
    req = {"cmd": args.helper_name, "context": args.context, "timeout": args.timeout}
    for field in ("selector", "text", "pattern"):
        v = getattr(args, field, None)
        if v is not None:
            req[field] = v
    await _route_request(args, req)


async def _cmd_helpers(_args):
    print(HELPERS_TEXT)


# --- Entry point ---


async def amain():
    _preprocess_argv()
    parser = build_parser()
    args = parser.parse_args()
    try:
        await args.func(args)
    except BiDiError as e:
        print(f"BiDi error: {e}", file=sys.stderr)
        sys.exit(2)
    except aiohttp.ClientError as e:
        print(f"WebSocket error: {e}", file=sys.stderr)
        sys.exit(2)
    except asyncio.TimeoutError:
        print("Timeout waiting for BiDi response", file=sys.stderr)
        sys.exit(2)


def main():
    asyncio.run(amain())


if __name__ == "__main__":
    main()
