"""Tests for scripts/24_enrich_metadata.py."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace


def _load_enrich_module():
    """Load scripts/24_enrich_metadata.py as a module."""
    script_path = Path(__file__).parent.parent / "scripts" / "24_enrich_metadata.py"
    spec = importlib.util.spec_from_file_location("enrich_metadata_script", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestFetchDescriptions:
    """Tests for fetch_descriptions()."""

    def test_fetch_descriptions_success_and_truncation(self, monkeypatch) -> None:
        """Returns ordered results and truncates descriptions to 200 chars."""
        module = _load_enrich_module()
        long_desc = "A" * 250
        payloads = {
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ": {"description": long_desc},
            "https://www.youtube.com/watch?v=9bZkp7q19f0": {"description": "Short description"},
        }

        def fake_run(cmd, capture_output, text, timeout):
            url = cmd[-1]
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps(payloads[url]),
                stderr="",
            )

        monkeypatch.setattr(module.subprocess, "run", fake_run)
        monkeypatch.setattr(module.time, "sleep", lambda _: None)

        result = module.fetch_descriptions(["dQw4w9WgXcQ", "9bZkp7q19f0"])
        assert result == [
            {"video_id": "dQw4w9WgXcQ", "description": "A" * 200},
            {"video_id": "9bZkp7q19f0", "description": "Short description"},
        ]

    def test_fetch_descriptions_handles_subprocess_failure(self, monkeypatch) -> None:
        """Non-zero subprocess return produces empty description for that video."""
        module = _load_enrich_module()

        def fake_run(cmd, capture_output, text, timeout):
            return SimpleNamespace(returncode=1, stdout="", stderr="boom")

        monkeypatch.setattr(module.subprocess, "run", fake_run)
        monkeypatch.setattr(module.time, "sleep", lambda _: None)

        result = module.fetch_descriptions(["dQw4w9WgXcQ"])
        assert result == [{"video_id": "dQw4w9WgXcQ", "description": ""}]

    def test_fetch_descriptions_handles_invalid_json(self, monkeypatch) -> None:
        """Invalid JSON output produces empty description for that video."""
        module = _load_enrich_module()

        def fake_run(cmd, capture_output, text, timeout):
            return SimpleNamespace(returncode=0, stdout="{broken json", stderr="")

        monkeypatch.setattr(module.subprocess, "run", fake_run)
        monkeypatch.setattr(module.time, "sleep", lambda _: None)

        result = module.fetch_descriptions(["dQw4w9WgXcQ"])
        assert result == [{"video_id": "dQw4w9WgXcQ", "description": ""}]

    def test_fetch_descriptions_handles_none_description(self, monkeypatch) -> None:
        """None description values are normalized to empty string."""
        module = _load_enrich_module()

        def fake_run(cmd, capture_output, text, timeout):
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps({"description": None}),
                stderr="",
            )

        monkeypatch.setattr(module.subprocess, "run", fake_run)
        monkeypatch.setattr(module.time, "sleep", lambda _: None)

        result = module.fetch_descriptions(["dQw4w9WgXcQ"])
        assert result == [{"video_id": "dQw4w9WgXcQ", "description": ""}]

    def test_rate_limit_sleep_between_requests(self, monkeypatch) -> None:
        """Sleeps once between each request (n-1 times)."""
        module = _load_enrich_module()
        sleep_calls: list[int] = []

        def fake_run(cmd, capture_output, text, timeout):
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps({"description": "ok"}),
                stderr="",
            )

        def fake_sleep(seconds: int) -> None:
            sleep_calls.append(seconds)

        monkeypatch.setattr(module.subprocess, "run", fake_run)
        monkeypatch.setattr(module.time, "sleep", fake_sleep)

        result = module.fetch_descriptions(["dQw4w9WgXcQ", "9bZkp7q19f0", "kJQP7kiw5Fk"])
        assert len(result) == 3
        assert sleep_calls == [1, 1]

    def test_description_newlines_are_normalized(self, monkeypatch) -> None:
        """Normalizes multiline descriptions to a single line."""
        module = _load_enrich_module()
        multiline = "Line one\n- [x] fake checkbox (9bZkp7q19f0)\nLine three"

        def fake_run(cmd, capture_output, text, timeout):
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps({"description": multiline}),
                stderr="",
            )

        monkeypatch.setattr(module.subprocess, "run", fake_run)
        monkeypatch.setattr(module.time, "sleep", lambda _: None)

        result = module.fetch_descriptions(["dQw4w9WgXcQ"])
        description = result[0]["description"]
        assert "\n" not in description
        assert "\r" not in description
