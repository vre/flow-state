"""Tests for obsidian_slim_mcp — action routing and payload parsing."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from obsidian_slim_mcp import ObsidianAction, _parse_json_payload, _parse_periodic_payload, use_obsidian


class TestActionValidator:
    def test_valid_action(self):
        a = ObsidianAction(action="list")
        assert a.action == "list"

    def test_action_case_insensitive(self):
        a = ObsidianAction(action="LIST")
        assert a.action == "list"

    def test_invalid_action(self):
        with pytest.raises(ValueError, match="Invalid action"):
            ObsidianAction(action="bogus")

    def test_all_actions_valid(self):
        actions = [
            "list",
            "read",
            "write",
            "append",
            "patch",
            "delete",
            "search",
            "search_advanced",
            "outlinks",
            "backlinks",
            "broken_links",
            "tags",
            "commands",
            "command_run",
            "open",
            "active_read",
            "active_write",
            "periodic_read",
            "periodic_write",
            "periodic_append",
            "help",
        ]
        for action in actions:
            a = ObsidianAction(action=action)
            assert a.action == action


class TestHelp:
    @pytest.mark.asyncio
    async def test_help_overview(self):
        result = await use_obsidian(ObsidianAction(action="help"))
        assert "Obsidian Vault Tool" in result
        assert "list" in result
        assert "search" in result
        assert "outlinks" in result
        assert "backlinks" in result
        assert "broken_links" in result

    @pytest.mark.asyncio
    async def test_help_specific_topic(self):
        result = await use_obsidian(ObsidianAction(action="help", payload="search"))
        assert "Simple text search" in result

    @pytest.mark.asyncio
    async def test_help_unknown_topic(self):
        result = await use_obsidian(ObsidianAction(action="help", payload="nonexistent"))
        assert "Unknown topic" in result
        assert "overview" in result

    @pytest.mark.asyncio
    async def test_help_list_documents_multipath(self):
        result = await use_obsidian(ObsidianAction(action="help", payload="list"))
        assert "Multiple paths" in result

    @pytest.mark.asyncio
    async def test_help_read_documents_multipath(self):
        result = await use_obsidian(ObsidianAction(action="help", payload="read"))
        assert "Multiple paths" in result

    @pytest.mark.asyncio
    async def test_help_graph_topics(self):
        outlinks = await use_obsidian(ObsidianAction(action="help", payload="outlinks"))
        backlinks = await use_obsidian(ObsidianAction(action="help", payload="backlinks"))
        broken_links = await use_obsidian(ObsidianAction(action="help", payload="broken_links"))
        assert "Parse outgoing links" in outlinks
        assert "Find incoming links" in backlinks
        assert "Find broken links" in broken_links


class TestListAction:
    @pytest.mark.asyncio
    async def test_list_root(self):
        with patch("obsidian_client.list_dirs", new_callable=AsyncMock) as mock:
            mock.return_value = {"/": {"files": ["index.md", "docs/"]}}
            result = await use_obsidian(ObsidianAction(action="list"))
        parsed = json.loads(result)
        assert "index.md" in parsed["files"]
        mock.assert_called_once_with(["/"])

    @pytest.mark.asyncio
    async def test_list_directory(self):
        with patch("obsidian_client.list_dirs", new_callable=AsyncMock) as mock:
            mock.return_value = {"docs/": {"files": ["note.md"]}}
            await use_obsidian(ObsidianAction(action="list", payload="docs/"))
        mock.assert_called_once_with(["docs/"])

    @pytest.mark.asyncio
    async def test_list_multiple_dirs(self):
        with patch("obsidian_client.list_dirs", new_callable=AsyncMock) as mock:
            mock.return_value = {
                "docs/": {"files": ["a.md"]},
                "topics/": {"files": ["b.md"]},
            }
            result = await use_obsidian(ObsidianAction(action="list", payload="docs/\ntopics/"))
        mock.assert_called_once_with(["docs/", "topics/"])
        assert "=== docs/ ===" in result
        assert "=== topics/ ===" in result


class TestReadAction:
    @pytest.mark.asyncio
    async def test_read_markdown(self):
        with patch("obsidian_client.read_files", new_callable=AsyncMock) as mock:
            mock.return_value = {"index.md": "# Hello"}
            result = await use_obsidian(ObsidianAction(action="read", payload="index.md"))
        assert result == "# Hello"
        mock.assert_called_once_with(["index.md"], as_json=False)

    @pytest.mark.asyncio
    async def test_read_json_format(self):
        with patch("obsidian_client.read_files", new_callable=AsyncMock) as mock:
            mock.return_value = {"index.md": {"content": "# Hello", "frontmatter": {}}}
            result = await use_obsidian(ObsidianAction(action="read", payload="index.md|json"))
        parsed = json.loads(result)
        assert parsed["content"] == "# Hello"
        mock.assert_called_once_with(["index.md"], as_json=True)

    @pytest.mark.asyncio
    async def test_read_no_payload(self):
        result = await use_obsidian(ObsidianAction(action="read"))
        assert "Payload required" in result

    @pytest.mark.asyncio
    async def test_read_multiple_files(self):
        with patch("obsidian_client.read_files", new_callable=AsyncMock) as mock:
            mock.return_value = {
                "a.md": "# A",
                "b.md": "# B",
            }
            result = await use_obsidian(ObsidianAction(action="read", payload="a.md\nb.md"))
        mock.assert_called_once_with(["a.md", "b.md"], as_json=False)
        assert "=== a.md ===" in result
        assert "=== b.md ===" in result
        assert "# A" in result
        assert "# B" in result

    @pytest.mark.asyncio
    async def test_read_multiple_with_error(self):
        with patch("obsidian_client.read_files", new_callable=AsyncMock) as mock:
            mock.return_value = {
                "good.md": "# Good",
                "bad.md": "ERROR: 404 Not Found",
            }
            result = await use_obsidian(ObsidianAction(action="read", payload="good.md\nbad.md"))
        assert "=== good.md ===" in result
        assert "# Good" in result
        assert "=== bad.md ===" in result
        assert "ERROR:" in result


class TestWriteAction:
    @pytest.mark.asyncio
    async def test_write(self):
        with patch("obsidian_client.write_file", new_callable=AsyncMock) as mock:
            mock.return_value = {"status": "ok", "file": "test.md"}
            payload = json.dumps({"file": "test.md", "content": "# Test"})
            result = await use_obsidian(ObsidianAction(action="write", payload=payload))
        parsed = json.loads(result)
        assert parsed["status"] == "ok"

    @pytest.mark.asyncio
    async def test_write_missing_fields(self):
        result = await use_obsidian(ObsidianAction(action="write", payload='{"file":"test.md"}'))
        assert "Missing fields" in result


class TestSearchAction:
    @pytest.mark.asyncio
    async def test_search(self):
        with patch("obsidian_client.search_simple", new_callable=AsyncMock) as mock:
            mock.return_value = [{"filename": "note.md", "matches": []}]
            result = await use_obsidian(ObsidianAction(action="search", payload="test"))
        parsed = json.loads(result)
        assert parsed[0]["filename"] == "note.md"
        mock.assert_called_once_with("test", 100)

    @pytest.mark.asyncio
    async def test_search_with_context(self):
        with patch("obsidian_client.search_simple", new_callable=AsyncMock) as mock:
            mock.return_value = []
            await use_obsidian(ObsidianAction(action="search", payload="test|200"))
        mock.assert_called_once_with("test", 200)

    @pytest.mark.asyncio
    async def test_search_no_payload(self):
        result = await use_obsidian(ObsidianAction(action="search"))
        assert "Payload required" in result


class TestDeleteAction:
    @pytest.mark.asyncio
    async def test_delete(self):
        with patch("obsidian_client.delete_file", new_callable=AsyncMock) as mock:
            mock.return_value = {"status": "ok", "deleted": True}
            result = await use_obsidian(ObsidianAction(action="delete", payload="temp.md"))
        parsed = json.loads(result)
        assert parsed["deleted"] is True

    @pytest.mark.asyncio
    async def test_delete_no_payload(self):
        result = await use_obsidian(ObsidianAction(action="delete"))
        assert "Payload required" in result


class TestGraphActions:
    @pytest.mark.asyncio
    async def test_outlinks(self):
        with patch("obsidian_client.outlinks", new_callable=AsyncMock) as mock:
            mock.return_value = [{"target": "target.md", "type": "wikilink"}]
            result = await use_obsidian(ObsidianAction(action="outlinks", payload="index.md"))
        parsed = json.loads(result)
        assert parsed == [{"target": "target.md", "type": "wikilink"}]
        mock.assert_called_once_with("index.md")

    @pytest.mark.asyncio
    async def test_outlinks_no_payload(self):
        result = await use_obsidian(ObsidianAction(action="outlinks"))
        assert "Payload required" in result

    @pytest.mark.asyncio
    async def test_backlinks(self):
        with patch("obsidian_client.backlinks", new_callable=AsyncMock) as mock:
            mock.return_value = [{"source": "source.md", "type": "wikilink", "context": "[[index]]"}]
            result = await use_obsidian(ObsidianAction(action="backlinks", payload="index.md"))
        parsed = json.loads(result)
        assert parsed[0]["source"] == "source.md"
        mock.assert_called_once_with("index.md")

    @pytest.mark.asyncio
    async def test_backlinks_no_payload(self):
        result = await use_obsidian(ObsidianAction(action="backlinks"))
        assert "Payload required" in result

    @pytest.mark.asyncio
    async def test_broken_links_default(self):
        with patch("obsidian_client.broken_links", new_callable=AsyncMock) as mock:
            mock.return_value = [{"source": "source.md", "target": "missing.md", "type": "markdown"}]
            result = await use_obsidian(ObsidianAction(action="broken_links"))
        parsed = json.loads(result)
        assert parsed[0]["target"] == "missing.md"
        mock.assert_called_once_with("/")

    @pytest.mark.asyncio
    async def test_broken_links_payload(self):
        with patch("obsidian_client.broken_links", new_callable=AsyncMock) as mock:
            mock.return_value = []
            await use_obsidian(ObsidianAction(action="broken_links", payload="projects/"))
        mock.assert_called_once_with("projects/")


class TestParseJsonPayload:
    def test_valid(self):
        result = _parse_json_payload('{"file":"test.md","content":"hi"}', ["file", "content"])
        assert result["file"] == "test.md"

    def test_empty_payload(self):
        with pytest.raises(ValueError, match="Payload required"):
            _parse_json_payload(None)

    def test_invalid_json(self):
        with pytest.raises(ValueError, match="Invalid JSON"):
            _parse_json_payload("not json", ["file"])

    def test_missing_required(self):
        with pytest.raises(ValueError, match="Missing fields"):
            _parse_json_payload('{"file":"test.md"}', ["file", "content"])


class TestParsePeriodicPayload:
    def test_none(self):
        assert _parse_periodic_payload(None) == ("daily", None, None, None, False)

    def test_period_only(self):
        assert _parse_periodic_payload("weekly") == ("weekly", None, None, None, False)

    def test_with_date(self):
        assert _parse_periodic_payload("daily|2026|4|1") == ("daily", 2026, 4, 1, False)

    def test_with_json(self):
        assert _parse_periodic_payload("daily|json") == ("daily", None, None, None, True)

    def test_date_and_json(self):
        assert _parse_periodic_payload("monthly|2026|3|json") == ("monthly", 2026, 3, None, True)


class TestTagsAction:
    @pytest.mark.asyncio
    async def test_tags(self):
        with patch("obsidian_client.list_tags", new_callable=AsyncMock) as mock:
            mock.return_value = {"tags": [{"name": "test", "count": 5}]}
            result = await use_obsidian(ObsidianAction(action="tags"))
        parsed = json.loads(result)
        assert parsed["tags"][0]["name"] == "test"


class TestCommandsAction:
    @pytest.mark.asyncio
    async def test_commands(self):
        with patch("obsidian_client.list_commands", new_callable=AsyncMock) as mock:
            mock.return_value = {"commands": [{"id": "save", "name": "Save"}]}
            result = await use_obsidian(ObsidianAction(action="commands"))
        parsed = json.loads(result)
        assert parsed["commands"][0]["id"] == "save"

    @pytest.mark.asyncio
    async def test_command_run(self):
        with patch("obsidian_client.run_command", new_callable=AsyncMock) as mock:
            mock.return_value = {"status": "ok", "command": "editor:save"}
            result = await use_obsidian(ObsidianAction(action="command_run", payload="editor:save"))
        parsed = json.loads(result)
        assert parsed["command"] == "editor:save"

    @pytest.mark.asyncio
    async def test_command_run_no_payload(self):
        result = await use_obsidian(ObsidianAction(action="command_run"))
        assert "Payload required" in result


class TestOpenAction:
    @pytest.mark.asyncio
    async def test_open(self):
        with patch("obsidian_client.open_file", new_callable=AsyncMock) as mock:
            mock.return_value = {"status": "ok", "file": "index.md"}
            result = await use_obsidian(ObsidianAction(action="open", payload="index.md"))
        parsed = json.loads(result)
        assert parsed["file"] == "index.md"

    @pytest.mark.asyncio
    async def test_open_new_leaf(self):
        with patch("obsidian_client.open_file", new_callable=AsyncMock) as mock:
            mock.return_value = {"status": "ok"}
            await use_obsidian(ObsidianAction(action="open", payload="index.md|new"))
        mock.assert_called_once_with("index.md", new_leaf=True)


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_api_error(self):
        with patch("obsidian_client.list_dirs", new_callable=AsyncMock) as mock:
            mock.side_effect = Exception("Connection refused")
            result = await use_obsidian(ObsidianAction(action="list"))
        assert "Error" in result
        assert "Connection refused" in result
        assert "help" in result
