"""Tests for generate_cli.py."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "builder-cli-tool" / "scripts"))

from generate_cli import (
    generate,
    generate_action_function,
    generate_action_registry,
    generate_cli,
    generate_core,
    generate_pyproject,
    generate_security_helpers,
    main,
    validate_domain,
    validate_name,
    validate_operations,
)

# --- validate_name ---


class TestValidateName:
    def test_valid_name(self):
        name, err = validate_name("bookmark_mgr")
        assert err is None
        assert name == "bookmark_mgr"

    def test_starts_with_number(self):
        _, err = validate_name("3tool")
        assert err is not None
        assert "Try:" in err

    def test_hyphen_rejected_with_suggestion(self):
        _, err = validate_name("my-tool")
        assert err is not None
        assert "my_tool" in err

    def test_uppercase_rejected(self):
        _, err = validate_name("MyTool")
        assert err is not None


# --- validate_operations ---


class TestValidateOperations:
    def test_valid_json_array(self):
        ops, err = validate_operations('["list", "get"]')
        assert err is None
        assert "list" in ops
        assert "help" in ops  # auto-added

    def test_invalid_json(self):
        _, err = validate_operations("not json")
        assert err is not None
        assert "Try:" in err

    def test_empty_array(self):
        _, err = validate_operations("[]")
        assert err is not None

    def test_non_array(self):
        _, err = validate_operations('"list"')
        assert err is not None

    def test_help_not_duplicated(self):
        ops, err = validate_operations('["list", "help"]')
        assert err is None
        assert ops.count("help") == 1


# --- validate_domain ---


class TestValidateDomain:
    def test_valid_domain(self):
        domain, err = validate_domain("api_client")
        assert err is None
        assert domain == "api_client"

    def test_invalid_domain(self):
        _, err = validate_domain("bogus")
        assert err is not None
        assert "Valid:" in err

    def test_general_default(self):
        domain, err = validate_domain("general")
        assert err is None


# --- generate_action_function ---


class TestGenerateActionFunction:
    def test_returns_function_def(self):
        code = generate_action_function("list")
        assert "def list_action" in code
        assert "Result" in code
        assert "NotImplementedError" in code

    def test_function_name_matches_action(self):
        code = generate_action_function("create")
        assert "def create_action" in code


# --- generate_action_registry ---


class TestGenerateActionRegistry:
    def test_maps_actions_to_functions(self):
        reg = generate_action_registry(["list", "get", "help"])
        assert '"list": list_action' in reg
        assert '"get": get_action' in reg
        assert "help" not in reg  # help is in template

    def test_single_action(self):
        reg = generate_action_registry(["create", "help"])
        assert '"create": create_action' in reg


# --- generate_core ---


class TestGenerateCore:
    def test_has_result_class(self):
        code = generate_core("my_tool", "my_tool", ["list", "help"])
        assert "class Result" in code
        assert "EXIT_OK" in code

    def test_has_actions_dict(self):
        code = generate_core("my_tool", "my_tool", ["list", "help"])
        assert "ACTIONS" in code
        assert '"list": list_action' in code

    def test_has_dispatch(self):
        code = generate_core("my_tool", "my_tool", ["list", "help"])
        assert "def dispatch" in code

    def test_has_format_output(self):
        code = generate_core("my_tool", "my_tool", ["list", "help"])
        assert "def format_output" in code


# --- generate_cli ---


class TestGenerateCli:
    def test_has_main(self):
        code = generate_cli("my_tool", "my_tool", "My tool", ["list", "help"])
        assert "def main" in code

    def test_has_argparse(self):
        code = generate_cli("my_tool", "my_tool", "My tool", ["list", "help"])
        assert "argparse" in code

    def test_has_quiet_flag(self):
        code = generate_cli("my_tool", "my_tool", "My tool", ["list", "help"])
        assert "--quiet" in code

    def test_has_load_env(self):
        code = generate_cli("my_tool", "my_tool", "My tool", ["list", "help"])
        assert "load_env" in code


# --- generate_pyproject ---


class TestGeneratePyproject:
    def test_has_project_name(self):
        text = generate_pyproject("my_tool", "my_tool", "My tool")
        assert "my_tool" in text

    def test_has_entry_point(self):
        text = generate_pyproject("my_tool", "my_tool", "My tool")
        assert "scripts" in text or "entry" in text.lower()


# --- generate_security_helpers ---


class TestGenerateSecurityHelpers:
    def test_has_safe_path(self):
        code = generate_security_helpers("my_tool")
        assert "def safe_path" in code

    def test_has_load_env(self):
        code = generate_security_helpers("my_tool")
        assert "def load_env" in code


# --- generate (full) ---


class TestGenerateFull:
    def test_creates_all_files(self, tmp_path: Path):
        generate("test_tool", ["list", "get", "help"], tmp_path, "Test tool")
        tool_dir = tmp_path / "test_tool"
        assert (tool_dir / "test_tool" / "test_tool.py").exists()
        assert (tool_dir / "test_tool" / "cli.py").exists()
        assert (tool_dir / "test_tool" / "__init__.py").exists()
        assert (tool_dir / "pyproject.toml").exists()
        assert (tool_dir / "tests" / "test_core.py").exists()
        assert (tool_dir / "tests" / "test_cli.py").exists()

    def test_no_security_for_general_domain(self, tmp_path: Path):
        generate("test_tool", ["list", "help"], tmp_path, "Test tool", domain="general")
        assert not (tmp_path / "test_tool" / "test_tool" / "security.py").exists()

    def test_security_for_cli_wrapper_domain(self, tmp_path: Path):
        generate("test_tool", ["list", "help"], tmp_path, "Test tool", domain="cli_wrapper")
        assert (tmp_path / "test_tool" / "test_tool" / "security.py").exists()

    def test_security_for_data_processor_domain(self, tmp_path: Path):
        generate("test_tool", ["list", "help"], tmp_path, "Test tool", domain="data_processor")
        assert (tmp_path / "test_tool" / "test_tool" / "security.py").exists()

    def test_pyproject_not_overwritten(self, tmp_path: Path):
        tool_dir = tmp_path / "test_tool"
        tool_dir.mkdir()
        (tool_dir / "pyproject.toml").write_text("existing\n")
        generate("test_tool", ["list", "help"], tmp_path, "Test tool")
        assert (tool_dir / "pyproject.toml").read_text() == "existing\n"


# --- main ---


class TestMain:
    def test_returns_0_on_success(self, tmp_path: Path):
        rc = main(
            [
                "--name",
                "test_tool",
                "--operations",
                '["list"]',
                "--output",
                str(tmp_path),
            ]
        )
        assert rc == 0

    def test_returns_2_on_bad_name(self, tmp_path: Path, capsys):
        rc = main(["--name", "Bad-Name!", "--operations", '["list"]', "--output", str(tmp_path)])
        assert rc == 2

    def test_returns_2_on_bad_operations(self, tmp_path: Path, capsys):
        rc = main(["--name", "test_tool", "--operations", "not_json", "--output", str(tmp_path)])
        assert rc == 2

    def test_returns_2_on_missing_output(self, tmp_path: Path, capsys):
        rc = main(["--name", "test_tool", "--operations", '["list"]', "--output", str(tmp_path / "nonexistent")])
        assert rc == 2


# --- Integration: bookmark manager ---


class TestBookmarkManagerIntegration:
    """End-to-end: generate bookmark_mgr and validate it."""

    @pytest.fixture()
    def bookmark_dir(self, tmp_path: Path) -> Path:
        generate(
            "bookmark_mgr",
            ["list", "add", "delete", "search", "help"],
            tmp_path,
            "Bookmark manager CLI",
        )
        return tmp_path / "bookmark_mgr"

    def test_all_files_created(self, bookmark_dir: Path):
        assert (bookmark_dir / "bookmark_mgr" / "bookmark_mgr.py").exists()
        assert (bookmark_dir / "bookmark_mgr" / "cli.py").exists()
        assert (bookmark_dir / "pyproject.toml").exists()
        assert (bookmark_dir / "tests" / "test_core.py").exists()
        assert (bookmark_dir / "tests" / "test_cli.py").exists()

    def test_generated_tests_fail_as_tdd_stubs(self, bookmark_dir: Path):
        """Generated tests should FAIL because actions raise NotImplementedError."""
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(bookmark_dir / "tests" / "test_core.py"), "-q"],
            capture_output=True,
            text=True,
            cwd=str(bookmark_dir),
            env={**__import__("os").environ, "PYTHONPATH": str(bookmark_dir)},
        )
        # Some tests pass (help, dispatch), some fail (action stubs)
        assert "failed" in result.stdout.lower() or result.returncode != 0

    def test_passes_validation(self, bookmark_dir: Path):
        """validate_tool.py should pass on the generated tool."""
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "builder-cli-tool" / "scripts"))
        from validate_tool import validate

        result = validate(bookmark_dir)
        errors = [i for i in result["issues"] if i.get("severity") != "warning"]
        assert result["pass"] is True, f"Validation errors: {errors}"

    def test_core_has_all_actions(self, bookmark_dir: Path):
        core = (bookmark_dir / "bookmark_mgr" / "bookmark_mgr.py").read_text()
        for action in ["list", "add", "delete", "search", "help"]:
            assert f'"{action}"' in core

    def test_pyproject_has_entry_point(self, bookmark_dir: Path):
        pyproject = (bookmark_dir / "pyproject.toml").read_text()
        assert "bookmark_mgr" in pyproject


# --- flat mode ---


class TestFlatMode:
    """Tests for --flat mode generating single-file CLI tools."""

    def _run_flat(self, tmp_path: Path, actions: list[str] | None = None) -> Path:
        """Run generate_cli in flat mode, return output dir."""
        ops = actions or ["list", "get"]
        rc = main(["--name", "test_tool", "--operations", json.dumps(ops), "--output", str(tmp_path), "--flat"])
        assert rc == 0
        return tmp_path

    def test_flat_creates_single_file(self, tmp_path: Path):
        out = self._run_flat(tmp_path)
        assert (out / "test_tool.py").exists()
        subdirs = [p for p in out.iterdir() if p.is_dir()]
        assert len(subdirs) == 0

    def test_flat_no_package_structure(self, tmp_path: Path):
        out = self._run_flat(tmp_path)
        assert not (out / "__init__.py").exists()
        assert not (out / "pyproject.toml").exists()
        assert not (out / "tests").exists()

    def test_flat_file_has_dispatch(self, tmp_path: Path):
        out = self._run_flat(tmp_path)
        content = (out / "test_tool.py").read_text()
        assert "def dispatch" in content
        assert "ACTIONS" in content

    def test_flat_file_has_argparse(self, tmp_path: Path):
        out = self._run_flat(tmp_path)
        content = (out / "test_tool.py").read_text()
        assert "ArgumentParser" in content

    def test_flat_file_has_result(self, tmp_path: Path):
        out = self._run_flat(tmp_path)
        content = (out / "test_tool.py").read_text()
        assert "class Result" in content

    def test_flat_file_passes_ast_parse(self, tmp_path: Path):
        import ast

        out = self._run_flat(tmp_path)
        content = (out / "test_tool.py").read_text()
        ast.parse(content)  # Should not raise

    def test_flat_file_has_all_actions(self, tmp_path: Path):
        out = self._run_flat(tmp_path, actions=["create", "list", "delete"])
        content = (out / "test_tool.py").read_text()
        assert "def create_action" in content
        assert "def list_action" in content
        assert "def delete_action" in content

    def test_non_flat_unchanged(self, tmp_path: Path):
        """Regression: non-flat mode still creates full package."""
        rc = main(["--name", "test_tool", "--operations", '["list"]', "--output", str(tmp_path)])
        assert rc == 0
        assert (tmp_path / "test_tool" / "test_tool" / "test_tool.py").exists()
        assert (tmp_path / "test_tool" / "pyproject.toml").exists()
        assert (tmp_path / "test_tool" / "tests").exists()
