"""Tests for scripts/22_list_channel.py output behavior."""

import importlib.util
import json
from pathlib import Path


def _load_list_channel_module():
    """Load scripts/22_list_channel.py as a module."""
    script_path = Path(__file__).parent.parent / "scripts" / "22_list_channel.py"
    spec = importlib.util.spec_from_file_location("list_channel_script", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_list_channel_outputs_view_count_for_new_and_existing(tmp_path: Path, monkeypatch, capsys) -> None:
    """view_count from parse_channel_entry is preserved in script JSON output."""
    module = _load_list_channel_module()

    raw_entries = [{"id": "raw1"}, {"id": "raw2"}]
    parsed = {
        "raw1": {
            "video_id": "dQw4w9WgXcQ",
            "title": "New Video",
            "views": "1.5M",
            "view_count": 1_500_000,
            "duration": "10:00",
            "url": "https://youtube.com/watch?v=dQw4w9WgXcQ",
        },
        "raw2": {
            "video_id": "9bZkp7q19f0",
            "title": "Existing Video",
            "views": "2.1M",
            "view_count": 2_100_000,
            "duration": "4:13",
            "url": "https://youtube.com/watch?v=9bZkp7q19f0",
        },
    }

    monkeypatch.setattr(
        module,
        "list_channel_videos",
        lambda channel_url, offset, limit: raw_entries,
    )
    monkeypatch.setattr(
        module,
        "parse_channel_metadata",
        lambda entry: {
            "name": "Test Channel",
            "id": "UC123",
            "url": "https://youtube.com/@test",
            "total_videos": 2,
            "verified": False,
        },
    )
    monkeypatch.setattr(module, "parse_channel_entry", lambda entry: parsed[entry["id"]])
    monkeypatch.setattr(module, "find_output_dir", lambda base_dir, channel_id: None)
    monkeypatch.setattr(
        module,
        "match_existing_videos",
        lambda videos, output_dir: (
            [videos[0]],
            [{**videos[1], "stored_comments": "100"}],
        ),
    )
    monkeypatch.setattr(
        module,
        "suggest_output_dir",
        lambda base_dir, channel_name, channel_id: base_dir / "suggested",
    )
    monkeypatch.setattr(
        module.sys,
        "argv",
        ["22_list_channel.py", "https://youtube.com/@test", str(tmp_path)],
    )

    module.main()
    output = json.loads(capsys.readouterr().out)

    assert output["new_videos"][0]["video_id"] == "dQw4w9WgXcQ"
    assert output["new_videos"][0]["view_count"] == 1_500_000
    assert output["existing_videos"][0]["video_id"] == "9bZkp7q19f0"
    assert output["existing_videos"][0]["view_count"] == 2_100_000


def test_list_channel_default_limit_is_50(tmp_path: Path, monkeypatch, capsys) -> None:
    """Default limit is 50 and has_more uses effective limit."""
    module = _load_list_channel_module()
    calls: list[dict] = []
    raw_entries = [{"id": f"raw{i}"} for i in range(50)]

    def fake_list_channel_videos(channel_url, offset, limit):
        calls.append({"offset": offset, "limit": limit})
        return raw_entries

    monkeypatch.setattr(module, "list_channel_videos", fake_list_channel_videos)
    monkeypatch.setattr(
        module,
        "parse_channel_metadata",
        lambda entry: {
            "name": "Test Channel",
            "id": "UC123",
            "url": "https://youtube.com/@test",
            "total_videos": 50,
            "verified": False,
        },
    )
    monkeypatch.setattr(
        module,
        "parse_channel_entry",
        lambda entry: {
            "video_id": "dQw4w9WgXcQ",
            "title": "Video",
            "views": "1K",
            "view_count": 1000,
            "description": "desc",
            "duration": "1:00",
            "url": "https://youtube.com/watch?v=dQw4w9WgXcQ",
        },
    )
    monkeypatch.setattr(module, "find_output_dir", lambda base_dir, channel_id: None)
    monkeypatch.setattr(module, "suggest_output_dir", lambda base_dir, channel_name, channel_id: None)
    monkeypatch.setattr(
        module.sys,
        "argv",
        ["22_list_channel.py", "https://youtube.com/@test", str(tmp_path)],
    )

    module.main()
    output = json.loads(capsys.readouterr().out)
    assert calls == [{"offset": 0, "limit": 50}]
    assert output["page"]["count"] == 50
    assert output["page"]["has_more"] is True


def test_list_channel_custom_limit_and_offset(tmp_path: Path, monkeypatch, capsys) -> None:
    """--limit and --offset are parsed and forwarded to listing call."""
    module = _load_list_channel_module()
    calls: list[dict] = []
    raw_entries = [{"id": f"raw{i}"} for i in range(10)]

    def fake_list_channel_videos(channel_url, offset, limit):
        calls.append({"offset": offset, "limit": limit})
        return raw_entries

    monkeypatch.setattr(module, "list_channel_videos", fake_list_channel_videos)
    monkeypatch.setattr(
        module,
        "parse_channel_metadata",
        lambda entry: {
            "name": "Test Channel",
            "id": "UC123",
            "url": "https://youtube.com/@test",
            "total_videos": 60,
            "verified": False,
        },
    )
    monkeypatch.setattr(
        module,
        "parse_channel_entry",
        lambda entry: {
            "video_id": "dQw4w9WgXcQ",
            "title": "Video",
            "views": "1K",
            "view_count": 1000,
            "description": "desc",
            "duration": "1:00",
            "url": "https://youtube.com/watch?v=dQw4w9WgXcQ",
        },
    )
    monkeypatch.setattr(module, "find_output_dir", lambda base_dir, channel_id: None)
    monkeypatch.setattr(module, "suggest_output_dir", lambda base_dir, channel_name, channel_id: None)
    monkeypatch.setattr(
        module.sys,
        "argv",
        [
            "22_list_channel.py",
            "https://youtube.com/@test",
            str(tmp_path),
            "--offset",
            "100",
            "--limit",
            "10",
        ],
    )

    module.main()
    output = json.loads(capsys.readouterr().out)
    assert calls == [{"offset": 100, "limit": 10}]
    assert output["page"]["offset"] == 100
    assert output["page"]["count"] == 10
    assert output["page"]["has_more"] is True
