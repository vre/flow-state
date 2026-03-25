"""Tests for scripts/run.py."""

import importlib.util
from pathlib import Path
from typing import Any

import pytest

SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "run.py"


def _load_module() -> Any:
    """Load dispatcher script as an importable module."""
    assert SCRIPT_PATH.exists(), f"Missing script: {SCRIPT_PATH}"
    spec = importlib.util.spec_from_file_location("run_dispatcher_script", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_dispatch_passthrough_stdout_stderr_and_exit_code(tmp_path: Path, monkeypatch, capfd) -> None:
    """Dispatcher should preserve child stdout, stderr, and exit code."""
    module = _load_module()
    helper_dir = tmp_path / "helpers"
    helper_dir.mkdir()
    helper_script = helper_dir / "helper.py"
    helper_script.write_text("import sys\nprint('stdout from helper')\nprint('stderr from helper', file=sys.stderr)\nsys.exit(7)\n")

    other_dir = tmp_path / "cwd"
    other_dir.mkdir()
    monkeypatch.chdir(other_dir)
    monkeypatch.setattr(module, "SCRIPT_DIR", helper_dir)
    monkeypatch.setitem(module.SCRIPT_MAP, "check", helper_script.name)

    exit_code = module.main(["check", "alpha", "beta"])
    captured = capfd.readouterr()

    assert exit_code == 7
    assert "stdout from helper" in captured.out
    assert "stderr from helper" in captured.err


def test_dispatch_resolves_script_relative_to_run_py(monkeypatch, tmp_path: Path) -> None:
    """Dispatcher should resolve wrapped scripts from its own script directory."""
    module = _load_module()
    helper_dir = tmp_path / "helpers"
    helper_dir.mkdir()
    helper_script = helper_dir / "helper.py"
    helper_script.write_text("print('ok')\n")
    monkeypatch.setattr(module, "SCRIPT_DIR", helper_dir)
    monkeypatch.setitem(module.SCRIPT_MAP, "check", helper_script.name)

    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)

    recorded: list[list[str]] = []

    class _Result:
        """Simple subprocess result stub."""

        def __init__(self, returncode: int) -> None:
            self.returncode = returncode

    def fake_run(args: list[str]) -> _Result:
        recorded.append(args)
        return _Result(returncode=3)

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    exit_code = module.main(["check", "arg1"])

    assert exit_code == 3
    assert recorded == [[module.sys.executable, str(helper_script), "arg1"]]


def test_unknown_subcommand_errors(capsys) -> None:
    """Unknown commands should raise the standard argparse error."""
    module = _load_module()

    with pytest.raises(SystemExit) as exc_info:
        module.main(["unknown"])

    captured = capsys.readouterr()
    assert exc_info.value.code == 2
    assert "invalid choice" in captured.err


def test_missing_command_errors(capsys) -> None:
    """Missing subcommand should raise the standard argparse error."""
    module = _load_module()

    with pytest.raises(SystemExit) as exc_info:
        module.main([])

    captured = capsys.readouterr()
    assert exc_info.value.code == 2
    assert "required" in captured.err


def test_flag_creates_and_overwrites_marker_file(tmp_path: Path) -> None:
    """Flag should create or overwrite the marker file with 1 newline."""
    module = _load_module()
    marker_path = tmp_path / "requested.flag"

    exit_code_create = module.main(["flag", str(marker_path)])
    marker_path.write_text("stale\n")
    exit_code_overwrite = module.main(["flag", str(marker_path)])

    assert exit_code_create == 0
    assert exit_code_overwrite == 0
    assert marker_path.read_text() == "1\n"


def test_rm_removes_existing_file_and_ignores_missing(tmp_path: Path) -> None:
    """Rm should delete files when present and be harmless when absent."""
    module = _load_module()
    temp_path = tmp_path / "temp.md"
    temp_path.write_text("data")

    exit_code_existing = module.main(["rm", str(temp_path)])
    exit_code_missing = module.main(["rm", str(temp_path)])

    assert exit_code_existing == 0
    assert exit_code_missing == 0
    assert not temp_path.exists()


def test_guard_reports_ok_missing_and_oversize(tmp_path: Path, capsys) -> None:
    """Guard should always exit zero and describe the file state."""
    module = _load_module()
    transcript_path = tmp_path / "transcript.md"
    transcript_path.write_text("short")

    ok_exit = module.main(["guard", str(transcript_path), "--max-size", "10"])
    ok_output = capsys.readouterr().out.strip()

    missing_exit = module.main(["guard", str(tmp_path / "missing.md")])
    missing_output = capsys.readouterr().out.strip()

    transcript_path.write_text("x" * 11)
    oversize_exit = module.main(["guard", str(transcript_path), "--max-size", "10"])
    oversize_output = capsys.readouterr().out.strip()

    assert ok_exit == 0
    assert ok_output == "ok"
    assert missing_exit == 0
    assert missing_output.startswith("skip:")
    assert oversize_exit == 0
    assert oversize_output.startswith("skip:")


def test_paragraph_breaks_subcommand_registered() -> None:
    """Dispatcher should expose the deterministic paragraph-break command."""
    module = _load_module()
    parser = module.build_parser()
    namespace = parser.parse_args(["paragraph-breaks"])

    assert "paragraph-breaks" in module.SCRIPT_MAP
    assert namespace.command == "paragraph-breaks"
