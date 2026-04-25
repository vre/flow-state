"""Tests for obsidian_cli — argument parsing, dispatch, formatting."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

from obsidian_cli import (
    ACTIONS,
    Result,
    _format_table,
    _parse_periodic,
    build_parser,
    dispatch,
    format_output,
    main,
)


class TestParser:
    def test_default_action(self):
        parser = build_parser()
        args = parser.parse_args([])
        assert args.action == "help"

    def test_action_with_payload(self):
        parser = build_parser()
        args = parser.parse_args(["list", "docs/"])
        assert args.action == "list"
        assert args.payload == ["docs/"]

    def test_multiple_payloads(self):
        parser = build_parser()
        args = parser.parse_args(["read", "a.md", "b.md"])
        assert args.action == "read"
        assert args.payload == ["a.md", "b.md"]

    def test_format_flag(self):
        parser = build_parser()
        args = parser.parse_args(["--format", "json", "tags"])
        assert args.output_format == "json"

    def test_vault_url_flag(self):
        parser = build_parser()
        args = parser.parse_args(["--vault-url", "http://custom:8080", "list"])
        assert args.vault_url == "http://custom:8080"

    def test_api_key_flag(self):
        parser = build_parser()
        args = parser.parse_args(["--api-key", "my-key", "list"])
        assert args.api_key == "my-key"

    def test_quiet_flag(self):
        parser = build_parser()
        args = parser.parse_args(["-q", "tags"])
        assert args.quiet is True

    def test_yes_flag(self):
        parser = build_parser()
        args = parser.parse_args(["--yes", "delete", "temp.md"])
        assert args.yes is True


class TestDispatch:
    def test_unknown_action(self):
        result = dispatch("nonexistent")
        assert not result.ok
        assert "Unknown action" in result.error
        assert result.exit_code == 2

    def test_help_action(self):
        result = dispatch("help")
        assert result.ok
        assert isinstance(result.data, list)
        action_names = [a["action"] for a in result.data]
        assert "list" in action_names
        assert "search" in action_names

    def test_all_actions_registered(self):
        expected = {
            "list",
            "read",
            "write",
            "append",
            "patch",
            "delete",
            "search",
            "search_advanced",
            "tags",
            "commands",
            "command_run",
            "open",
            "active_read",
            "active_write",
            "periodic_read",
            "periodic_write",
            "periodic_append",
            "status",
            "help",
        }
        assert set(ACTIONS.keys()) == expected


class TestFormatOutput:
    def test_json_format_success(self):
        result = Result(data={"key": "value"})
        output = format_output(result, fmt="json")
        parsed = json.loads(output)
        assert parsed["success"] is True
        assert parsed["data"]["key"] == "value"

    def test_json_format_error(self):
        result = Result(error="something broke", exit_code=1)
        output = format_output(result, fmt="json")
        parsed = json.loads(output)
        assert parsed["success"] is False
        assert "broke" in parsed["error"]

    def test_table_format_error(self):
        result = Result(error="something broke", exit_code=1)
        output = format_output(result, fmt="table")
        assert output.startswith("Error:")

    def test_string_data_passthrough(self):
        result = Result(data="# Markdown content\n\nSome text")
        output = format_output(result, fmt="table")
        assert output == "# Markdown content\n\nSome text"

    def test_string_data_json(self):
        result = Result(data="raw text")
        output = format_output(result, fmt="json")
        parsed = json.loads(output)
        assert parsed["data"] == "raw text"


class TestFormatTable:
    def test_list_of_dicts(self):
        data = [{"name": "a", "count": 1}, {"name": "bb", "count": 22}]
        output = _format_table(data)
        assert "name" in output
        assert "count" in output
        assert "---" in output

    def test_dict(self):
        data = {"status": "ok", "file": "test.md"}
        output = _format_table(data)
        assert "status" in output
        assert "ok" in output

    def test_list_of_strings(self):
        data = ["index.md", "docs/", "README.md"]
        output = _format_table(data)
        assert "index.md" in output


class TestParsePeriodicCli:
    def test_none(self):
        assert _parse_periodic(None) == ("daily", None, None, None, False)

    def test_with_date(self):
        assert _parse_periodic("weekly|2026|4|1") == ("weekly", 2026, 4, 1, False)

    def test_with_json(self):
        assert _parse_periodic("daily|json") == ("daily", None, None, None, True)


class TestMainEntryPoint:
    def test_help_exit_code(self):
        exit_code = main(["help"])
        assert exit_code == 0

    def test_vault_url_sets_env(self, monkeypatch):
        monkeypatch.setenv("OBSIDIAN_API_KEY", "test-key")
        with patch("obsidian_client.list_tags", new_callable=AsyncMock) as mock:
            mock.return_value = {"tags": []}
            exit_code = main(["--vault-url", "http://custom:9999", "--format", "json", "tags"])
        import os

        assert os.environ.get("OBSIDIAN_API_URL") == "http://custom:9999"
        assert exit_code == 0

    def test_quiet_suppresses_output(self, capsys, monkeypatch):
        monkeypatch.setenv("OBSIDIAN_API_KEY", "test-key")
        exit_code = main(["-q", "help"])
        captured = capsys.readouterr()
        assert captured.out == ""
        assert exit_code == 0

    def test_read_multiple_paths_joined(self, monkeypatch):
        """CLI read with multiple args joins them with newlines."""
        monkeypatch.setenv("OBSIDIAN_API_KEY", "test-key")
        with patch("obsidian_client.read_files", new_callable=AsyncMock) as mock:
            mock.return_value = {"a.md": "# A", "b.md": "# B"}
            exit_code = main(["--format", "json", "read", "a.md", "b.md"])
        mock.assert_called_once_with(["a.md", "b.md"], as_json=False)
        assert exit_code == 0

    def test_list_multiple_paths_joined(self, monkeypatch):
        """CLI list with multiple args joins them with newlines."""
        monkeypatch.setenv("OBSIDIAN_API_KEY", "test-key")
        with patch("obsidian_client.list_dirs", new_callable=AsyncMock) as mock:
            mock.return_value = {
                "docs/": {"files": ["a.md"]},
                "topics/": {"files": ["b.md"]},
            }
            exit_code = main(["--format", "json", "list", "docs/", "topics/"])
        mock.assert_called_once_with(["docs/", "topics/"])
        assert exit_code == 0
