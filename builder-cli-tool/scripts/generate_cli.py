#!/usr/bin/env python3
"""Generate CLI tool skeleton from templates.

Usage:
    generate_cli.py --name <tool_name> --operations '["list","get","help"]' --output <dir>
    generate_cli.py --name <tool_name> --operations '["list","get","help"]'

Options:
    --name          Tool name (lowercase, valid Python identifier)
    --operations    JSON array of action names
    --output        Output directory (default: current directory)
    --description   Tool description (default: "<name> CLI tool")
    --help, -h      Show this help

Generates:
    <name>/<name>.py        Core logic with action dispatcher
    <name>/cli.py           CLI entry point with argparse
    <name>/__init__.py      Package init
    <name>/pyproject.toml   Project config with entry points
    <name>/tests/           Test stubs (TDD, failing)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from string import Template

SCRIPT_DIR = Path(__file__).parent.parent
TEMPLATE_DIR = SCRIPT_DIR / "templates"

RESERVED_ACTIONS = {"help"}  # Always included, don't generate stubs


def load_template(name: str) -> Template:
    """Load a template file as string.Template."""
    path = TEMPLATE_DIR / name
    if not path.exists():
        print(f"Error: Template not found: {path}", file=sys.stderr)
        print(f"Try: ls {TEMPLATE_DIR}", file=sys.stderr)
        sys.exit(1)
    return Template(path.read_text())


VALID_DOMAINS = {"api_client", "data_processor", "cli_wrapper", "system_utility", "general"}


def validate_name(name: str) -> tuple[str, str | None]:
    """Validate tool name is a valid Python identifier.

    Returns:
        (name, error) - error is None on success.
    """
    if not re.match(r"^[a-z][a-z0-9_]*$", name):
        suggestion = name.lower().replace("-", "_")
        return name, (
            f"Invalid tool name '{name}'. Must be lowercase, start with letter, contain only [a-z0-9_]. Try: --name \"{suggestion}\""
        )
    return name, None


def validate_operations(ops_json: str) -> tuple[list[str], str | None]:
    """Parse and validate operations JSON.

    Returns:
        (operations, error) - error is None on success.
    """
    try:
        ops = json.loads(ops_json)
    except json.JSONDecodeError as e:
        return [], f'Invalid JSON for --operations: {e}. Try: --operations \'["list", "get"]\''

    if not isinstance(ops, list) or not all(isinstance(o, str) for o in ops):
        return [], "--operations must be a JSON array of strings."

    if not ops:
        return [], '--operations must have at least one action. Try: --operations \'["list", "help"]\''

    # Ensure help is always present
    if "help" not in ops:
        ops.append("help")

    return ops, None


def validate_domain(domain: str) -> tuple[str, str | None]:
    """Validate domain is recognized.

    Returns:
        (domain, error) - error is None on success.
    """
    if domain not in VALID_DOMAINS:
        valid = ", ".join(sorted(VALID_DOMAINS))
        return domain, f"Unknown domain '{domain}'. Valid: {valid}"
    return domain, None


def generate_action_function(action: str) -> str:
    """Generate a stub action function."""
    return f'''def {action}_action(**kwargs) -> Result:
    """{action.capitalize()} items."""
    # TODO: Implement {action} logic
    raise NotImplementedError("{action} not yet implemented")
'''


def generate_action_registry(actions: list[str]) -> str:
    """Generate ACTIONS dict entries."""
    lines = []
    for action in actions:
        if action == "help":
            continue  # help is defined in the template
        lines.append(f'    "{action}": {action}_action,')
    return "\n".join(lines)


def generate_action_help_lines(actions: list[str]) -> str:
    """Generate help text for CLI docstring."""
    lines = []
    for action in actions:
        lines.append(f"    {action:20s} {action.capitalize()} items")
    return "\n".join(lines)


def generate_help_test_assertions(actions: list[str]) -> str:
    """Generate assertions that all actions appear in help output."""
    lines = []
    for action in actions:
        lines.append(f'        assert "{action}" in action_names')
    return "\n".join(lines)


def generate_action_test_class(action: str) -> str:
    """Generate a test class for one action."""
    class_name = "".join(word.capitalize() for word in action.split("_"))
    return f'''
class Test{class_name}Action:
    """{action.capitalize()} action tests. FAIL until implemented."""

    def test_{action}_returns_result(self):
        result = dispatch("{action}")
        assert isinstance(result, Result)

    def test_{action}_ok_on_success(self):
        result = dispatch("{action}")
        assert result.ok
        assert result.exit_code == 0
'''


def generate_core(tool_name: str, module_name: str, actions: list[str]) -> str:
    """Generate core module from template."""
    user_actions = [a for a in actions if a not in RESERVED_ACTIONS]
    action_functions = "\n\n".join(generate_action_function(a) for a in user_actions)
    action_registry = generate_action_registry(actions)

    template = load_template("core.py.tmpl")
    return template.safe_substitute(
        tool_name=tool_name,
        module_name=module_name,
        action_functions=action_functions,
        action_registry=action_registry,
    )


def generate_cli(tool_name: str, module_name: str, description: str, actions: list[str]) -> str:
    """Generate CLI entry point from template."""
    action_help_lines = generate_action_help_lines(actions)

    template = load_template("cli.py.tmpl")
    return template.safe_substitute(
        tool_name=tool_name,
        module_name=module_name,
        tool_description=description,
        action_help_lines=action_help_lines,
    )


def generate_pyproject(tool_name: str, module_name: str, description: str) -> str:
    """Generate pyproject.toml from template."""
    template = load_template("pyproject.toml.tmpl")
    return template.safe_substitute(
        tool_name=tool_name,
        module_name=module_name,
        tool_description=description,
    )


def generate_test_core(module_name: str, actions: list[str]) -> str:
    """Generate core test stubs from template."""
    user_actions = [a for a in actions if a not in RESERVED_ACTIONS]
    help_test_assertions = generate_help_test_assertions(actions)
    action_test_classes = "\n".join(generate_action_test_class(a) for a in user_actions)

    template = load_template("test_core.py.tmpl")
    return template.safe_substitute(
        tool_name=module_name,
        module_name=module_name,
        help_test_assertions=help_test_assertions,
        action_test_classes=action_test_classes,
    )


def generate_test_cli(module_name: str) -> str:
    """Generate CLI test stubs from template."""
    template = load_template("test_cli.py.tmpl")
    return template.safe_substitute(
        tool_name=module_name,
        module_name=module_name,
    )


def write_file(path: Path, content: str) -> None:
    """Write file, creating parent dirs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    print(f"  Created: {path}", file=sys.stderr)


