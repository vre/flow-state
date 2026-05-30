"""Tests for chromectl — no Chrome required.

Tests cover: argument parsing, helper functions, Dispatcher command routing,
chromectl_daemon module, and socket protocol JSON format.
"""

import asyncio
import json
import os
import tempfile
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from chromectl import (
    CDPError,
    Dispatcher,
    FlatSession,
    build_parser,
    default_chrome_user_data_dir,
    read_devtools_active_port,
    resolve_connection,
)

# --- Helper functions ---


class TestDefaultChromeUserDataDir:
    def test_darwin(self):
        with patch("chromectl.platform.system", return_value="Darwin"):
            result = default_chrome_user_data_dir()
            assert "Library/Application Support/Google/Chrome" in result

    def test_linux(self):
        with patch("chromectl.platform.system", return_value="Linux"):
            result = default_chrome_user_data_dir()
            assert ".config/google-chrome" in result

    def test_windows(self):
        with patch("chromectl.platform.system", return_value="Windows"):
            with patch.dict(os.environ, {"LOCALAPPDATA": "C:\\Users\\test\\AppData\\Local"}):
                result = default_chrome_user_data_dir()
                assert "Google" in result and "Chrome" in result

    def test_unknown_platform(self):
        with patch("chromectl.platform.system", return_value="FreeBSD"):
            assert default_chrome_user_data_dir() == ""


class TestReadDevToolsActivePort:
    def test_valid_file(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "DevToolsActivePort"), "w") as f:
                f.write("9222\n/devtools/browser/abc-123\n")
            port, ws_path = read_devtools_active_port(d)
            assert port == 9222
            assert ws_path == "/devtools/browser/abc-123"

    def test_missing_file(self):
        with tempfile.TemporaryDirectory() as d:
            with pytest.raises(FileNotFoundError):
                read_devtools_active_port(d)

    def test_invalid_content_single_line(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "DevToolsActivePort"), "w") as f:
                f.write("9222\n")
            with pytest.raises(CDPError, match="Invalid"):
                read_devtools_active_port(d)

    def test_empty_file(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "DevToolsActivePort"), "w") as f:
                f.write("")
            with pytest.raises(CDPError, match="Invalid"):
                read_devtools_active_port(d)

    def test_corrupt_non_integer_port(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "DevToolsActivePort"), "w") as f:
                f.write("not-a-number\n/devtools/browser/abc\n")
            with pytest.raises(ValueError):
                read_devtools_active_port(d)

    def test_extra_whitespace(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "DevToolsActivePort"), "w") as f:
                f.write("  9222  \n  /devtools/browser/xyz  \n\n")
            port, ws_path = read_devtools_active_port(d)
            assert port == 9222
            assert ws_path == "/devtools/browser/xyz"


class TestResolveConnection:
    def test_traditional_mode(self):
        args = SimpleNamespace(host="127.0.0.1", port=9222, auto_connect=False)
        host, port, ws_path = resolve_connection(args)
        assert host == "127.0.0.1"
        assert port == 9222
        assert ws_path is None

    def test_auto_connect_with_port_file(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "DevToolsActivePort"), "w") as f:
                f.write("9333\n/devtools/browser/test-guid\n")
            args = SimpleNamespace(host="127.0.0.1", port=9222, auto_connect=True, user_data_dir=d)
            host, port, ws_path = resolve_connection(args)
            assert port == 9333
            assert ws_path == "/devtools/browser/test-guid"

    def test_auto_connect_fallback_no_port_file(self):
        with tempfile.TemporaryDirectory() as d:
            args = SimpleNamespace(host="127.0.0.1", port=9222, auto_connect=True, user_data_dir=d)
            host, port, ws_path = resolve_connection(args)
            assert port == 9222
            assert ws_path == "/devtools/browser"


# --- Argument parser ---


