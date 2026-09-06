"""AC9/AC10: the contract must be readable in what a session already loads.

Everything inside `payload` is a JSON string, so none of it reaches the tool
schema. These tests guard the two surfaces that do: the tool docstring and the
field descriptions, plus the examples, which must all be callable as written.
"""

import re

import imap_stream_mcp as mcp_mod
from imap_stream_mcp import HELP_TOPICS, MailAction, use_mail

# Measured 2026-08-26 before this cut: docstring 1357 + field descriptions 562.
BASELINE = 1919
BUDGET = 330


def _description_text() -> str:
    doc = use_mail.__doc__ or ""
    fields = "".join(f.description or "" for f in MailAction.model_fields.values())
    return doc + fields


class TestAlwaysLoadedDescription:
    def test_states_the_two_modes_and_that_choosing_is_required(self):
        text = _description_text().lower()
        assert "markdown" in text
        assert "plain" in text
        assert "required" in text

    def test_states_the_newline_rule(self):
        text = _description_text().lower()
        assert "line break" in text
        assert "paragraph" in text

    def test_states_that_plain_is_verbatim(self):
        text = _description_text().lower()
        assert "as written" in text or "verbatim" in text
        assert "no html" in text

    def test_stays_within_the_description_text_budget(self):
        """Prose only. The property name, type, enum and default also occupy
        served-schema space and are deliberately outside this number."""
        size = len(_description_text())
        assert size <= BASELINE + BUDGET, f"{size} chars, budget {BASELINE + BUDGET}"


class TestSchemaExposesTheChoice:
    """AC2: the values must be visible in the schema, not only in prose."""

    def test_format_is_a_top_level_property_with_both_values(self):
        schema = MailAction.model_json_schema()
        prop = schema["properties"]["format"]
        branches = prop.get("anyOf", [prop])
        enums = [b["enum"] for b in branches if "enum" in b]
        assert enums, f"no enum branch in {prop}"
        assert set(enums[0]) == {"markdown", "plain"}
        assert any(b.get("type") == "null" for b in branches), "must stay nullable"
        assert prop.get("default") is None
        assert "required" in (prop.get("description") or "").lower()

    def test_the_served_schema_matches(self):
        """model_json_schema() is pre-FastMCP; assert what is actually served.

        FastMCP wraps the single `params: MailAction` argument, so the served
        schema is {properties: {params: $ref}} with MailAction under $defs. The
        enum reaches the model, one level deeper than the annotation suggests.
        """
        served = mcp_mod.mcp._tool_manager.get_tool("use_mail").parameters
        assert list(served["properties"]) == ["params"]
        prop = served["$defs"]["MailAction"]["properties"]["format"]
        branches = prop.get("anyOf", [prop])
        enums = [b["enum"] for b in branches if "enum" in b]
        assert enums and set(enums[0]) == {"markdown", "plain"}
        assert "required" in (prop.get("description") or "").lower()


class TestExamplesAreValidCalls:
    """AC10: an example that would be rejected teaches the wrong thing."""

    def _draft_examples(self) -> list[str]:
        sources = [use_mail.__doc__ or ""] + list(HELP_TOPICS.values())
        examples = []
        for source in sources:
            for line in source.split("\n"):
                if 'action: "draft"' in line or 'action:"draft"' in line:
                    examples.append(line)
        return examples

    def test_there_are_examples_to_check(self):
        assert self._draft_examples()

    def test_every_draft_example_carries_a_top_level_format(self):
        for line in self._draft_examples():
            assert re.search(r'format:\s*"', line), f"no top-level format: {line}"

    def test_no_example_puts_format_inside_the_payload(self):
        for line in self._draft_examples():
            payload = line.split("payload:", 1)[1] if "payload:" in line else ""
            assert '"format"' not in payload, f"format inside payload: {line}"

    def test_nothing_calls_markdown_the_default(self):
        haystack = (use_mail.__doc__ or "") + HELP_TOPICS["draft"]
        assert "markdown" in haystack
        assert "(default" not in haystack.lower()


class TestDraftHelpMatchesBehaviour:
    def test_format_section_covers_both_modes_and_precedence(self):
        draft_help = HELP_TOPICS["draft"].lower()
        assert "markdown" in draft_help and "plain" in draft_help
        assert "line break" in draft_help
        assert "block syntax" in draft_help
        assert "no default" in draft_help


class TestHelpNamesCodeAndTables:
    """AC8: the help said these were unsupported; they are now supported."""

    def test_help_does_not_claim_they_are_unsupported(self):
        draft_help = HELP_TOPICS["draft"]
        assert "NOT supported" not in draft_help
        assert "not supported yet" not in draft_help.lower()

    def test_help_names_them(self):
        draft_help = HELP_TOPICS["draft"].lower()
        assert "code block" in draft_help
        assert "table" in draft_help
        assert "left margin" in draft_help, "the column-zero requirement must be stated"


class TestTheSurfaceIsDefinedOnce:
    """Cut 4a: the dispatcher moved to actions.py so the daemon and CLI can
    reach it without importing FastMCP. These guard the seams that move made."""

    def test_use_mail_only_delegates(self):
        import inspect

        source = inspect.getsource(use_mail)
        body = source.split('"""')[-1]
        assert "run_action" in body
        assert "if action ==" not in body, "dispatch logic must live in actions.py, not the wrapper"

    def test_actions_imports_no_front_end(self):
        """Checked on the AST, not by grep: a comment naming fastmcp would pass a grep.

        If actions.py imported FastMCP, the CLI would pay the 40 MB it exists to avoid.
        """
        import ast
        from pathlib import Path

        tree = ast.parse((Path(mcp_mod.__file__).parent / "actions.py").read_text())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        assert "mcp" not in imported
        assert "imap_stream_mcp" not in imported
        assert "imapctl" not in imported

    def test_the_served_schema_did_not_move(self):
        """Pinned against a literal recorded before the extraction.

        Comparing the schema to a freshly computed copy of itself would prove
        nothing; this file is what makes a future change to the advertised
        surface a deliberate edit.
        """
        import json
        from pathlib import Path

        recorded = json.loads((Path(__file__).parent / "use_mail_schema.json").read_text())
        served = mcp_mod.mcp._tool_manager.get_tool("use_mail").parameters
        assert json.dumps(served, sort_keys=True) == json.dumps(recorded, sort_keys=True)

    def test_the_wrapper_is_still_what_fastmcp_introspects(self):
        import inspect

        assert inspect.iscoroutinefunction(use_mail)
        params = list(inspect.signature(use_mail).parameters.values())
        assert len(params) == 1
        assert params[0].annotation is MailAction
        assert inspect.signature(use_mail).return_annotation is str
        assert "EXTERNAL_EMAIL" in (use_mail.__doc__ or ""), "the untrusted-content notice must stay on the wrapper"
