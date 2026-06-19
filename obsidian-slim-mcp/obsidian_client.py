"""Obsidian Local REST API client — domain logic separated from MCP/CLI."""

from __future__ import annotations

import asyncio
import os
import re
from posixpath import dirname, normpath
from posixpath import join as pjoin
from typing import Any

import httpx
import yaml

DEFAULT_BASE_URL = "http://127.0.0.1:27123"


SETUP_GUIDE = """# Obsidian setup for this MCP (HTTP / localhost — recommended)

1. In Obsidian: Settings → Community plugins → install "Local REST API", enable it.
2. Open its settings. By default it serves HTTPS on port 27124; plain HTTP is OFF.
3. Turn on "Enable Non-encrypted (HTTP) Server". HTTP is enough on localhost —
   traffic never leaves the machine, and it avoids the self-signed-certificate
   hassle of HTTPS. Note the HTTP port (default 27123).
4. Per vault: every Obsidian vault that runs the plugin needs its OWN unique
   "Server Port". Two open vaults on the same port collide — one wins, the other
   looks broken.
5. Copy the API key from the plugin settings. Configure this MCP with the port
   and key FROM THE SAME VAULT — they are a pair, always copy them together:
     OBSIDIAN_API_URL=http://127.0.0.1:<that vault's HTTP port>
     OBSIDIAN_API_KEY=<that vault's API key>"""


_NO_KEY_REACHABLE = (
    "A Local REST API server is reachable at {url}, but OBSIDIAN_API_KEY is not "
    "set — set it (from this vault's plugin settings) and you're done.\n\n"
)

_NO_KEY_UNREACHABLE = "OBSIDIAN_API_KEY is not set, and nothing is answering at {url} yet — both need fixing.\n\n"

_UNAUTHED_MSG = (
    "Reached a Local REST API server at {url}, but it rejected the key (HTTP "
    "{code}). Two possible causes — this MCP cannot tell which:\n"
    "  (a) the API key is wrong or stale for this vault, or\n"
    "  (b) the key is fine, but {url}'s port belongs to a DIFFERENT vault that\n"
    "      does not know this key.\n"
    "Fix: open the vault you intend to use → its Local REST API settings → copy\n"
    "BOTH the Server Port and the API key (they are a pair) and set them together:\n"
    "  OBSIDIAN_API_URL=http://127.0.0.1:<that vault's port>\n"
    "  OBSIDIAN_API_KEY=<that vault's key>"
)

_NO_SERVER_MSG = (
    "Nothing is answering at {url}. Likely causes:\n"
    "  - Obsidian is not open, or the Local REST API plugin is not enabled.\n"
    "  - The HTTP server is off: the plugin ships HTTP (27123) DISABLED and only\n"
    "    HTTPS (27124) on by default. If {url} is http://...:27123 you must enable\n"
    "    the HTTP server first.\n"
    "  - {url}'s port belongs to a different (closed) vault.\n\n"
)

_WRONG_PORT_MSG = (
    "{url} points at port 27124 over plain HTTP, but 27124 is the plugin's HTTPS\n"
    "port. Either switch this MCP to the HTTP port (default 27123, after enabling\n"
    "the HTTP server), or use https://127.0.0.1:27124 and trust the self-signed\n"
    "certificate.\n\n"
)

_HTTPS_CERT_MSG = (
    "TLS/certificate error talking to {url}. The plugin uses a self-signed\n"
    "certificate. On localhost the simplest fix is the plain HTTP endpoint: enable\n"
    "the HTTP server and set OBSIDIAN_API_URL=http://127.0.0.1:27123. (Otherwise\n"
    "trust the cert at {url}/obsidian-local-rest-api.crt.)\n\n"
)

# httpx transport errors that mean the whole endpoint is unreachable/misconfigured
# (as opposed to a per-file 404). Used both to re-raise from batch helpers and to
# classify in explain_error().
_TRANSPORT_ERRORS = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.ReadError,
    httpx.RemoteProtocolError,
)


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


# --- Links ---