class TestParser:
    def setup_method(self):
        self.parser = build_parser()

    def test_start_command(self):
        args = self.parser.parse_args(["start"])
        assert args.cmd == "start"

    def test_stop_command(self):
        args = self.parser.parse_args(["stop"])
        assert args.cmd == "stop"

    def test_list_command(self):
        args = self.parser.parse_args(["list"])
        assert args.cmd == "list"

    def test_open_command(self):
        args = self.parser.parse_args(["open", "https://example.com"])
        assert args.cmd == "open"
        assert args.url == "https://example.com"

    def test_eval_command(self):
        args = self.parser.parse_args(["eval", "ABC123", "document.title"])
        assert args.cmd == "eval"
        assert args.target_id == "ABC123"
        assert args.expression == "document.title"

    def test_screenshot_command(self):
        args = self.parser.parse_args(["screenshot", "ABC123", "-o", "out.png", "--full-page"])
        assert args.cmd == "screenshot"
        assert args.target_id == "ABC123"
        assert args.output == "out.png"
        assert args.full_page is True

    def test_console_tail_command(self):
        args = self.parser.parse_args(["console-tail", "ABC123", "--for", "30"])
        assert args.cmd == "console-tail"
        assert args.target_id == "ABC123"
        assert args.for_seconds == 30.0

    def test_launch_legacy(self):
        args = self.parser.parse_args(["launch", "--headless", "--port", "9223"])
        assert args.cmd == "launch"
        assert args.headless is True
        assert args.port == 9223

    def test_click_command(self):
        args = self.parser.parse_args(["click", "T1", "button"])
        assert args.cmd == "click"
        assert args.target_id == "T1"
        assert args.selector == "button"

    def test_eval_with_target(self):
        args = self.parser.parse_args(["eval", "T1", "1+1"])
        assert args.target_id == "T1"
        assert args.expression == "1+1"

    def test_screenshot_with_options(self):
        args = self.parser.parse_args(["screenshot", "T1", "-o", "s.png", "--full-page"])
        assert args.target_id == "T1"
        assert args.output == "s.png"
        assert args.full_page is True

    def test_global_options_before_command(self):
        args = self.parser.parse_args(["--port", "9333", "--host", "10.0.0.1", "list"])
        assert args.port == 9333
        assert args.host == "10.0.0.1"

    def test_no_command_fails(self):
        with pytest.raises(SystemExit):
            self.parser.parse_args([])

    def test_launch_is_last_subcommand(self):
        """Launch should appear after start/stop/eval in help ordering."""
        actions = self.parser._subparsers._actions
        for action in actions:
            if hasattr(action, "_parser_class"):
                choices = list(action.choices.keys())
                assert choices.index("launch") > choices.index("start")
                assert choices.index("launch") > choices.index("eval")
                break


# --- Dispatcher (mocked CDP) ---


