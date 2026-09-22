"""The stateless CLI: argument mapping, exit codes, and the shared dispatcher.

There is no daemon to test. Each command connects, acts and exits, so the only
things worth guarding are that arguments become the same MailAction the MCP tool
receives, and that failure is distinguishable from success by exit code.
"""

from pathlib import Path
from unittest.mock import patch

import actions
import imapctl
import pytest
from actions import MailAction

REPO = Path(__file__).resolve().parent.parent.parent


class TestArgumentsBecomeAnAction:
    def test_list_supplies_preview_explicitly(self):
        """The model rejects a missing preview, so absence of the flag must mean
        False rather than unspecified."""
        args = imapctl.build_parser().parse_args(["list", "INBOX"])
        action = imapctl.to_action(args)
        assert action.action == "list"
        assert action.folder == "INBOX"
        assert action.preview is False

        args = imapctl.build_parser().parse_args(["list", "INBOX", "--preview"])
        assert imapctl.to_action(args).preview is True

    def test_search_carries_the_query_as_payload(self):
        args = imapctl.build_parser().parse_args(["search", "INBOX", "from:x@y.com", "--limit", "5"])
        action = imapctl.to_action(args)
        assert action.payload == "from:x@y.com"
        assert action.limit == 5
        assert action.preview is False

    def test_read_carries_the_message_spec(self):
        args = imapctl.build_parser().parse_args(["read", "INBOX", "1253:full"])
        assert imapctl.to_action(args).payload == "1253:full"

    def test_create_requires_and_carries_format(self):
        args = imapctl.build_parser().parse_args(["create", "--format", "plain", "--payload", '{"to":"a","subject":"b","body":"c"}'])
        action = imapctl.to_action(args)
        assert action.format == "plain"
        assert action.action == "create"

    def test_replace_carries_the_folder_holding_the_draft(self):
        args = imapctl.build_parser().parse_args(["replace", "Drafts", "--format", "markdown", "--payload", '{"id":1,"body":"x"}'])
        action = imapctl.to_action(args)
        assert action.action == "replace"
        assert action.folder == "Drafts"

    def test_edit_is_gone(self):
        """IMAP messages are immutable; what was called editing was always a replace."""
        with pytest.raises(SystemExit):
            imapctl.build_parser().parse_args(["edit", "Drafts", "--payload", "{}"])

    def test_create_without_format_is_a_usage_error(self):
        with pytest.raises(SystemExit) as exc:
            imapctl.build_parser().parse_args(["create", "--payload", "{}"])
        assert exc.value.code == imapctl.EXIT_USAGE

    def test_account_reaches_the_action(self):
        args = imapctl.build_parser().parse_args(["folders", "--account", "work"])
        assert imapctl.to_action(args).account == "work"

    def test_help_defaults_to_the_overview(self):
        args = imapctl.build_parser().parse_args(["help"])
        assert imapctl.to_action(args).payload == "overview"


class TestExitCodes:
    def test_no_subcommand_is_usage(self, capsys):
        assert imapctl.main([]) == imapctl.EXIT_USAGE

    def test_success_prints_to_stdout_and_exits_zero(self, capsys):
        with patch("actions.run_action", return_value="# Folders\n\n- INBOX") as run:
            code = imapctl.main(["folders"])
        assert code == imapctl.EXIT_OK
        out = capsys.readouterr()
        assert "INBOX" in out.out
        assert out.err == ""
        assert isinstance(run.call_args.args[0], MailAction)

    @pytest.mark.parametrize(
        "text",
        [
            "Error: Message 5 not found in 'INBOX'",
            "**Connection to the mail server was lost** (stage: command, after 30.0s).",
            "**Login rejected by the server** (stage: connect, after 1.0s).",
            "# IMAP Stream - Setup Required\n\nYour IMAP credentials are not configured yet.",
        ],
    )
    def test_a_failed_action_exits_one_and_writes_to_stderr(self, text, capsys):
        with patch("actions.run_action", return_value=actions.Failure(text)):
            code = imapctl.main(["folders"])
        assert code == imapctl.EXIT_ERROR
        out = capsys.readouterr()
        assert out.out == ""
        assert text.split("\n")[0] in out.err

    def test_quiet_prints_nothing_but_keeps_the_code(self, capsys):
        with patch("actions.run_action", return_value=actions.Failure("Error: nope")):
            code = imapctl.main(["-q", "folders"])
        assert code == imapctl.EXIT_ERROR
        out = capsys.readouterr()
        assert out.out == "" and out.err == ""

    def test_verbose_goes_to_stderr_and_leaves_stdout_alone(self, capsys):
        with patch("actions.run_action", return_value="# Folders"):
            imapctl.main(["-v", "folders", "--account", "work"])
        out = capsys.readouterr()
        assert "action=folders" in out.err
        assert out.out.strip() == "# Folders"


class TestOneDispatcherForBothFrontEnds:
    def test_the_cli_calls_the_same_function_the_tool_calls(self):
        """If the CLI grew its own dispatch, the two surfaces would drift silently."""
        import inspect

        source = inspect.getsource(imapctl)
        assert "actions.run_action" in source
        assert "if action ==" not in source

    def test_the_cli_does_not_import_fastmcp(self):
        """Importing the MCP stack here would cost the CLI the 40 MB it exists to avoid."""
        import ast

        tree = ast.parse((REPO / "imap-slim" / "imapctl.py").read_text())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        assert "mcp" not in imported
        assert "imap_stream_mcp" not in imported


class TestSkillDocument:
    SKILL = (REPO / "imap-slim" / "SKILL.md").read_text()

    def test_it_is_a_skill(self):
        assert self.SKILL.startswith("---\nname: imap-slim-cli")

    def test_it_says_there_is_no_daemon(self):
        assert "no daemon" in self.SKILL.lower()

    def test_it_states_the_draft_contract(self):
        assert "`--format` is **required**" in self.SKILL
        assert "keep the source" in self.SKILL.lower()

    def test_it_says_there_is_no_edit(self):
        """The action names describe IMAP: create appends, replace supersedes."""
        assert "There is no edit" in self.SKILL
        assert "imap-slim-cli create" in self.SKILL
        assert "imap-slim-cli replace" in self.SKILL
        assert "new id" in self.SKILL.lower()

    def test_it_warns_that_mail_is_untrusted(self):
        assert "EXTERNAL_EMAIL" in self.SKILL

    def test_the_marketplace_offers_it_as_a_skill(self):
        import json

        marketplace = json.loads((REPO / ".claude-plugin" / "marketplace.json").read_text())
        entry = next(p for p in marketplace["plugins"] if p["name"] == "imap-slim-cli")
        assert entry["source"] == "./imap-slim"
        assert entry["skills"] == ["./"]
        assert "mcpServers" not in entry, "the CLI entry must not start an MCP server"

    def test_no_mcp_config_is_auto_discovered_from_the_plugin_root(self):
        """The whole point of the skill is not paying for the tool schema.

        A .mcp.json at a plugin root is auto-discovered, so leaving one there
        would start the MCP server for the CLI install too and load the ~814
        tokens anyway - silently, with nothing failing.
        """
        assert not (REPO / "imap-slim" / ".mcp.json").exists(), "this would fire for both marketplace entries"
        assert (REPO / "imap-slim" / "mcp-server.json").exists()

        import json

        marketplace = json.loads((REPO / ".claude-plugin" / "marketplace.json").read_text())
        mcp_entry = next(p for p in marketplace["plugins"] if p["name"] == "imap-slim-mcp")
        assert mcp_entry["mcpServers"] == "./mcp-server.json", "the MCP entry must name its config explicitly"
