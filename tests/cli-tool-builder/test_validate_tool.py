"""Tests for validate_tool.py."""

import sys
import textwrap
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "cli-tool-builder" / "scripts"))

from validate_tool import (
    check_dependency_count,
    check_error_suggestions,
    check_exit_codes,
    check_hardcoded_paths,
    check_help_action,
    check_quiet_flag,
    check_structure,
    validate,
)

# --- Fixtures ---


def _make_tool(tmp_path: Path, module: str = "my_tool", **overrides) -> Path:
    """Create a minimal valid tool directory.

    Returns tool_dir path. Pass file content overrides as kwargs:
        core="...", cli="...", pyproject="...", test_core="...", test_cli="..."
    """
    tool_dir = tmp_path / module
    pkg_dir = tool_dir / module
    test_dir = tool_dir / "tests"
    pkg_dir.mkdir(parents=True)
    test_dir.mkdir(parents=True)

    (pkg_dir / "__init__.py").write_text('"""Package."""\n')

    core_default = textwrap.dedent("""\
        from dataclasses import dataclass
        EXIT_OK = 0
        EXIT_ERROR = 1
        EXIT_USAGE = 2

        @dataclass
        class Result:
            data: object = None
            error: str | None = None
            exit_code: int = EXIT_OK
            @property
            def ok(self):
                return self.error is None

        def show_help(**kwargs):
            return Result(data=[])

        ACTIONS = {
            "list": lambda **kw: Result(),
            "help": show_help,
        }

        def dispatch(action, **kwargs):
            if action not in ACTIONS:
                valid = ", ".join(ACTIONS.keys())
                return Result(error=f"Unknown action '{action}'. Valid: {valid}", exit_code=EXIT_USAGE)
            return ACTIONS[action](**kwargs)

        def format_output(result, fmt="auto"):
            return str(result.data)
    """)

    cli_default = textwrap.dedent("""\
        import argparse
        import sys
        from .my_tool import dispatch, format_output, ACTIONS

        def build_parser():
            parser = argparse.ArgumentParser()
            parser.add_argument("action", nargs="?", default="help")
            parser.add_argument("--format", dest="output_format", default="auto")
            parser.add_argument("--quiet", "-q", action="store_true")
            parser.add_argument("--verbose", "-v", action="store_true")
            return parser

        def main(argv=None):
            parser = build_parser()
            args = parser.parse_args(argv)
            result = dispatch(args.action)
            if not args.quiet:
                print(format_output(result, fmt=args.output_format))
            return result.exit_code
    """)

    pyproject_default = textwrap.dedent("""\
        [project]
        name = "my-tool"
        version = "0.1.0"
        dependencies = []
    """)

    (pkg_dir / f"{module}.py").write_text(overrides.get("core", core_default))
    (pkg_dir / "cli.py").write_text(overrides.get("cli", cli_default))
    (tool_dir / "pyproject.toml").write_text(overrides.get("pyproject", pyproject_default))
    (test_dir / "__init__.py").write_text("")
    (test_dir / "test_core.py").write_text(overrides.get("test_core", "# tests\n"))
    (test_dir / "test_cli.py").write_text(overrides.get("test_cli", "# tests\n"))

    return tool_dir


@pytest.fixture()
def valid_tool(tmp_path: Path) -> Path:
    """A valid generated tool directory."""
    return _make_tool(tmp_path)


# --- check_structure ---


class TestCheckStructure:
    def test_valid_structure_passes(self, valid_tool: Path):
        issues = check_structure(valid_tool)
        assert issues == []

    def test_missing_core_module(self, tmp_path: Path):
        tool_dir = _make_tool(tmp_path)
        # Remove core module
        core = tool_dir / "my_tool" / "my_tool.py"
        core.unlink()
        issues = check_structure(tool_dir)
        assert any("my_tool.py" in i["msg"] for i in issues)

    def test_missing_cli(self, tmp_path: Path):
        tool_dir = _make_tool(tmp_path)
        (tool_dir / "my_tool" / "cli.py").unlink()
        issues = check_structure(tool_dir)
        assert any("cli.py" in i["msg"] for i in issues)

    def test_missing_pyproject(self, tmp_path: Path):
        tool_dir = _make_tool(tmp_path)
        (tool_dir / "pyproject.toml").unlink()
        issues = check_structure(tool_dir)
        assert any("pyproject.toml" in i["msg"] for i in issues)

    def test_missing_tests(self, tmp_path: Path):
        tool_dir = _make_tool(tmp_path)
        (tool_dir / "tests" / "test_core.py").unlink()
        issues = check_structure(tool_dir)
        assert any("test_core.py" in i["msg"] for i in issues)


# --- check_exit_codes ---


class TestCheckExitCodes:
    def test_valid_exit_codes(self):
        source = "EXIT_OK = 0\nEXIT_ERROR = 1\nEXIT_USAGE = 2\n"
        assert check_exit_codes(source) == []

    def test_missing_exit_ok(self):
        source = "EXIT_ERROR = 1\nEXIT_USAGE = 2\n"
        issues = check_exit_codes(source)
        assert any("EXIT_OK" in i["msg"] for i in issues)

    def test_missing_exit_usage(self):
        source = "EXIT_OK = 0\nEXIT_ERROR = 1\n"
        issues = check_exit_codes(source)
        assert any("EXIT_USAGE" in i["msg"] for i in issues)

    def test_all_missing(self):
        issues = check_exit_codes("pass\n")
        assert len(issues) == 3  # EXIT_OK, EXIT_ERROR, EXIT_USAGE