class TestDispatcher:
    def _make_dispatcher(self, ws_path="/devtools/browser/test"):
        bc = MagicMock()
        bc._conn = MagicMock()
        return Dispatcher("127.0.0.1", 9222, ws_path, bc)

    @pytest.mark.asyncio
    async def test_list_filters_pages(self):
        d = self._make_dispatcher()
        d.bc.list_targets = AsyncMock(
            return_value=[
                {"targetId": "1", "type": "page", "title": "Tab 1", "url": "https://a.com"},
                {"targetId": "2", "type": "service_worker", "title": "SW", "url": "https://a.com/sw.js"},
                {"targetId": "3", "type": "page", "title": "Tab 2", "url": "https://b.com"},
            ]
        )
        result = await d.dispatch({"cmd": "list"})
        assert len(result["targets"]) == 2
        assert all(t["type"] == "page" for t in result["targets"])

    @pytest.mark.asyncio
    async def test_targets_returns_all(self):
        d = self._make_dispatcher()
        d.bc.list_targets = AsyncMock(
            return_value=[
                {"targetId": "1", "type": "page", "title": "Tab", "url": "https://a.com"},
                {"targetId": "2", "type": "service_worker", "title": "SW", "url": "https://a.com/sw.js"},
            ]
        )
        result = await d.dispatch({"cmd": "targets"})
        assert len(result["targets"]) == 2

    @pytest.mark.asyncio
    async def test_open(self):
        d = self._make_dispatcher()
        d.bc.create_target = AsyncMock(return_value={"id": "NEW1", "url": "https://x.com"})
        result = await d.dispatch({"cmd": "open", "url": "https://x.com"})
        assert result["id"] == "NEW1"

    @pytest.mark.asyncio
    async def test_eval_success(self):
        d = self._make_dispatcher()
        session = AsyncMock()
        session.send = AsyncMock(
            side_effect=[
                None,  # Runtime.enable
                {"result": {"value": "Hello"}},  # Runtime.evaluate
            ]
        )
        d.bc.attach_to_target = AsyncMock(return_value=session)
        tid = "A" * 32
        result = await d.dispatch({"cmd": "eval", "id": tid, "expr": "document.title"})
        assert result == {"value": "Hello"}

    @pytest.mark.asyncio
    async def test_eval_missing_id(self):
        d = self._make_dispatcher()
        result = await d.dispatch({"cmd": "eval", "expr": "1+1"})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_eval_exception(self):
        d = self._make_dispatcher()
        session = AsyncMock()
        session.send = AsyncMock(
            side_effect=[
                None,
                {"exceptionDetails": {"text": "ReferenceError"}},
            ]
        )
        d.bc.attach_to_target = AsyncMock(return_value=session)
        tid = "A" * 32
        result = await d.dispatch({"cmd": "eval", "id": tid, "expr": "badVar"})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_screenshot_missing_id(self):
        d = self._make_dispatcher()
        result = await d.dispatch({"cmd": "screenshot"})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_console_tail_missing_id(self):
        d = self._make_dispatcher()
        result = await d.dispatch({"cmd": "console-tail"})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_unknown_command(self):
        d = self._make_dispatcher()
        tid = "A" * 32
        result = await d.dispatch({"cmd": "foobar", "id": tid})
        assert "error" in result
        assert "Unknown command" in result["error"]

    @pytest.mark.asyncio
    async def test_status(self):
        d = self._make_dispatcher()
        result = await d.dispatch({"cmd": "status"})
        assert result["connected"] is True
        assert result["mode"] == "auto-connect"
        assert result["port"] == 9222

    @pytest.mark.asyncio
    async def test_status_traditional_mode(self):
        bc = MagicMock()
        d = Dispatcher("127.0.0.1", 9222, None, bc)
        result = await d.dispatch({"cmd": "status"})
        assert result["mode"] == "http"

    @pytest.mark.asyncio
    async def test_session_caching(self):
        d = self._make_dispatcher()
        session = AsyncMock()
        session.send = AsyncMock(return_value=None)
        d.bc.attach_to_target = AsyncMock(return_value=session)
        await d.get_session("T1")
        await d.get_session("T1")
        d.bc.attach_to_target.assert_called_once()

    @pytest.mark.asyncio
    async def test_cdp_raw(self):
        d = self._make_dispatcher()
        d.bc._conn.send = AsyncMock(return_value={"data": "test"})
        result = await d.dispatch({"cmd": "cdp", "method": "Browser.getVersion"})
        assert result == {"result": {"data": "test"}}

    @pytest.mark.asyncio
    async def test_cdp_missing_method(self):
        d = self._make_dispatcher()
        result = await d.dispatch({"cmd": "cdp"})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_worker_eval_success(self):
        d = self._make_dispatcher()
        tid = "W" * 32
        d.bc._conn.send = AsyncMock(
            side_effect=[
                {"sessionId": "WS1"},  # Target.attachToTarget
                None,  # Runtime.enable (via send_session)
                {"result": {"value": 3}},  # Runtime.evaluate
            ]
        )
        d.bc._conn.send_session = AsyncMock(
            side_effect=[
                None,  # Runtime.enable
                {"result": {"value": 3}},  # Runtime.evaluate
            ]
        )
        d.sessions[tid] = FlatSession(d.bc._conn, "WS1")
        d.sessions[tid].send = AsyncMock(
            side_effect=[
                None,
                {"result": {"value": 3}},
            ]
        )
        result = await d.dispatch({"cmd": "worker-eval", "id": tid, "expr": "1+2"})
        assert result == {"value": 3}

    @pytest.mark.asyncio
    async def test_worker_eval_missing_id(self):
        d = self._make_dispatcher()
        result = await d.dispatch({"cmd": "worker-eval", "expr": "1+1"})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_worker_eval_no_browser_connection(self):
        d = self._make_dispatcher()
        d.bc = None
        tid = "W" * 32
        result = await d.dispatch({"cmd": "worker-eval", "id": tid, "expr": "1"})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_screenshot_success(self):
        d = self._make_dispatcher()
        session = AsyncMock()
        import base64

        tid = "A" * 32
        b64_data = base64.b64encode(b"fake-png-data").decode()
        session.send = AsyncMock(
            side_effect=[
                None,  # Page.enable
                None,  # Page.bringToFront
                {"data": b64_data},  # Page.captureScreenshot
            ]
        )
        d.bc.attach_to_target = AsyncMock(return_value=session)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            tmp_path = f.name
        try:
            result = await d.dispatch({"cmd": "screenshot", "id": tid, "output": tmp_path})
            assert result["file"] == tmp_path
            with open(tmp_path, "rb") as f:
                assert f.read() == b"fake-png-data"
        finally:
            os.unlink(tmp_path)

    @pytest.mark.asyncio
    async def test_screenshot_full_page(self):
        d = self._make_dispatcher()
        session = AsyncMock()
        import base64

        tid = "A" * 32
        b64_data = base64.b64encode(b"full-page").decode()
        session.send = AsyncMock(
            side_effect=[
                None,  # Page.enable
                {"contentSize": {"width": 1280, "height": 5000}},  # Page.getLayoutMetrics
                None,  # Emulation.setDeviceMetricsOverride
                None,  # Page.bringToFront
                {"data": b64_data},  # Page.captureScreenshot
                None,  # Emulation.clearDeviceMetricsOverride
            ]
        )
        d.bc.attach_to_target = AsyncMock(return_value=session)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            tmp_path = f.name
        try:
            result = await d.dispatch({"cmd": "screenshot", "id": tid, "output": tmp_path, "full_page": True})
            assert result["file"] == tmp_path
        finally:
            os.unlink(tmp_path)

    @pytest.mark.asyncio
    async def test_console_tail_collects_messages(self):
        d = self._make_dispatcher()
        session = AsyncMock()
        session.send = AsyncMock(return_value=None)
        captured_handler = {}

        def capture_handler(handler):
            captured_handler["fn"] = handler

        session.set_event_handler = capture_handler
        d.bc.attach_to_target = AsyncMock(return_value=session)

        async def inject_events():
            await asyncio.sleep(0.05)
            if "fn" in captured_handler and captured_handler["fn"]:
                await captured_handler["fn"](
                    {"method": "Runtime.consoleAPICalled", "params": {"type": "log", "args": [{"value": "hello"}]}}
                )
                await captured_handler["fn"](
                    {"method": "Log.entryAdded", "params": {"entry": {"level": "error", "source": "javascript", "text": "oops"}}}
                )

        tid = "A" * 32
        task = asyncio.create_task(inject_events())
        result = await d.dispatch({"cmd": "console-tail", "id": tid, "for": 0.2})
        await task
        assert len(result["messages"]) == 2
        assert result["messages"][0]["console"] == "log"
        assert result["messages"][1]["level"] == "error"
        assert result["messages"][1]["source"] == "javascript"

    @pytest.mark.asyncio
    async def test_console_tail_clears_handler(self):
        d = self._make_dispatcher()
        session = AsyncMock()
        session.send = AsyncMock(return_value=None)
        handlers_set = []

        def track_handler(handler):
            handlers_set.append(handler)

        session.set_event_handler = track_handler
        tid = "A" * 32
        d.bc.attach_to_target = AsyncMock(return_value=session)
        await d.dispatch({"cmd": "console-tail", "id": tid, "for": 0.05})
        assert len(handlers_set) == 2
        assert handlers_set[0] is not None
        assert handlers_set[1] is None

    @pytest.mark.asyncio
    async def test_dispatch_safe_timeout(self):
        d = self._make_dispatcher()
        d.DISPATCH_TIMEOUT = 0.1

        async def slow_dispatch(req):
            await asyncio.sleep(5)

        d.dispatch = slow_dispatch
        d._reconnect = AsyncMock(return_value=False)
        result = await d.dispatch_safe({"cmd": "list"})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_dispatch_safe_reconnect_on_timeout(self):
        d = self._make_dispatcher()
        d.DISPATCH_TIMEOUT = 0.1
        call_count = 0

        async def flaky_dispatch(req):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                await asyncio.sleep(5)
            return {"targets": []}

        d.dispatch = flaky_dispatch
        d._reconnect = AsyncMock(return_value=True)
        result = await d.dispatch_safe({"cmd": "list"})
        assert result == {"targets": []}
        d._reconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_reconnect_success(self):
        d = self._make_dispatcher()
        d._user_data_dir = "/tmp/fake-chrome-dir"
        old_bc = d.bc
        old_bc.__aexit__ = AsyncMock()
        new_bc = MagicMock()
        new_bc.__aenter__ = AsyncMock(return_value=new_bc)
        new_bc.list_targets = AsyncMock(return_value=[])
        d.sessions["old"] = AsyncMock()

        with patch("chromectl.read_devtools_active_port", return_value=(9333, "/devtools/browser/new")):
            with patch("chromectl.BrowserConnection", return_value=new_bc):
                result = await d._reconnect()

        assert result is True
        assert d._connected is True
        assert d.port == 9333
        assert d.sessions == {}  # cleared

    @pytest.mark.asyncio
    async def test_reconnect_failure_all_attempts(self):
        d = self._make_dispatcher()
        d._user_data_dir = "/tmp/fake-chrome-dir"
        d.MAX_RECONNECT = 2
        d.RECONNECT_DELAY = 0.01
        old_bc = d.bc
        old_bc.__aexit__ = AsyncMock()

        with patch("chromectl.read_devtools_active_port", side_effect=FileNotFoundError):
            with patch("chromectl.BrowserConnection") as mock_bc_cls:
                mock_bc = MagicMock()
                mock_bc.__aenter__ = AsyncMock(side_effect=ConnectionError("refused"))
                mock_bc_cls.return_value = mock_bc
                result = await d._reconnect()

        assert result is False
        assert d._connected is False

    @pytest.mark.asyncio
    async def test_reconnect_no_user_data_dir(self):
        d = self._make_dispatcher()
        d._user_data_dir = None
        result = await d._reconnect()
        assert result is False

    @pytest.mark.asyncio
    async def test_dispatch_safe_marks_dead_on_reconnect_failure(self):
        d = self._make_dispatcher()
        d.DISPATCH_TIMEOUT = 0.1

        async def timeout_dispatch(req):
            await asyncio.sleep(5)

        d.dispatch = timeout_dispatch
        d._reconnect = AsyncMock(return_value=False)
        await d.dispatch_safe({"cmd": "list"})
        assert d._dead is True


