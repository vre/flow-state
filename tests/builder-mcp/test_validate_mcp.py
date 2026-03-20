"""Tests for validate_mcp.py."""

from __future__ import annotations

from conftest import load_builder_mcp_script

validate_mcp = load_builder_mcp_script("validate_mcp")


def _tool_code(docstring: str, *, with_instructions: bool = True, http: bool = False) -> str:
    instructions = ', instructions="Use for testing"' if with_instructions else ""
    run_call = 'mcp.run(transport="streamable-http")' if http else "mcp.run()"
    return f'''
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("test_mcp"{instructions})

@mcp.tool()
async def use_test() -> str:
    """{docstring}"""
    return "ok"

def main() -> None:
    {run_call}
'''


class TestValidateDiscoverability:
    def test_warns_when_server_instructions_are_missing(self):
        issues = validate_mcp.validate(
            _tool_code(
                "Find and inspect test records quickly with clear action guidance.",
                with_instructions=False,
            )
        )

        assert any("instructions" in issue.lower() for issue in issues)

    def test_warns_when_tool_description_is_too_short(self):
        issues = validate_mcp.validate(_tool_code("Test tool."))

        assert any("description" in issue.lower() and "<5 words" in issue for issue in issues)

    def test_warns_when_tool_description_is_too_long(self):
        long_description = " ".join(["word"] * 51)

        issues = validate_mcp.validate(_tool_code(long_description))

        assert any("description" in issue.lower() and ">50 words" in issue for issue in issues)

    def test_warns_when_http_transport_has_no_health_hint(self):
        issues = validate_mcp.validate(
            _tool_code(
                "Find and inspect test records quickly with clear action guidance.",
                http=True,
            )
        )

        assert any("health" in issue.lower() for issue in issues)

    def test_does_not_fail_for_http_without_auth(self):
        issues = validate_mcp.validate(
            _tool_code(
                "Find and inspect test records quickly with clear action guidance.",
                http=True,
            )
        )

        assert not any(issue.startswith("FAIL") and "auth" in issue.lower() for issue in issues)