# --- check_hardcoded_paths ---


class TestCheckHardcodedPaths:
    def test_clean_source(self):
        sources = {"core.py": "x = Path.cwd()\n"}
        assert check_hardcoded_paths(sources) == []

    def test_detects_users_path(self):
        sources = {"core.py": 'base = "/Users/john/data"\n'}
        issues = check_hardcoded_paths(sources)
        assert len(issues) == 1
        assert "core.py" in issues[0]["file"]

    def test_detects_home_path(self):
        sources = {"cli.py": 'DEFAULT = "/home/user/.config"\n'}
        issues = check_hardcoded_paths(sources)
        assert len(issues) == 1

    def test_detects_windows_path(self):
        sources = {"core.py": r'path = "C:\Users\john"' + "\n"}
        issues = check_hardcoded_paths(sources)
        assert len(issues) == 1

    def test_ignores_comments(self):
        sources = {"core.py": "# Example: /Users/john/data\n"}
        issues = check_hardcoded_paths(sources)
        assert issues == []

    def test_multiple_files(self):
        sources = {
            "core.py": 'a = "/Users/x"\n',
            "cli.py": 'b = "/home/y"\n',
        }
        issues = check_hardcoded_paths(sources)
        assert len(issues) == 2


# --- check_dependency_count ---


class TestCheckDependencyCount:
    def test_zero_deps_passes(self):
        text = "[project]\ndependencies = []\n"
        assert check_dependency_count(text) == []

    def test_few_deps_warns(self):
        text = '[project]\ndependencies = [\n  "requests",\n  "click",\n  "rich",\n  "httpx",\n]\n'
        issues = check_dependency_count(text)
        assert len(issues) == 1
        assert issues[0].get("severity") == "warning"

    def test_no_dependencies_section(self):
        text = "[project]\nname = 'x'\n"
        issues = check_dependency_count(text)
        # No dependencies key at all — that's fine (treated as zero)
        assert issues == []


# --- check_error_suggestions ---


class TestCheckErrorSuggestions:
    def test_valid_error_with_suggestion(self):
        source = textwrap.dedent("""\
            def dispatch(action, **kwargs):
                if action not in ACTIONS:
                    valid = ", ".join(ACTIONS.keys())
                    return Result(error=f"Unknown action '{action}'. Valid: {valid}")
        """)
        assert check_error_suggestions(source) == []

    def test_bare_error_without_suggestion(self):
        source = textwrap.dedent("""\
            def dispatch(action, **kwargs):
                if action not in ACTIONS:
                    return Result(error=f"Unknown action '{action}'")
        """)
        issues = check_error_suggestions(source)
        assert len(issues) >= 1

    def test_try_suggestion_accepted(self):
        source = 'return Result(error=f"File not found. Try: ls {dir}")\n'
        assert check_error_suggestions(source) == []


# --- check_quiet_flag ---


class TestCheckQuietFlag:
    def test_valid_quiet_support(self):
        source = textwrap.dedent("""\
            parser.add_argument("--quiet", "-q", action="store_true")
            if not args.quiet:
                print(output)
        """)
        assert check_quiet_flag(source) == []

    def test_missing_quiet_flag(self):
        source = textwrap.dedent("""\
            parser.add_argument("--verbose", "-v", action="store_true")
        """)
        issues = check_quiet_flag(source)
        assert any("--quiet" in i["msg"] for i in issues)

    def test_quiet_declared_but_not_checked(self):
        source = textwrap.dedent("""\
            parser.add_argument("--quiet", "-q", action="store_true")
            print(output)
        """)
        issues = check_quiet_flag(source)
        assert any("quiet" in i["msg"].lower() for i in issues)


# --- check_help_action ---


class TestCheckHelpAction:
    def test_valid_help_action(self):
        source = 'ACTIONS = {\n    "list": list_action,\n    "help": show_help,\n}\n'
        assert check_help_action(source) == []

    def test_missing_help_in_actions(self):
        source = 'ACTIONS = {\n    "list": list_action,\n}\n'
        issues = check_help_action(source)
        assert any("help" in i["msg"] for i in issues)

    def test_no_actions_dict(self):
        source = "def do_thing(): pass\n"
        issues = check_help_action(source)
        assert any("ACTIONS" in i["msg"] for i in issues)


# --- validate (integration) ---


class TestValidate:
    def test_valid_tool_passes(self, valid_tool: Path):
        result = validate(valid_tool)
        errors = [i for i in result["issues"] if i.get("severity") != "warning"]
        assert result["pass"] is True, f"Unexpected errors: {errors}"

    def test_missing_files_fails(self, tmp_path: Path):
        tool_dir = tmp_path / "broken"
        tool_dir.mkdir()
        result = validate(tool_dir)
        assert result["pass"] is False

    def test_hardcoded_path_fails(self, tmp_path: Path):
        tool_dir = _make_tool(
            tmp_path,
            core=textwrap.dedent("""\
                EXIT_OK = 0
                EXIT_ERROR = 1
                EXIT_USAGE = 2
                ACTIONS = {"help": lambda: None}
                base = "/Users/john/data"
                def dispatch(action, **kwargs):
                    if action not in ACTIONS:
                        return None
                    return ACTIONS[action]()
            """),
        )
        result = validate(tool_dir)
        assert result["pass"] is False
        assert any("hardcoded" in i["msg"].lower() or "/Users" in i["msg"] for i in result["issues"])

    def test_result_format(self, valid_tool: Path):
        result = validate(valid_tool)
        assert "pass" in result
        assert "issues" in result
        assert isinstance(result["issues"], list)