# --- CLI → request mapping ---


class TestBuildOnRequest:
    """Verify that CLI args map to the correct JSON request for the daemon."""

    def _build(self, argv: list[str]) -> dict:
        parser = build_parser()
        args = parser.parse_args(argv)
        captured = {}

        async def fake_route(_args, req, **_kw):
            captured.update(req)

        with patch("chromectl._route_request", fake_route):
            asyncio.run(args.func(args))
        return captured

    def test_eval(self):
        req = self._build(["eval", "T1", "document.title"])
        assert req == {"cmd": "eval", "id": "T1", "expr": "document.title"}

    def test_click(self):
        req = self._build(["click", "T1", "button#submit"])
        assert req == {"cmd": "click", "id": "T1", "selector": "button#submit"}

    def test_type(self):
        req = self._build(["type", "T1", "#email", "user@example.com"])
        assert req == {"cmd": "type", "id": "T1", "selector": "#email", "text": "user@example.com"}

    def test_select(self):
        req = self._build(["select", "T1", "#country", "FI"])
        assert req == {"cmd": "select", "id": "T1", "selector": "#country", "value": "FI"}

    def test_get_attr(self):
        req = self._build(["get-attr", "T1", "a.link", "href"])
        assert req == {"cmd": "get-attr", "id": "T1", "selector": "a.link", "attr": "href"}

    def test_screenshot(self):
        req = self._build(["screenshot", "T1", "-o", "out.png"])
        assert req == {"cmd": "screenshot", "id": "T1", "output": "out.png"}

    def test_screenshot_full_page(self):
        req = self._build(["screenshot", "T1", "--full-page"])
        assert req == {"cmd": "screenshot", "id": "T1", "output": "screenshot.png", "full_page": True}

    def test_console_tail(self):
        req = self._build(["console-tail", "T1", "--for", "30"])
        assert req == {"cmd": "console-tail", "id": "T1", "for": 30.0}

    def test_console_tail_default_duration(self):
        req = self._build(["console-tail", "T1"])
        assert req == {"cmd": "console-tail", "id": "T1", "for": 10.0}

    def test_navigate(self):
        req = self._build(["navigate", "T1", "https://example.com"])
        assert req == {"cmd": "navigate", "id": "T1", "url": "https://example.com"}

    def test_scroll_down_pixels(self):
        req = self._build(["scroll-down", "T1", "500"])
        assert req == {"cmd": "scroll-down", "id": "T1", "pixels": 500}

    def test_scroll_down_default(self):
        req = self._build(["scroll-down", "T1"])
        assert req == {"cmd": "scroll-down", "id": "T1"}

    def test_scroll_by(self):
        req = self._build(["scroll-by", "T1", "0", "300"])
        assert req == {"cmd": "scroll-by", "id": "T1", "x": 0, "y": 300}

    def test_inject_css(self):
        req = self._build(["inject-css", "T1", "body { color: red }"])
        assert req == {"cmd": "inject-css", "id": "T1", "css": "body { color: red }"}

    def test_wait_for(self):
        req = self._build(["wait-for", "T1", ".loaded", "--timeout", "5"])
        assert req == {"cmd": "wait-for", "id": "T1", "selector": ".loaded", "timeout": 5.0}

    def test_wait_text(self):
        req = self._build(["wait-text", "T1", "#status", "Done"])
        assert req == {"cmd": "wait-text", "id": "T1", "selector": "#status", "text": "Done", "timeout": 10}

    def test_wait_url(self):
        req = self._build(["wait-url", "T1", "/dashboard"])
        assert req == {"cmd": "wait-url", "id": "T1", "pattern": "/dashboard", "timeout": 10}

    def test_cdp(self):
        req = self._build(["cdp", "Browser.getVersion"])
        assert req == {"cmd": "cdp", "method": "Browser.getVersion"}

    def test_worker_eval(self):
        req = self._build(["worker-eval", "T1", "self.clients.matchAll()"])
        assert req == {"cmd": "worker-eval", "id": "T1", "expr": "self.clients.matchAll()"}

    def test_no_args_commands(self):
        for cmd in ("reload", "back", "forward", "get-title", "get-url", "scroll-top", "scroll-bottom"):
            req = self._build([cmd, "T1"])
            assert req == {"cmd": cmd, "id": "T1"}, f"Failed for {cmd}"