def _iter_links(content: str) -> list[tuple[dict[str, Any], int, int]]:
    links: list[tuple[dict[str, Any], int, int]] = []

    for match in re.finditer(r"(!?)\[\[([^\[\]]+)\]\]", content):
        inner = match.group(2)
        target_part, alias = (inner.split("|", 1) + [""])[:2] if "|" in inner else (inner, "")
        target, heading = (target_part.split("#", 1) + [""])[:2] if "#" in target_part else (target_part, "")
        if not target:
            continue
        link: dict[str, Any] = {"target": target, "type": "wikilink"}
        if alias:
            link["alias"] = alias
        if heading:
            link["heading"] = heading
        if match.group(1):
            link["embed"] = True
        links.append((link, match.start(), match.end()))

    for match in re.finditer(r"(?<!!)\[([^\[\]]*)\]\(([^)]+)\)", content):
        href = match.group(2)
        if not href or href.startswith(("http://", "https://")):
            continue
        links.append(({"target": href, "type": "markdown"}, match.start(), match.end()))

    return sorted(links, key=lambda item: item[1])


def parse_links(content: str) -> list[dict[str, Any]]:
    """Parse internal markdown and wikilinks from content."""
    return [link for link, _, _ in _iter_links(content)]


def resolve_relative_path(href: str, source_path: str) -> str:
    """Resolve a relative markdown link path from a source file."""
    resolved = normpath(pjoin(dirname(source_path), href))
    return resolved[2:] if resolved.startswith("./") else resolved


def resolve_wikilink(target: str, source_path: str, vault_files: list[str]) -> str | None:
    """Resolve a wikilink target to a vault file path."""
    normalized_target = target.lstrip("/")
    if "." not in normalized_target.rsplit("/", 1)[-1]:
        normalized_target = f"{normalized_target}.md"

    matches = [path for path in vault_files if path == normalized_target or path.endswith(f"/{normalized_target}")]
    if not matches:
        return None
    if len(matches) == 1:
        return matches[0]

    source_segments = source_path.split("/")[:-1]

    def _score(path: str) -> tuple[int, int]:
        candidate_segments = path.split("/")[:-1]
        shared = 0
        for source_segment, candidate_segment in zip(source_segments, candidate_segments, strict=False):
            if source_segment != candidate_segment:
                break
            shared += 1
        return (-shared, len(path))

    return sorted(matches, key=_score)[0]


# --- Frontmatter validation ---

_FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)---", re.DOTALL)


def validate_frontmatter(content: str) -> str | None:
    """Return error message if frontmatter YAML is invalid, None if ok.

    Only validates when content starts with '---'. Files without
    frontmatter pass validation.
    """
    if not content.startswith("---"):
        return None
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return "Frontmatter opened with '---' but no closing '---' found."
    try:
        parsed = yaml.safe_load(match.group(1))
    except yaml.YAMLError as e:
        return f"Invalid YAML in frontmatter: {e}"
    if parsed is not None and not isinstance(parsed, dict):
        return f"Frontmatter must be a mapping (key: value), got {type(parsed).__name__}."
    return None


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
            if _is_endpoint_error(e):
                raise
            return path, {"error": f"ERROR: {e}"}

    async with _client() as c:
        results = await asyncio.gather(*[_list_one(c, p) for p in paths])
    return dict(results)


async def list_vault_files(path: str = "/") -> list[str]:
    """Recursively list all files in the vault."""
    normalized_path = path if path.endswith("/") else f"{path}/"
    listing = (await list_dirs([normalized_path])).get(normalized_path, {})
    if "error" in listing:
        return []

    files: list[str] = []
    for entry in listing.get("files", []):
        full_path = entry if normalized_path == "/" else f"{normalized_path}{entry}"
        if entry.endswith("/"):
            files.extend(await list_vault_files(full_path))
        else:
            files.append(full_path)
    return files


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
            if _is_endpoint_error(e):
                raise
            return path, f"ERROR: {e}"

    async with _client() as c:
        results = await asyncio.gather(*[_read_one(c, p) for p in paths])
    return dict(results)


async def outlinks(path: str) -> list[dict[str, Any]]:
    """Return resolved outgoing links from a file."""
    vault_files = await list_vault_files("/")
    result = await read_files([path])
    content = result[path]
    if isinstance(content, str) and content.startswith("ERROR: "):
        raise ValueError(content)
    if not isinstance(content, str):
        return []

    links = parse_links(content)
    for link in links:
        if link["type"] == "wikilink":
            resolved = resolve_wikilink(link["target"], path, vault_files)
            if resolved:
                link["target"] = resolved
        elif link["type"] == "markdown":
            link["target"] = resolve_relative_path(link["target"], path)
    return links


