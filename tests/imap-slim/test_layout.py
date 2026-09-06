"""AC2/AC5: the rename must not break an existing install, and render.py must
hold the shared helpers rather than a copy of them.

These guard repo structure rather than behaviour, which is unusual in a plugin
test suite. They earn their place because the compatibility symlink is the only
reason an already-installed plugin keeps working after the directory was renamed
- deleting it would break the user's mail tool with nothing failing in CI.
"""

from pathlib import Path

import imap_stream_mcp
import render

REPO = Path(__file__).resolve().parent.parent.parent


class TestOldPathsStillResolve:
    def test_package_directory_is_imap_slim(self):
        assert (REPO / "imap-slim" / "imap_stream_mcp.py").is_file()

    def test_the_previous_names_are_symlinks_to_it(self):
        for legacy in ("imap-slim-mcp", "imap-stream-mcp"):
            link = REPO / legacy
            assert link.is_symlink(), f"{legacy} must stay a symlink so installed plugins keep working"
            assert link.readlink().name == "imap-slim", f"{legacy} must point at imap-slim, not at another symlink"

    def test_a_file_opens_through_each_legacy_path(self):
        canonical = (REPO / "imap-slim" / "pyproject.toml").read_text()
        for legacy in ("imap-slim-mcp", "imap-stream-mcp"):
            assert (REPO / legacy / "pyproject.toml").read_text() == canonical

    def test_marketplace_points_at_the_real_directory(self):
        import json

        marketplace = json.loads((REPO / ".claude-plugin" / "marketplace.json").read_text())
        entry = next(p for p in marketplace["plugins"] if p["name"] == "imap-slim-mcp")
        assert entry["source"] == "./imap-slim"


class TestRenderHoldsTheSharedHelpers:
    """POTENTIAL_INJECTION_NOTICE is deliberately absent: nothing in imap-slim
    referenced it, before this cut or after. It was dead in imap_stream_mcp.py
    and was not carried into a new module. youtube-to-markdown has its own
    same-named constant, which is unrelated."""

    SHARED = (
        "format_flags",
        "format_attachment_line",
        "format_description",
        "classify_connection_error",
        "POTENTIAL_INJECTION_WARNING",
    )

    def test_render_defines_them(self):
        for name in self.SHARED:
            assert hasattr(render, name), f"render.{name} missing"

    def test_the_mcp_module_imports_rather_than_redefines(self):
        for name in self.SHARED:
            mine = getattr(imap_stream_mcp, name)
            theirs = getattr(render, name)
            assert mine is theirs, f"{name} is a copy, not the shared one"
