"""Obsidian Local REST API client — domain logic separated from MCP/CLI."""

from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx

DEFAULT_BASE_URL = "http://127.0.0.1:27123"


def _base_url() -> str:
    return os.environ.get("OBSIDIAN_API_URL", DEFAULT_BASE_URL).rstrip("/")


def _api_key() -> str:
    key = os.environ.get("OBSIDIAN_API_KEY")
    if not key:
        raise RuntimeError("OBSIDIAN_API_KEY not set. Export it: export OBSIDIAN_API_KEY=your-key-here")
    return key


def _headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    h = {"Authorization": f"Bearer {_api_key()}"}
    if extra:
        h.update(extra)
    return h


def _client(**kwargs: Any) -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=_base_url(), timeout=30.0, **kwargs)


# --- Vault CRUD ---


async def list_dirs(paths: list[str]) -> dict[str, dict]:
    """List one or more directories concurrently.

    Args:
        paths: Directory paths inside the vault.
               Empty list or ["/"] = vault root.

    Returns:
        {path: listing} dict. On per-path error, value has "error" key.
    """
    if not paths:
        paths = ["/"]

    async def _list_one(
        c: httpx.AsyncClient,
        path: str,
    ) -> tuple[str, dict]:
        try:
            url_path = path if path.endswith("/") else path + "/"
            if not url_path.startswith("/"):
                url_path = "/" + url_path
            r = await c.get(f"/vault{url_path}", headers=_headers())
            r.raise_for_status()
            return path, r.json()
        except Exception as e:
            return path, {"error": f"ERROR: {e}"}

    async with _client() as c:
        results = await asyncio.gather(*[_list_one(c, p) for p in paths])
    return dict(results)


async def read_files(
    paths: list[str],
    as_json: bool = False,
) -> dict[str, str | dict]:
    """Read one or more files concurrently.

    Args:
        paths: File paths inside the vault.
        as_json: If True, return structured JSON with frontmatter/tags/stat.

    Returns:
        {path: content} dict. On per-file error, value is error string
        prefixed with 'ERROR: '.
    """
    accept = "application/vnd.olrapi.note+json" if as_json else "text/markdown"

    async def _read_one(
        c: httpx.AsyncClient,
        path: str,
    ) -> tuple[str, str | dict]:
        try:
            r = await c.get(
                f"/vault/{path}",
                headers=_headers({"Accept": accept}),
            )
            r.raise_for_status()
            return path, r.json() if as_json else r.text
        except Exception as e:
            return path, f"ERROR: {e}"

    async with _client() as c:
        results = await asyncio.gather(*[_read_one(c, p) for p in paths])
    return dict(results)


async def write_file(filename: str, content: str) -> dict[str, Any]:
    """Create or replace a file in the vault.

    Args:
        filename: Path to the file inside the vault.
        content: Markdown content to write.
    """
    async with _client() as c:
        r = await c.put(
            f"/vault/{filename}",
            headers=_headers({"Content-Type": "text/markdown"}),
            content=content.encode("utf-8"),
        )
        r.raise_for_status()
        # API returns 204 No Content on success
        return {"status": "ok", "file": filename}


async def append_file(filename: str, content: str) -> dict[str, Any]:
    """Append content to an existing file.

    Args:
        filename: Path to the file inside the vault.
        content: Markdown content to append.
    """
    async with _client() as c:
        r = await c.post(
            f"/vault/{filename}",
            headers=_headers({"Content-Type": "text/markdown"}),
            content=content.encode("utf-8"),
        )
        r.raise_for_status()
        return {"status": "ok", "file": filename}


async def patch_file(
    filename: str,
    content: str,
    operation: str = "append",
    target_type: str = "heading",
    target: str = "",
) -> dict[str, Any]:
    """Partial update of a file — target a heading, block, or frontmatter.

    Args:
        filename: Path to the file inside the vault.
        content: Content to insert/replace.
        operation: "append", "prepend", or "replace".
        target_type: "heading", "block", or "frontmatter".
        target: Target identifier (heading text, block ID, or frontmatter key).
    """
    hdrs = _headers(
        {
            "Content-Type": "text/markdown",
            "Operation": operation,
            "Target-Type": target_type,
            "Target": target,
        }
    )
    async with _client() as c:
        r = await c.patch(
            f"/vault/{filename}",
            headers=hdrs,
            content=content.encode("utf-8"),
        )
        r.raise_for_status()
        return {"status": "ok", "file": filename}


async def delete_file(filename: str) -> dict[str, Any]:
    """Delete a file from the vault.

    Args:
        filename: Path to the file inside the vault.
    """
    async with _client() as c:
        r = await c.delete(
            f"/vault/{filename}",
            headers=_headers(),
        )
        r.raise_for_status()
        return {"status": "ok", "file": filename, "deleted": True}


# --- Search ---


async def search_simple(query: str, context_length: int = 100) -> list[dict[str, Any]]:
    """Simple text search across the vault.

    Args:
        query: Text to search for.
        context_length: Characters of context around each match.
    """
    async with _client() as c:
        r = await c.post(
            "/search/simple/",
            headers=_headers(),
            params={"query": query, "contextLength": context_length},
        )
        r.raise_for_status()
        return r.json()