async def backlinks(path: str) -> list[dict[str, Any]]:
    """Find files linking to a target file."""
    target_path = path.lstrip("/")
    vault_files = await list_vault_files("/")
    markdown_files = [file for file in vault_files if file.endswith(".md") and file != target_path]
    results: list[dict[str, Any]] = []

    for start in range(0, len(markdown_files), 50):
        batch = markdown_files[start : start + 50]
        contents = await read_files(batch)
        for source_file in batch:
            content = contents[source_file]
            if not isinstance(content, str) or content.startswith("ERROR: "):
                continue
            for link, match_start, match_end in _iter_links(content):
                if link["type"] == "wikilink":
                    resolved = resolve_wikilink(link["target"], source_file, vault_files)
                else:
                    resolved = resolve_relative_path(link["target"], source_file)
                if resolved != target_path:
                    continue
                context_start = max(0, match_start - 50)
                context_end = min(len(content), match_end + 50)
                results.append(
                    {
                        "source": source_file,
                        "type": link["type"],
                        "context": content[context_start:context_end],
                    }
                )
    return results


async def broken_links(path: str = "/") -> list[dict[str, Any]]:
    """Find broken links in the vault or a directory."""
    vault_files = await list_vault_files("/")
    vault_file_set = set(vault_files)
    if path == "/":
        scan_files = vault_files
    else:
        scan_path = path.lstrip("/")
        scan_prefix = scan_path if scan_path.endswith("/") else f"{scan_path}/"
        scan_files = [file for file in vault_files if file.startswith(scan_prefix)]

    markdown_files = [file for file in scan_files if file.endswith(".md")]
    results: list[dict[str, Any]] = []

    for start in range(0, len(markdown_files), 50):
        batch = markdown_files[start : start + 50]
        contents = await read_files(batch)
        for source_file in batch:
            content = contents[source_file]
            if not isinstance(content, str) or content.startswith("ERROR: "):
                continue
            for link in parse_links(content):
                if link["type"] == "wikilink":
                    resolved = resolve_wikilink(link["target"], source_file, vault_files)
                    if resolved is None:
                        results.append(
                            {
                                "source": source_file,
                                "target": link["target"],
                                "type": link["type"],
                            }
                        )
                else:
                    resolved = resolve_relative_path(link["target"], source_file)
                    if resolved not in vault_file_set:
                        results.append(
                            {
                                "source": source_file,
                                "target": link["target"],
                                "type": link["type"],
                            }
                        )
    return results


async def write_file(filename: str, content: str) -> dict[str, Any]:
    """Create or replace a file in the vault.

    Args:
        filename: Path to the file inside the vault.
        content: Markdown content to write.
    """
    if filename.endswith(".md"):
        error = validate_frontmatter(content)
        if error:
            raise ValueError(f"Frontmatter validation failed: {error}")
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


# --- Diagnostics ---


def _is_endpoint_error(exc: BaseException) -> bool:
    """True if exc means the whole endpoint is unreachable or unauthorized.

    Such errors affect every request identically, so batch helpers re-raise them
    instead of swallowing them per-path — letting the MCP layer surface setup help.
    A per-file 404 is NOT an endpoint error.
    """
    if isinstance(exc, RuntimeError) and "OBSIDIAN_API_KEY" in str(exc):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (401, 403)
    return isinstance(exc, _TRANSPORT_ERRORS)


async def _server_reachable() -> bool:
    """Probe GET / (no auth). True if a server answers at the configured URL."""
    try:
        async with _client() as c:
            r = await c.get("/")
        return r.status_code < 500
    except Exception:
        return False


async def explain_error(exc: BaseException) -> str | None:
    """Translate a transport/config error into an actionable setup message.

    Returns an enriched, onboarding-oriented message, or None when the error is a
    normal operation error (e.g. 404 file not found) the caller should surface as-is.
    """
    url = _base_url()

    # No API key configured — probe to report whether a server is even up.
    if isinstance(exc, RuntimeError) and "OBSIDIAN_API_KEY" in str(exc):
        head = _NO_KEY_REACHABLE if await _server_reachable() else _NO_KEY_UNREACHABLE
        return head.format(url=url) + SETUP_GUIDE

    # Key rejected — port/key/vault mismatch (cannot tell which from the response).
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in (401, 403):
        return _UNAUTHED_MSG.format(url=url, code=exc.response.status_code)

    # Transport problem — distinguish wrong-protocol from no-server by URL shape.
    if isinstance(exc, _TRANSPORT_ERRORS):
        if url.startswith("https"):
            return _HTTPS_CERT_MSG.format(url=url) + SETUP_GUIDE
        if ":27124" in url:
            return _WRONG_PORT_MSG.format(url=url) + SETUP_GUIDE
        return _NO_SERVER_MSG.format(url=url) + SETUP_GUIDE

    return None
