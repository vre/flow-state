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


class TestParseLinks:
    def test_wikilink(self):
        assert client.parse_links("[[target]]") == [{"target": "target", "type": "wikilink"}]

    def test_wikilink_alias(self):
        assert client.parse_links("[[target|Alias]]") == [{"target": "target", "type": "wikilink", "alias": "Alias"}]

    def test_wikilink_heading(self):
        assert client.parse_links("[[target#Heading]]") == [{"target": "target", "type": "wikilink", "heading": "Heading"}]

    def test_wikilink_heading_alias(self):
        assert client.parse_links("[[target#Heading|Alias]]") == [
            {
                "target": "target",
                "type": "wikilink",
                "heading": "Heading",
                "alias": "Alias",
            }
        ]

    def test_wikilink_embed(self):
        assert client.parse_links("![[embed.png]]") == [{"target": "embed.png", "type": "wikilink", "embed": True}]

    def test_markdown_link(self):
        assert client.parse_links("[text](relative/path.md)") == [{"target": "relative/path.md", "type": "markdown"}]

    def test_excludes_external_urls(self):
        assert client.parse_links("[site](https://example.com) [plain](http://example.com)") == []

    def test_excludes_markdown_images(self):
        assert client.parse_links("![alt](image.png)") == []

    def test_mixed_content_preserves_order(self):
        assert client.parse_links("[one](one.md) [[two]]") == [
            {"target": "one.md", "type": "markdown"},
            {"target": "two", "type": "wikilink"},
        ]

    def test_empty_and_same_file_heading(self):
        assert client.parse_links("[[]] [[#Heading]] []()") == []


class TestResolveWikilink:
    def test_unique_match(self):
        assert client.resolve_wikilink("foo", "notes/bar.md", ["notes/foo.md"]) == "notes/foo.md"

    def test_proximity_tiebreaker(self):
        assert client.resolve_wikilink("foo", "notes/bar.md", ["notes/foo.md", "archive/foo.md"]) == "notes/foo.md"

    def test_shortest_path_fallback(self):
        assert client.resolve_wikilink("foo", "other/bar.md", ["notes/foo.md", "archive/deep/foo.md"]) == "notes/foo.md"

    def test_exact_suffix(self):
        assert client.resolve_wikilink("notes/foo", "x.md", ["notes/foo.md", "other/foo.md"]) == "notes/foo.md"

    def test_no_match(self):
        assert client.resolve_wikilink("bar", "x.md", ["notes/foo.md"]) is None

    def test_with_extension(self):
        assert client.resolve_wikilink("foo.md", "x.md", ["foo.md"]) == "foo.md"


class TestResolveRelativePath:
    def test_parent_dir(self):
        assert client.resolve_relative_path("../foo.md", "notes/sub/bar.md") == "notes/foo.md"

    def test_sibling(self):
        assert client.resolve_relative_path("sibling.md", "notes/bar.md") == "notes/sibling.md"

    def test_current_dir(self):
        assert client.resolve_relative_path("./local.md", "bar.md") == "local.md"

    def test_root_level(self):
        assert client.resolve_relative_path("local.md", "bar.md") == "local.md"


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


class TestListVaultFiles:
    @pytest.mark.asyncio
    async def test_recursive(self):
        async def fake_list_dirs(paths):
            listings = {
                "/": {"files": ["index.md", "notes/", "attachments/"]},
                "notes/": {"files": ["foo.md"]},
                "attachments/": {"files": ["image.png"]},
            }
            return {path: listings[path] for path in paths}

        with patch.object(client, "list_dirs", side_effect=fake_list_dirs):
            result = await client.list_vault_files("/")
        assert result == ["index.md", "notes/foo.md", "attachments/image.png"]

    @pytest.mark.asyncio
    async def test_normalizes_path(self):
        async def fake_list_dirs(paths):
            assert paths == ["notes/"]
            return {"notes/": {"files": ["foo.md"]}}

        with patch.object(client, "list_dirs", side_effect=fake_list_dirs):
            result = await client.list_vault_files("notes")
        assert result == ["notes/foo.md"]

    @pytest.mark.asyncio
    async def test_skips_subdirectory_error(self):
        async def fake_list_dirs(paths):
            listings = {
                "/": {"files": ["index.md", "broken/"]},
                "broken/": {"error": "ERROR: 404"},
            }
            return {path: listings[path] for path in paths}

        with patch.object(client, "list_dirs", side_effect=fake_list_dirs):
            result = await client.list_vault_files("/")
        assert result == ["index.md"]


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


