#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "aiohttp>=3.9",
# ]
# ///
"""chromectl — drive a local Chrome debugging instance via CDP using a uv-only, single-file script.

Commands:
  start                Launch a new Chrome with remote debugging enabled (macOS)
  stop                 Stop all chromectl-managed Chrome instances
  list                 List open tabs/targets
  open <url>           Open a new tab at URL, print its targetId
  eval  --id <id>  -e <js>         Evaluate JavaScript in the target context
  screenshot --id <id> [-o file]   Capture a PNG screenshot of the page
  console-tail --id <id> [--for SECONDS]   Stream console/log messages
"""

import argparse
import asyncio
import base64
import json
import os
import sys
import time
from typing import Any

import aiohttp

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9222


class CDPError(RuntimeError):
    pass


async def http_get_json(session: aiohttp.ClientSession, url: str) -> Any:
    async with session.get(url) as resp:
        resp.raise_for_status()
        return await resp.json()


async def list_targets(host: str, port: int) -> Any:
    async with aiohttp.ClientSession() as session:
        async with session.get(f"http://{host}:{port}/json") as resp:
            resp.raise_for_status()
            return await resp.json()


async def new_tab(host: str, port: int, url: str) -> Any:
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

    async def __aenter__(self):
        self._session = aiohttp.ClientSession()
        self._ws = await self._session.ws_connect(self.ws_url, autoclose=True, autoping=True)
        self._recv_task = asyncio.create_task(self._recv_loop())
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._ws is not None:
            await self._ws.close()
        await self._session.close()

    async def _recv_loop(self):
        assert self._ws is not None
        async for msg in self._ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                data = json.loads(msg.data)
                if "id" in data:
                    fut = self._pending.pop(data["id"], None)
                    if fut and not fut.done():
                        fut.set_result(data)
                else:
                    if self._event_handler:
                        await self._event_handler(data)
            elif msg.type == aiohttp.WSMsgType.ERROR:
                break

    async def send(self, method: str, params: dict[str, Any] | None = None) -> Any:
        self._id += 1
        msg = {"id": self._id, "method": method}
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


async def find_ws_for_target(host: str, port: int, target_id: str) -> str:
    targets = await list_targets(host, port)
    for t in targets:
        if t.get("id") == target_id:
            return t["webSocketDebuggerUrl"]
    raise CDPError(f"Target {target_id} not found. Use `chromectl list`.")


async def attach_to_target(host: str, port: int, target_id: str) -> CDPConnection:
    ws_url = await find_ws_for_target(host, port, target_id)
    return CDPConnection(ws_url)


# --- Commands ---


async def cmd_start(args):
    chrome_app = args.chrome_app or "Google Chrome"
    user_data_dir = args.user_data_dir or os.path.expanduser("~/chromectl-profile")
    os.makedirs(user_data_dir, exist_ok=True)
    port = args.port

    # Resolve Chrome binary path
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
    # Don't wait - let it run in background
    print(f"Chrome launched (PID: {proc.pid}) with remote debugging on port {port}")
    print(f"Profile directory: {user_data_dir}")


async def cmd_list(args):
    targets = await list_targets(args.host, args.port)
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
    res = await new_tab(args.host, args.port, args.url)
    print(json.dumps({"id": res.get("id"), "url": res.get("url")}, ensure_ascii=False))


async def cmd_eval(args):
    async with await attach_to_target(args.host, args.port, args.id) as conn:
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
    async with await attach_to_target(args.host, args.port, args.id) as conn:
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
    async with await attach_to_target(args.host, args.port, args.id) as conn:
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
                args = params.get("args", [])
                vals = []
                for a in args:
                    if "value" in a:
                        vals.append(a["value"])
                    else:
                        vals.append(a.get("description") or a.get("type"))
                print(json.dumps({"t": tdelta, "console": typ, "args": vals}, ensure_ascii=False))

        conn.set_event_handler(handler)
        duration = float(args.for_seconds)
        await asyncio.sleep(duration)


async def cmd_stop(args):
    import signal
    import subprocess

    # Find Chrome processes using chromectl profile directories
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

        if not pids_to_kill:
            print("No chromectl Chrome instances found running")
            return

        for pid, _line in pids_to_kill:
            print(f"Stopping Chrome instance (PID: {pid})")
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                print(f"  Process {pid} already stopped")
            except PermissionError:
                print(f"  Permission denied to stop process {pid}")

        if pids_to_kill:
            import time

            time.sleep(1)
            print(f"Stopped {len(pids_to_kill)} Chrome instance(s)")
    except Exception as e:
        print(f"Error stopping Chrome: {e}", file=sys.stderr)
        sys.exit(1)


def build_parser():
    p = argparse.ArgumentParser(prog="chromectl", description="Operate Chrome via DevTools Protocol (CDP) from the CLI.")
    p.add_argument("--host", default=DEFAULT_HOST)
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("start", help="Launch Chrome with remote debugging (macOS convenience)")
    sp.add_argument("--chrome-app", default="Google Chrome", help='macOS app name, e.g., "Google Chrome" or "Google Chrome Canary"')
    sp.add_argument("--user-data-dir", default=None, help="Custom Chrome profile directory to isolate sessions")
    sp.add_argument("--port", type=int, default=DEFAULT_PORT, help="Remote debugging port")
    sp.add_argument("--headless", action="store_true", help="Launch with --headless=new")
    sp.set_defaults(func=cmd_start)

    sp = sub.add_parser("stop", help="Stop all chromectl-managed Chrome instances")
    sp.set_defaults(func=cmd_stop)

    sp = sub.add_parser("list", help="List open tabs/targets")
    sp.set_defaults(func=cmd_list)

    sp = sub.add_parser("open", help="Open a new tab at URL and print its targetId")
    sp.add_argument("url", help="URL to open, e.g., https://example.com")
    sp.set_defaults(func=cmd_open)

    sp = sub.add_parser("eval", help="Evaluate JavaScript in a target")
    sp.add_argument("--id", required=True, help="Target id from `chromectl list` or `chromectl open`")
    sp.add_argument("-e", "--expr", required=True, help="JavaScript expression to evaluate (use quotes)")
    sp.set_defaults(func=cmd_eval)

    sp = sub.add_parser("screenshot", help="Capture a PNG screenshot")
    sp.add_argument("--id", required=True, help="Target id to capture")
    sp.add_argument("-o", "--output", help="Output PNG path")
    sp.add_argument("--full-page", action="store_true", help="Attempt full-page capture by resizing the viewport")
    sp.set_defaults(func=cmd_screenshot)

    sp = sub.add_parser("console-tail", help="Stream console/log entries for a target")
    sp.add_argument("--id", required=True, help="Target id to attach to")
    sp.add_argument("--for", dest="for_seconds", default="10", help="Seconds to stream (default: 10)")
    sp.set_defaults(func=cmd_console_tail)

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
