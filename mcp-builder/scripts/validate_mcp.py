#!/usr/bin/env python3
"""Validate a generated MCP server against quality rules.

Usage:
    python3 validate_mcp.py <mcp_server.py>

Exit codes: 0=pass, 1=has failures, 2=usage error.
"""

import json
import re
import sys
from pathlib import Path


def validate(code: str) -> list[str]:
    """Run deterministic checks on MCP server code.

    Returns list of issues (FAIL: fatal, WARN: advisory).
    """
    issues: list[str] = []

    # --- Fatal checks ---

    # stdout pollution: print() without stderr redirect
    for i, line in enumerate(code.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if "print(" in stripped and "file=sys.stderr" not in stripped:
            # Allow print in __main__ block for JSON output
            if "print(json.dumps" not in stripped:
                issues.append(f"FAIL: print() without stderr on line {i} - breaks JSON-RPC")

    # Tool count
    tool_count = len(re.findall(r"@mcp\.tool", code))
    if tool_count > 4:
        issues.append(f"FAIL: {tool_count} tools found - likely wrong abstraction, max 4")
    elif tool_count > 1:
        issues.append(f"WARN: {tool_count} tools found - justify why action dispatcher won't work")

    # Help action
    if '"help"' not in code and "'help'" not in code:
        issues.append("FAIL: No help action found - required for progressive documentation")

    # Action validator (allowlist)
    if "@field_validator" not in code and "validate_action" not in code:
        issues.append("FAIL: No action validator - use Pydantic field_validator with allowlist")

    # --- Warning checks ---

    # Tool annotations
    if "readOnlyHint" not in code:
        issues.append("WARN: Missing tool annotations (readOnlyHint, destructiveHint)")

    # Error suggestions
    has_suggestion = any(pattern in code for pattern in ["suggestion", "Try:", "Did you mean", "Example:", "Valid:"])
    if not has_suggestion:
        issues.append("WARN: Errors may not suggest fixes - add 'Try:' or 'Valid:' hints")

    # Pydantic model
    if "BaseModel" not in code:
        issues.append("WARN: No Pydantic model for input validation")

    # Tool description length
    docstrings = re.findall(r'"""(.*?)"""', code, re.DOTALL)
    for ds in docstrings:
        # Check tool docstrings (ones right after async def)
        first_line = ds.strip().split("\n")[0]
        words = first_line.split()
        if len(words) > 50:
            issues.append(f"WARN: Tool description >50 words ({len(words)} words)")
            break

    # Async handler
    if "async def use_" not in code and "async def " not in code:
        issues.append("WARN: No async handler - FastMCP expects async def")

    return issues


def main() -> None:
    """CLI entry point."""
    if len(sys.argv) != 2:
        print("Usage: python3 validate_mcp.py <mcp_server.py>", file=sys.stderr)
        sys.exit(2)

    filepath = Path(sys.argv[1])
    if not filepath.exists():
        print(f"File not found: {filepath}. Did you mean '{filepath.name}'?", file=sys.stderr)
        sys.exit(2)

    code = filepath.read_text()
    issues = validate(code)

    fails = [i for i in issues if i.startswith("FAIL")]
    warns = [i for i in issues if i.startswith("WARN")]

    result = {
        "file": str(filepath),
        "pass": len(fails) == 0,
        "fails": fails,
        "warnings": warns,
    }
    print(json.dumps(result, indent=2))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