async def search_advanced(
    query: str,
    query_type: str = "dataview",
) -> list[dict[str, Any]] | dict[str, Any]:
    """Advanced search using Dataview DQL or JsonLogic.

    Args:
        query: DQL query string or JSON-encoded JsonLogic object.
        query_type: "dataview" or "jsonlogic".
    """
    if query_type == "jsonlogic":
        content_type = "application/vnd.olrapi.jsonlogic+json"
    else:
        content_type = "application/vnd.olrapi.dataview.dql+txt"

    async with _client() as c:
        r = await c.post(
            "/search/",
            headers=_headers({"Content-Type": content_type}),
            content=query.encode("utf-8"),
        )
        r.raise_for_status()
        return r.json()


# --- Tags ---


async def list_tags() -> dict[str, Any]:
    """List all tags in the vault."""
    async with _client() as c:
        r = await c.get("/tags/", headers=_headers())
        r.raise_for_status()
        return r.json()


# --- Commands ---


async def list_commands() -> dict[str, Any]:
    """List all available Obsidian commands."""
    async with _client() as c:
        r = await c.get("/commands/", headers=_headers())
        r.raise_for_status()
        return r.json()


async def run_command(command_id: str) -> dict[str, Any]:
    """Execute an Obsidian command.

    Args:
        command_id: Command ID (e.g., "editor:save-file").
    """
    async with _client() as c:
        r = await c.post(
            f"/commands/{command_id}/",
            headers=_headers(),
        )
        r.raise_for_status()
        return {"status": "ok", "command": command_id}


# --- Open ---


async def open_file(filename: str, new_leaf: bool = False) -> dict[str, Any]:
    """Open a file in the Obsidian UI.

    Args:
        filename: Path to the file inside the vault.
        new_leaf: If True, open in a new tab.
    """
    async with _client() as c:
        r = await c.post(
            f"/open/{filename}",
            headers=_headers(),
            params={"newLeaf": str(new_leaf).lower()},
        )
        r.raise_for_status()
        return {"status": "ok", "file": filename, "new_leaf": new_leaf}


# --- Active File ---


async def active_read(as_json: bool = False) -> str | dict[str, Any]:
    """Read the currently active file in Obsidian."""
    accept = "application/vnd.olrapi.note+json" if as_json else "text/markdown"
    async with _client() as c:
        r = await c.get("/active/", headers=_headers({"Accept": accept}))
        r.raise_for_status()
        return r.json() if as_json else r.text


async def active_write(content: str) -> dict[str, Any]:
    """Replace the content of the currently active file."""
    async with _client() as c:
        r = await c.put(
            "/active/",
            headers=_headers({"Content-Type": "text/markdown"}),
            content=content.encode("utf-8"),
        )
        r.raise_for_status()
        return {"status": "ok", "target": "active_file"}


# --- Periodic Notes ---


async def periodic_read(
    period: str = "daily",
    year: int | None = None,
    month: int | None = None,
    day: int | None = None,
    as_json: bool = False,
) -> str | dict[str, Any]:
    """Read a periodic note (daily, weekly, monthly, quarterly, yearly).

    Args:
        period: Note period type.
        year: Specific year. If None, reads current period.
        month: Specific month.
        day: Specific day.
        as_json: Return structured JSON instead of markdown.
    """
    url = _periodic_url(period, year, month, day)
    accept = "application/vnd.olrapi.note+json" if as_json else "text/markdown"
    async with _client() as c:
        r = await c.get(url, headers=_headers({"Accept": accept}))
        r.raise_for_status()
        return r.json() if as_json else r.text


async def periodic_write(
    content: str,
    period: str = "daily",
    year: int | None = None,
    month: int | None = None,
    day: int | None = None,
) -> dict[str, Any]:
    """Create or replace a periodic note."""
    url = _periodic_url(period, year, month, day)
    async with _client() as c:
        r = await c.put(
            url,
            headers=_headers({"Content-Type": "text/markdown"}),
            content=content.encode("utf-8"),
        )
        r.raise_for_status()
        return {"status": "ok", "period": period}


async def periodic_append(
    content: str,
    period: str = "daily",
    year: int | None = None,
    month: int | None = None,
    day: int | None = None,
) -> dict[str, Any]:
    """Append content to a periodic note."""
    url = _periodic_url(period, year, month, day)
    async with _client() as c:
        r = await c.post(
            url,
            headers=_headers({"Content-Type": "text/markdown"}),
            content=content.encode("utf-8"),
        )
        r.raise_for_status()
        return {"status": "ok", "period": period}


def _periodic_url(
    period: str,
    year: int | None,
    month: int | None,
    day: int | None,
) -> str:
    base = f"/periodic/{period}/"
    if year is not None:
        parts = [str(year)]
        if month is not None:
            parts.append(str(month))
        if day is not None:
            parts.append(str(day))
        base += "/".join(parts) + "/"
    return base


# --- Status ---


async def server_status() -> dict[str, Any]:
    """Check Obsidian REST API server status (no auth required)."""
    async with _client() as c:
        r = await c.get("/")
        r.raise_for_status()
        return r.json()
