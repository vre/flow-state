"""Tests for obsidian_client — mock httpx, no external calls."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import obsidian_client as client
import pytest


@pytest.fixture(autouse=True)
def set_env(monkeypatch):
    """Set test environment variables."""
    monkeypatch.setenv("OBSIDIAN_API_KEY", "test-key-123")
    monkeypatch.setenv("OBSIDIAN_API_URL", "http://localhost:27123")


def _mock_response(data=None, text="", status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = data if data is not None else {}
    resp.text = text
    resp.raise_for_status = MagicMock()
    return resp


def _mock_client(response):
    """Create a mock async client context manager."""
    mock = AsyncMock()
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock(return_value=False)
    mock.get = AsyncMock(return_value=response)
    mock.post = AsyncMock(return_value=response)
    mock.put = AsyncMock(return_value=response)
    mock.patch = AsyncMock(return_value=response)
    mock.delete = AsyncMock(return_value=response)
    return mock


class TestListDirs:
    @pytest.mark.asyncio
    async def test_list_root(self):
        resp = _mock_response(data={"files": ["index.md", "docs/"]})
        mock = _mock_client(resp)
        with patch.object(client, "_client", return_value=mock):
            result = await client.list_dirs(["/"])
        assert result["/"] == {"files": ["index.md", "docs/"]}
        mock.get.assert_called_once()
        call_args = mock.get.call_args
        assert "/vault/" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_list_subdirectory(self):
        resp = _mock_response(data={"files": ["note.md"]})
        mock = _mock_client(resp)
        with patch.object(client, "_client", return_value=mock):
            await client.list_dirs(["docs/"])
        mock.get.assert_called_once()
        assert "/vault/docs/" in mock.get.call_args[0][0]

    @pytest.mark.asyncio
    async def test_list_adds_trailing_slash(self):
        resp = _mock_response(data={"files": []})
        mock = _mock_client(resp)
        with patch.object(client, "_client", return_value=mock):
            await client.list_dirs(["projects"])
        assert mock.get.call_args[0][0].endswith("/")

    @pytest.mark.asyncio
    async def test_list_empty_defaults_to_root(self):
        resp = _mock_response(data={"files": ["index.md"]})
        mock = _mock_client(resp)
        with patch.object(client, "_client", return_value=mock):
            result = await client.list_dirs([])
        assert "/" in result

    @pytest.mark.asyncio
    async def test_list_multiple_dirs(self):
        """Two directories listed concurrently."""
        resp = _mock_response(data={"files": ["a.md"]})
        mock = _mock_client(resp)
        with patch.object(client, "_client", return_value=mock):
            result = await client.list_dirs(["docs/", "topics/"])
        assert "docs/" in result
        assert "topics/" in result
        assert mock.get.call_count == 2

    @pytest.mark.asyncio
    async def test_list_one_fails(self):
        """One path errors, the other succeeds."""
        ok_resp = _mock_response(data={"files": ["a.md"]})
        err_resp = MagicMock()
        err_resp.raise_for_status = MagicMock(side_effect=Exception("404 Not Found"))

        call_count = 0

        async def _side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return ok_resp
            return err_resp

        mock = AsyncMock()
        mock.__aenter__ = AsyncMock(return_value=mock)
        mock.__aexit__ = AsyncMock(return_value=False)
        mock.get = AsyncMock(side_effect=_side_effect)

        with patch.object(client, "_client", return_value=mock):
            result = await client.list_dirs(["docs/", "nonexistent/"])
        # One succeeds, one has error
        assert "files" in result["docs/"]
        assert "error" in result["nonexistent/"]
        assert result["nonexistent/"]["error"].startswith("ERROR: ")


class TestReadFiles:
    @pytest.mark.asyncio
    async def test_read_markdown(self):
        resp = _mock_response(text="# Hello\n\nWorld")
        mock = _mock_client(resp)
        with patch.object(client, "_client", return_value=mock):
            result = await client.read_files(["index.md"])
        assert result["index.md"] == "# Hello\n\nWorld"
        headers = mock.get.call_args[1]["headers"]
        assert headers["Accept"] == "text/markdown"

    @pytest.mark.asyncio
    async def test_read_json(self):
        note_data = {"content": "# Hello", "frontmatter": {"title": "Test"}}
        resp = _mock_response(data=note_data)
        mock = _mock_client(resp)
        with patch.object(client, "_client", return_value=mock):
            result = await client.read_files(["index.md"], as_json=True)
        assert result["index.md"] == note_data
        headers = mock.get.call_args[1]["headers"]
        assert headers["Accept"] == "application/vnd.olrapi.note+json"

    @pytest.mark.asyncio
    async def test_read_multiple_files(self):
        """Two files read concurrently."""
        resp = _mock_response(text="content")
        mock = _mock_client(resp)
        with patch.object(client, "_client", return_value=mock):
            result = await client.read_files(["a.md", "b.md"])
        assert "a.md" in result
        assert "b.md" in result
        assert mock.get.call_count == 2

    @pytest.mark.asyncio
    async def test_read_one_fails(self):
        """One file errors, the other succeeds."""
        ok_resp = _mock_response(text="good content")
        err_resp = MagicMock()
        err_resp.raise_for_status = MagicMock(side_effect=Exception("404 Not Found"))

        call_count = 0

        async def _side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return ok_resp
            return err_resp

        mock = AsyncMock()
        mock.__aenter__ = AsyncMock(return_value=mock)
        mock.__aexit__ = AsyncMock(return_value=False)
        mock.get = AsyncMock(side_effect=_side_effect)

        with patch.object(client, "_client", return_value=mock):
            result = await client.read_files(["good.md", "bad.md"])
        assert result["good.md"] == "good content"
        assert result["bad.md"].startswith("ERROR: ")


class TestWriteFile:
    @pytest.mark.asyncio
    async def test_write(self):
        resp = _mock_response()
        mock = _mock_client(resp)
        with patch.object(client, "_client", return_value=mock):
            result = await client.write_file("test.md", "# Test")
        assert result["status"] == "ok"
        assert result["file"] == "test.md"
        mock.put.assert_called_once()


class TestAppendFile:
    @pytest.mark.asyncio
    async def test_append(self):
        resp = _mock_response()
        mock = _mock_client(resp)
        with patch.object(client, "_client", return_value=mock):
            result = await client.append_file("log.md", "\n- entry")
        assert result["status"] == "ok"
        mock.post.assert_called_once()


class TestPatchFile:
    @pytest.mark.asyncio
    async def test_patch_heading(self):
        resp = _mock_response()
        mock = _mock_client(resp)
        with patch.object(client, "_client", return_value=mock):
            result = await client.patch_file(
                "notes.md",
                "new text",
                operation="append",
                target_type="heading",
                target="Tasks",
            )
        assert result["status"] == "ok"
        mock.patch.assert_called_once()
        headers = mock.patch.call_args[1]["headers"]
        assert headers["Operation"] == "append"
        assert headers["Target-Type"] == "heading"
        assert headers["Target"] == "Tasks"


class TestDeleteFile:
    @pytest.mark.asyncio
    async def test_delete(self):
        resp = _mock_response()
        mock = _mock_client(resp)
        with patch.object(client, "_client", return_value=mock):
            result = await client.delete_file("temp.md")
        assert result["deleted"] is True
        mock.delete.assert_called_once()


class TestSearch:
    @pytest.mark.asyncio
    async def test_simple_search(self):
        search_results = [{"filename": "note.md", "matches": []}]
        resp = _mock_response(data=search_results)
        mock = _mock_client(resp)
        with patch.object(client, "_client", return_value=mock):
            result = await client.search_simple("test query", context_length=200)
        assert result == search_results
        mock.post.assert_called_once()
        call_params = mock.post.call_args[1]["params"]
        assert call_params["query"] == "test query"
        assert call_params["contextLength"] == 200

    @pytest.mark.asyncio
    async def test_advanced_search_dataview(self):
        resp = _mock_response(data=[{"result": "data"}])
        mock = _mock_client(resp)
        with patch.object(client, "_client", return_value=mock):
            result = await client.search_advanced("TABLE file.name", query_type="dataview")
        assert result == [{"result": "data"}]
        headers = mock.post.call_args[1]["headers"]
        assert headers["Content-Type"] == "application/vnd.olrapi.dataview.dql+txt"

    @pytest.mark.asyncio
    async def test_advanced_search_jsonlogic(self):
        resp = _mock_response(data=[])
        mock = _mock_client(resp)
        with patch.object(client, "_client", return_value=mock):
            await client.search_advanced('{"glob":["*.md"]}', query_type="jsonlogic")
        headers = mock.post.call_args[1]["headers"]
        assert headers["Content-Type"] == "application/vnd.olrapi.jsonlogic+json"


class TestTags:
    @pytest.mark.asyncio
    async def test_list_tags(self):
        resp = _mock_response(data={"tags": [{"name": "test", "count": 3}]})
        mock = _mock_client(resp)
        with patch.object(client, "_client", return_value=mock):
            result = await client.list_tags()
        assert result["tags"][0]["name"] == "test"


class TestCommands:
    @pytest.mark.asyncio
    async def test_list_commands(self):
        resp = _mock_response(data={"commands": [{"id": "editor:save", "name": "Save"}]})
        mock = _mock_client(resp)
        with patch.object(client, "_client", return_value=mock):
            result = await client.list_commands()
        assert result["commands"][0]["id"] == "editor:save"

    @pytest.mark.asyncio
    async def test_run_command(self):
        resp = _mock_response()
        mock = _mock_client(resp)
        with patch.object(client, "_client", return_value=mock):
            result = await client.run_command("editor:save-file")
        assert result["command"] == "editor:save-file"


class TestOpenFile:
    @pytest.mark.asyncio
    async def test_open(self):
        resp = _mock_response()
        mock = _mock_client(resp)
        with patch.object(client, "_client", return_value=mock):
            result = await client.open_file("index.md", new_leaf=True)
        assert result["new_leaf"] is True
        mock.post.assert_called_once()


class TestActiveFile:
    @pytest.mark.asyncio
    async def test_active_read(self):
        resp = _mock_response(text="# Active note")
        mock = _mock_client(resp)
        with patch.object(client, "_client", return_value=mock):
            result = await client.active_read()
        assert result == "# Active note"

    @pytest.mark.asyncio
    async def test_active_write(self):
        resp = _mock_response()
        mock = _mock_client(resp)
        with patch.object(client, "_client", return_value=mock):
            result = await client.active_write("# New content")
        assert result["target"] == "active_file"


class TestPeriodicNotes:
    @pytest.mark.asyncio
    async def test_periodic_read_current(self):
        resp = _mock_response(text="# Daily note")
        mock = _mock_client(resp)
        with patch.object(client, "_client", return_value=mock):
            result = await client.periodic_read(period="daily")
        assert result == "# Daily note"
        assert "/periodic/daily/" in mock.get.call_args[0][0]

    @pytest.mark.asyncio
    async def test_periodic_read_specific_date(self):
        resp = _mock_response(text="# Note")
        mock = _mock_client(resp)
        with patch.object(client, "_client", return_value=mock):
            await client.periodic_read(period="daily", year=2026, month=4, day=1)
        assert "/periodic/daily/2026/4/1/" in mock.get.call_args[0][0]

    @pytest.mark.asyncio
    async def test_periodic_write(self):
        resp = _mock_response()
        mock = _mock_client(resp)
        with patch.object(client, "_client", return_value=mock):
            result = await client.periodic_write("# Content", period="weekly")
        assert result["period"] == "weekly"

    @pytest.mark.asyncio
    async def test_periodic_append(self):
        resp = _mock_response()
        mock = _mock_client(resp)
        with patch.object(client, "_client", return_value=mock):
            result = await client.periodic_append("- item", period="daily")
        assert result["period"] == "daily"


class TestPeriodicUrl:
    def test_current_period(self):
        assert client._periodic_url("daily", None, None, None) == "/periodic/daily/"

    def test_specific_date(self):
        assert client._periodic_url("daily", 2026, 4, 1) == "/periodic/daily/2026/4/1/"

    def test_year_only(self):
        assert client._periodic_url("yearly", 2026, None, None) == "/periodic/yearly/2026/"


class TestHelpers:
    def test_base_url_default(self, monkeypatch):
        monkeypatch.delenv("OBSIDIAN_API_URL", raising=False)
        assert client._base_url() == "http://127.0.0.1:27123"

    def test_base_url_custom(self, monkeypatch):
        monkeypatch.setenv("OBSIDIAN_API_URL", "http://custom:8080/")
        assert client._base_url() == "http://custom:8080"

    def test_api_key_missing(self, monkeypatch):
        monkeypatch.delenv("OBSIDIAN_API_KEY", raising=False)
        with pytest.raises(RuntimeError, match="OBSIDIAN_API_KEY not set"):
            client._api_key()

    def test_headers_include_auth(self):
        headers = client._headers()
        assert headers["Authorization"] == "Bearer test-key-123"

    def test_headers_with_extra(self):
        headers = client._headers({"Accept": "text/plain"})
        assert "Authorization" in headers
        assert headers["Accept"] == "text/plain"


class TestServerStatus:
    @pytest.mark.asyncio
    async def test_status(self):
        status_data = {"status": "OK", "versions": {"self": "3.5.0"}}
        resp = _mock_response(data=status_data)
        mock = _mock_client(resp)
        with patch.object(client, "_client", return_value=mock):
            result = await client.server_status()
        assert result["status"] == "OK"