class TestGraphOperations:
    @pytest.mark.asyncio
    async def test_outlinks_resolves_targets(self):
        with (
            patch.object(
                client,
                "list_vault_files",
                new_callable=AsyncMock,
                return_value=["index.md", "notes/target.md", "local.md", "attachments/image.png"],
            ),
            patch.object(
                client,
                "read_files",
                new_callable=AsyncMock,
                return_value={"index.md": "[[target|Alias]] [local](local.md) ![[image.png]] [[missing]]"},
            ),
        ):
            result = await client.outlinks("index.md")
        assert result == [
            {"target": "notes/target.md", "type": "wikilink", "alias": "Alias"},
            {"target": "local.md", "type": "markdown"},
            {"target": "attachments/image.png", "type": "wikilink", "embed": True},
            {"target": "missing", "type": "wikilink"},
        ]

    @pytest.mark.asyncio
    async def test_outlinks_read_error_raises(self):
        with (
            patch.object(client, "list_vault_files", new_callable=AsyncMock, return_value=["index.md"]),
            patch.object(
                client,
                "read_files",
                new_callable=AsyncMock,
                return_value={"index.md": "ERROR: 404"},
            ),
        ):
            with pytest.raises(ValueError, match="ERROR: 404"):
                await client.outlinks("index.md")

    @pytest.mark.asyncio
    async def test_backlinks_finds_reverse_links_with_context(self):
        files = ["target.md", "source.md", "folder/source2.md", "skip.txt"]

        async def fake_read_files(paths):
            contents = {
                "source.md": "before " + ("x" * 60) + " [[target]] after",
                "folder/source2.md": "see [target](../target.md)",
            }
            return {path: contents[path] for path in paths}

        with (
            patch.object(client, "list_vault_files", new_callable=AsyncMock, return_value=files),
            patch.object(client, "read_files", side_effect=fake_read_files),
        ):
            result = await client.backlinks("target.md")
        assert result[0]["source"] == "source.md"
        assert result[0]["type"] == "wikilink"
        assert "[[target]]" in result[0]["context"]
        assert result[1] == {
            "source": "folder/source2.md",
            "type": "markdown",
            "context": "see [target](../target.md)",
        }

    @pytest.mark.asyncio
    async def test_broken_links_detects_missing_targets(self):
        files = ["index.md", "exists.md", "folder/ok.md", "folder/scan.md"]

        async def fake_read_files(paths):
            contents = {
                "index.md": "[[missing]] [[exists]] [bad](missing.md)",
                "exists.md": "",
                "folder/ok.md": "",
                "folder/scan.md": "[ok](ok.md) [bad](bad.md)",
            }
            return {path: contents[path] for path in paths}

        with (
            patch.object(client, "list_vault_files", new_callable=AsyncMock, return_value=files),
            patch.object(client, "read_files", side_effect=fake_read_files),
        ):
            result = await client.broken_links("/")
        assert result == [
            {"source": "index.md", "target": "missing", "type": "wikilink"},
            {"source": "index.md", "target": "missing.md", "type": "markdown"},
            {"source": "folder/scan.md", "target": "bad.md", "type": "markdown"},
        ]


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


# --- Frontmatter validation ---


class TestValidateFrontmatter:
    def test_no_frontmatter_passes(self):
        assert client.validate_frontmatter("# Just a heading\nSome text") is None

    def test_valid_frontmatter_passes(self):
        content = "---\ntitle: Test\ntags: [a, b]\n---\n# Content"
        assert client.validate_frontmatter(content) is None

    def test_empty_frontmatter_passes(self):
        assert client.validate_frontmatter("---\n---\n# Content") is None

    def test_unclosed_frontmatter(self):
        result = client.validate_frontmatter("---\ntitle: Test\n# No closing")
        assert result is not None
        assert "closing" in result.lower()

    def test_invalid_yaml(self):
        content = "---\ntitle: [unclosed\n---\n"
        result = client.validate_frontmatter(content)
        assert result is not None
        assert "invalid yaml" in result.lower()

    def test_non_mapping_frontmatter(self):
        content = "---\n- just a list\n- not a mapping\n---\n"
        result = client.validate_frontmatter(content)
        assert result is not None
        assert "mapping" in result.lower()

    def test_complex_valid_frontmatter(self):
        content = "---\ntitle: Test\ntags:\n  - a\n  - b\nnested:\n  key: value\n---\n"
        assert client.validate_frontmatter(content) is None


class TestWriteFileValidation:
    @pytest.mark.asyncio
    async def test_write_rejects_invalid_frontmatter(self):
        with pytest.raises(ValueError, match="Frontmatter validation failed"):
            await client.write_file("test.md", "---\ntitle: [broken\n---\n")

    @pytest.mark.asyncio
    async def test_write_skips_validation_for_non_md(self):
        """Non-markdown files skip frontmatter validation."""
        with patch.object(client, "_client") as mock_client:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_ctx.__aexit__ = AsyncMock(return_value=False)
            mock_ctx.put = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_ctx
            result = await client.write_file("data.json", "---\nnot: [valid\n---")
            assert result["status"] == "ok"