# --- Socket protocol JSON ---


class TestSocketProtocol:
    """Verify JSON wire format matches documented protocol."""

    def test_list_request(self):
        req = json.loads('{"cmd":"list"}')
        assert req == {"cmd": "list"}

    def test_eval_request(self):
        req = json.loads('{"cmd":"eval","id":"TARGET_ID","expr":"document.title"}')
        assert req["cmd"] == "eval"
        assert req["id"] == "TARGET_ID"
        assert req["expr"] == "document.title"

    def test_screenshot_request(self):
        req = json.loads('{"cmd":"screenshot","id":"TARGET_ID","output":"shot.png"}')
        assert req["cmd"] == "screenshot"
        assert req["output"] == "shot.png"

    def test_quit_request(self):
        req = json.loads('{"cmd":"quit"}')
        assert req == {"cmd": "quit"}

    def test_open_request(self):
        req = json.loads('{"cmd":"open","url":"https://example.com"}')
        assert req["url"] == "https://example.com"


# --- chromectl_daemon module ---


class TestDaemonModule:
    def test_default_socket_path(self):
        import chromectl_daemon as cd

        path = cd._default_socket_path()
        assert path.startswith("/tmp/chromectl-")
        assert str(os.getuid()) in path

    def test_chromectl_path_exists(self):
        import chromectl_daemon as cd

        assert os.path.exists(cd.CHROMECTL), f"CHROMECTL points to {cd.CHROMECTL} which doesn't exist"

    def test_chromectl_path_is_sibling(self):
        import chromectl_daemon as cd

        assert os.path.dirname(cd.CHROMECTL) == os.path.dirname(os.path.abspath(cd.__file__))

    @pytest.mark.asyncio
    async def test_daemon_context_exit_socket_already_gone(self):
        import chromectl_daemon as cd

        ctx = cd.daemon_context("/tmp/nonexistent-test-socket.sock")
        ctx._we_started = True
        ctx._proc = MagicMock()
        ctx._proc.kill = MagicMock()
        # Socket doesn't exist — __aexit__ should not crash
        await ctx.__aexit__(None, None, None)
        ctx._proc.kill.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_command_format(self):
        """Verify send_command sends JSON + newline and reads JSON response."""
        import chromectl_daemon as cd

        mock_reader = AsyncMock()
        mock_reader.readline = AsyncMock(return_value=b'{"targets":[]}\n')
        mock_writer = MagicMock()
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()

        with patch("chromectl_daemon.asyncio.open_unix_connection", return_value=(mock_reader, mock_writer)):
            result = await cd.send_command({"cmd": "list"}, "/tmp/test.sock")

        written = mock_writer.write.call_args[0][0]
        assert written.endswith(b"\n")
        parsed = json.loads(written.decode())
        assert parsed == {"cmd": "list"}
        assert result == {"targets": []}
