#!/usr/bin/env python3
"""Validate generated CLI tool: structure, patterns, exit codes, deps.

Usage:
    validate_tool.py <tool_dir>

Checks:
    - Required files exist (core, cli, pyproject, tests)
    - EXIT_OK/EXIT_ERROR/EXIT_USAGE constants defined
    - No hardcoded paths (/Users/, /home/, C:\\)
    - Dependency count within limits
    - Error messages contain actionable suggestions
    - --quiet flag supported in CLI
    - help action in ACTIONS dict
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REQUIRED_EXIT_CODES = ("EXIT_OK", "EXIT_ERROR", "EXIT_USAGE")
MAX_DEPS = 3  # warn above this

HARDCODED_PATH_RE = re.compile(
    r"""(?x)
    /Users/\w+          |
    /home/\w+           |
    /root\b             |
    [A-Z]:\\(?:Users|Program)
    """
)

SUGGESTION_PATTERNS = re.compile(r"(?:Try:|Valid:|Did you mean|Hint:)", re.IGNORECASE)

ERROR_RETURN_RE = re.compile(
    r'Result\(\s*error\s*=\s*f?"([^"]*)"|'
    r"Result\(\s*error\s*=\s*f?'([^']*)'",
)


def _detect_module(tool_dir: Path) -> str | None:
    """Detect module name from tool directory.

    Looks for a subdirectory containing __init__.py.
    """
    for child in sorted(tool_dir.iterdir()):
        if child.is_dir() and (child / "__init__.py").exists():
            if child.name not in ("tests",):
                return child.name
    return None


def check_structure(tool_dir: Path) -> list[dict]:
    """Verify required files exist."""
    issues: list[dict] = []
    module = _detect_module(tool_dir)

    if module is None:
        issues.append({"msg": "No Python package found (missing __init__.py)"})
        return issues

    required = [
        (tool_dir / module / f"{module}.py", f"{module}/{module}.py (core module)"),
        (tool_dir / module / "cli.py", f"{module}/cli.py"),
        (tool_dir / module / "__init__.py", f"{module}/__init__.py"),
        (tool_dir / "pyproject.toml", "pyproject.toml"),
        (tool_dir / "tests" / "test_core.py", "tests/test_core.py"),
        (tool_dir / "tests" / "test_cli.py", "tests/test_cli.py"),
    ]

    for path, label in required:
        if not path.exists():
            issues.append({"msg": f"Missing required file: {label}"})

    return issues


def check_exit_codes(core_source: str) -> list[dict]:
    """Verify EXIT_* constants are defined."""
    issues: list[dict] = []
    for code in REQUIRED_EXIT_CODES:
        if not re.search(rf"^{code}\s*=", core_source, re.MULTILINE):
            issues.append({"msg": f"Missing exit code constant: {code}"})
    return issues


def check_hardcoded_paths(sources: dict[str, str]) -> list[dict]:
    """Scan source files for hardcoded paths."""
    issues: list[dict] = []
    for filename, content in sources.items():
        for i, line in enumerate(content.splitlines(), start=1):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            if HARDCODED_PATH_RE.search(line):
                issues.append(
                    {
                        "file": filename,
                        "line": i,
                        "msg": f"Hardcoded path detected: {line.strip()}",
                    }
                )
    return issues


def check_dependency_count(pyproject_text: str) -> list[dict]:
    """Check number of required dependencies."""
    issues: list[dict] = []

    match = re.search(
        r"dependencies\s*=\s*\[(.*?)\]",
        pyproject_text,
        re.DOTALL,
    )
    if not match:
        return []

    deps_block = match.group(1)
    deps = [d.strip().strip('"').strip("'") for d in deps_block.split(",") if d.strip() and d.strip().strip('"').strip("'")]

    if len(deps) > MAX_DEPS:
        issues.append(
            {
                "severity": "warning",
                "msg": f"High dependency count: {len(deps)} > {MAX_DEPS}. Prefer stdlib where possible.",
            }
        )
    return issues


def check_error_suggestions(core_source: str) -> list[dict]:
    """Verify error messages contain actionable suggestions."""
    issues: list[dict] = []

    for match in ERROR_RETURN_RE.finditer(core_source):
        error_msg = match.group(1) or match.group(2) or ""
        if not SUGGESTION_PATTERNS.search(error_msg):
            issues.append(
                {
                    "msg": f"Error message lacks suggestion: {error_msg[:60]}...",
                }
            )
    return issues


def check_quiet_flag(cli_source: str) -> list[dict]:
    """Verify --quiet flag is supported."""
    issues: list[dict] = []

    if "--quiet" not in cli_source:
        issues.append({"msg": "Missing --quiet flag in CLI"})
        return issues

    if "args.quiet" not in cli_source and "quiet" not in cli_source.split("args.")[1:]:
        issues.append({"msg": "Flag --quiet declared but never checked"})

    return issues


def check_help_action(core_source: str) -> list[dict]:
    """Verify help action exists in ACTIONS dict."""
    issues: list[dict] = []

    if not re.search(r"^ACTIONS\s*[=:]", core_source, re.MULTILINE):
        issues.append({"msg": "No ACTIONS dict found in core module"})
        return issues

    if '"help"' not in core_source and "'help'" not in core_source:
        issues.append({"msg": "No 'help' action in ACTIONS dict"})

    return issues


def validate(tool_dir: Path) -> dict:
    """Run all checks on a generated tool directory.

    Args:
        tool_dir: Path to the tool root directory.

    Returns:
        Dict with "pass" (bool) and "issues" (list of dicts).
    """
    issues: list[dict] = []

    # Structure check
    structure_issues = check_structure(tool_dir)
    issues.extend(structure_issues)

    # If structure is broken, skip source analysis
    if structure_issues:
        errors = [i for i in issues if i.get("severity") != "warning"]
        return {"pass": len(errors) == 0, "issues": issues}

    module = _detect_module(tool_dir)
    pkg_dir = tool_dir / module

    core_path = pkg_dir / f"{module}.py"
    cli_path = pkg_dir / "cli.py"
    pyproject_path = tool_dir / "pyproject.toml"

    core_source = core_path.read_text()
    cli_source = cli_path.read_text()
    pyproject_text = pyproject_path.read_text()

    # Collect all .py sources for path scanning
    sources = {}
    for py_file in pkg_dir.glob("*.py"):
        sources[py_file.name] = py_file.read_text()

    # Run checks
    issues.extend(check_exit_codes(core_source))
    issues.extend(check_hardcoded_paths(sources))
    issues.extend(check_dependency_count(pyproject_text))
    issues.extend(check_error_suggestions(core_source))
    issues.extend(check_quiet_flag(cli_source))
    issues.extend(check_help_action(core_source))

    errors = [i for i in issues if i.get("severity") != "warning"]
    return {"pass": len(errors) == 0, "issues": issues}


def validate_dir(dir_path: str) -> dict:
    """Validate a tool directory from CLI arg.

    Args:
        dir_path: Path to tool directory.

    Returns:
        Validation result dict.
    """
    path = Path(dir_path)
    if not path.is_dir():
        print(f"Error: {dir_path} is not a directory.", file=sys.stderr)
        print(f"Try: ls {dir_path}", file=sys.stderr)
        raise SystemExit(2)
    return validate(path)


def main() -> None:
    """CLI entry point."""
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <tool_dir>", file=sys.stderr)
        raise SystemExit(2)

    result = validate_dir(sys.argv[1])
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["pass"] else 1)


if __name__ == "__main__":
    main()