def generate_security_helpers(tool_name: str) -> str:
    """Generate security helpers from template."""
    template = load_template("security_helpers.py.tmpl")
    return template.safe_substitute(tool_name=tool_name)


def generate(
    name: str,
    operations: list[str],
    output_dir: Path,
    description: str,
    domain: str = "general",
) -> None:
    """Generate complete CLI tool skeleton."""
    module_name = name.replace("-", "_")
    tool_dir = output_dir / module_name
    pkg_dir = tool_dir / module_name
    test_dir = tool_dir / "tests"

    print(f"Generating {name} with actions: {operations} (domain: {domain})", file=sys.stderr)

    # Core package
    write_file(pkg_dir / "__init__.py", f'"""{name} package."""\n')
    write_file(pkg_dir / f"{module_name}.py", generate_core(name, module_name, operations))
    write_file(pkg_dir / "cli.py", generate_cli(name, module_name, description, operations))

    # Security helpers for domains that handle paths or wrap CLIs
    if domain in ("data_processor", "cli_wrapper"):
        write_file(pkg_dir / "security.py", generate_security_helpers(name))

    # Project config (create or warn if exists)
    pyproject_path = tool_dir / "pyproject.toml"
    if pyproject_path.exists():
        print(
            f"  Warning: {pyproject_path} exists, not overwriting. Add entry points manually.",
            file=sys.stderr,
        )
    else:
        write_file(pyproject_path, generate_pyproject(name, module_name, description))

    # Tests
    write_file(test_dir / "__init__.py", "")
    write_file(test_dir / "test_core.py", generate_test_core(module_name, operations))
    write_file(test_dir / "test_cli.py", generate_test_cli(module_name))

    print("\nDone. Next steps:", file=sys.stderr)
    print(f"  cd {tool_dir}", file=sys.stderr)
    print("  uv run pytest tests/ -v  # Tests should FAIL (TDD)", file=sys.stderr)
    print(f"  # Implement actions in {module_name}/{module_name}.py", file=sys.stderr)
    print("  uv run pytest tests/ -v  # Tests should PASS", file=sys.stderr)


def generate_flat(
    name: str,
    operations: list[str],
    output_dir: Path,
    description: str,
) -> None:
    """Generate single-file CLI tool (no package structure)."""
    module_name = name.replace("-", "_")
    user_actions = [a for a in operations if a not in RESERVED_ACTIONS]
    action_functions = "\n\n".join(generate_action_function(a) for a in user_actions)
    action_registry = generate_action_registry(operations)
    action_help_lines = generate_action_help_lines(operations)

    template = load_template("flat.py.tmpl")
    content = template.safe_substitute(
        tool_name=name,
        tool_description=description,
        action_functions=action_functions,
        action_registry=action_registry,
        action_help_lines=action_help_lines,
    )
    write_file(output_dir / f"{module_name}.py", content)


def build_parser() -> argparse.ArgumentParser:
    """Build argument parser."""
    parser = argparse.ArgumentParser(
        description="Generate CLI tool skeleton with action dispatcher pattern.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--name", required=True, help="Tool name (lowercase, a-z0-9_)")
    parser.add_argument(
        "--operations",
        required=True,
        help='JSON array of action names, e.g. \'["list","get","create"]\'',
    )
    parser.add_argument(
        "--output",
        default=".",
        help="Output directory (default: current directory)",
    )
    parser.add_argument(
        "--description",
        default=None,
        help="Tool description (default: '<name> CLI tool')",
    )
    parser.add_argument(
        "--domain",
        default="general",
        choices=sorted(VALID_DOMAINS),
        help="Tool domain hint for conditional generation (default: general)",
    )
    parser.add_argument(
        "--flat",
        action="store_true",
        help="Generate single .py file (no package, no tests). For embedding in skill scripts/.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    name, err = validate_name(args.name)
    if err:
        print(f"Error: {err}", file=sys.stderr)
        return 2

    operations, err = validate_operations(args.operations)
    if err:
        print(f"Error: {err}", file=sys.stderr)
        return 2

    output_dir = Path(args.output)
    description = args.description or f"{name} CLI tool"

    if not output_dir.is_dir():
        print(f"Error: Output directory does not exist: {output_dir}", file=sys.stderr)
        print(f"Try: mkdir -p {output_dir}", file=sys.stderr)
        return 2

    if args.flat:
        generate_flat(name, operations, output_dir, description)
    else:
        domain, err = validate_domain(args.domain)
        if err:
            print(f"Error: {err}", file=sys.stderr)
            return 2
        generate(name, operations, output_dir, description, domain=domain)
    return 0


if __name__ == "__main__":
    sys.exit(main())
