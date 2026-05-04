# Plan: Graph Link Support — Cut 1 (Read-only)

**Frame**: `docs/obsidian-slim-mcp/plans/2026-04-25-frame-graph-links.md`
**Branch**: `obsidian-graph`
**Repo path**: `obsidian-slim-mcp/`

## Intent

Add link-graph awareness to obsidian-slim-mcp: parse links from files, find backlinks, detect broken links. Read-only operations only — rename is Cut 2.

## Goal

Three new MCP actions (`outlinks`, `backlinks`, `broken_links`) backed by pure link-parsing functions and a recursive vault listing helper.

## Constraints

- Pure functions for link parsing — no HTTP, fully testable without mocks.
- Async functions for graph operations — use existing `list_dirs` and `read_files`.
- Wikilink resolution follows Obsidian's proximity-based algorithm (closest to source file, then shortest path).
- External URLs (http/https) excluded from all results.
- Follow existing code patterns exactly (httpx client, action dispatcher, test structure).

## Architecture

### New pure functions in `obsidian_client.py`

```python
import re
from posixpath import normpath, dirname, join as pjoin

def parse_links(content: str) -> list[dict]:
def resolve_wikilink(target: str, source_path: str, vault_files: list[str]) -> str | None:
def resolve_relative_path(href: str, source_path: str) -> str:
```

### New async functions in `obsidian_client.py`

```python
async def list_vault_files(path: str = "/") -> list[str]:
async def outlinks(path: str) -> list[dict]:
async def backlinks(path: str) -> list[dict]:
async def broken_links(path: str = "/") -> list[dict]:
```

### Changes to `obsidian_slim_mcp.py`

- Add `outlinks`, `backlinks`, `broken_links` to validator set
- Update `Field(description=...)` string on `action` to include new actions
- Add action handlers in `use_obsidian()`
- Add help topics for all three new actions
- Update `HELP_TOPICS["overview"]` to list the new actions

## Detailed Specifications

### `parse_links(content: str) -> list[dict]`

Pure function. Parses all internal links from markdown content.

**Patterns to match:**
1. `[[target]]` → `{"target": "target", "type": "wikilink"}`
2. `[[target|alias]]` → `{"target": "target", "type": "wikilink", "alias": "alias"}`
3. `[[target#heading]]` → `{"target": "target", "type": "wikilink", "heading": "heading"}`
4. `[[target#heading|alias]]` → `{"target": "target", "type": "wikilink", "heading": "heading", "alias": "alias"}`
5. `![[embed.png]]` → `{"target": "embed.png", "type": "wikilink", "embed": true}` (embeds with `!` prefix)
6. `[text](relative/path.md)` → `{"target": "relative/path.md", "type": "markdown"}`

**Exclusions:**
- `[text](http://...)` and `[text](https://...)` — skip entirely
- `![alt](image.png)` — markdown images excluded (only wikilink embeds included)
- `[[#heading]]` — same-file heading references excluded (empty target after `#` split). Out of scope for Cut 1.
- Empty targets — skip

**Regex approach:**
- Wikilinks: `!?\[\[([^\[\]]+)\]\]` — match optional `!` prefix, capture inner content. Split inner on `|` for alias (take first part as target+heading, second as alias). Split target part on `#` for heading.
  - If `!` prefix matched → add `"embed": true`
- Markdown links: `(?<!!)\[([^\[\]]*)\]\(([^)]+)\)` — negative lookbehind for `!` to exclude images. Capture text and href. Filter out `http://` and `https://` prefixed hrefs.

**Return:** List of dicts. Keys present only when they have values (no `"alias": null`, no `"embed": false`).

**Simplification:** Links inside code blocks/fences are NOT filtered. Acceptable for Cut 1.

### `resolve_wikilink(target: str, source_path: str, vault_files: list[str]) -> str | None`

Pure function. Resolves a wikilink target to a full vault path using Obsidian's resolution algorithm.

**Algorithm:**
1. Normalize: strip leading `/` from target
2. If target has no `.md` extension, append `.md` for matching
3. Find all vault files where the path ends with `/target` or equals `target` exactly
4. If no matches → return `None`
5. If exactly one match → return it
6. If multiple matches → tiebreaker by proximity to source file:
   a. Count shared path prefix segments between each candidate and `source_path`
   b. Return candidate with most shared segments
   c. If still tied → return shortest path

**Examples:**
- `resolve_wikilink("foo", "notes/bar.md", ["notes/foo.md", "archive/foo.md"])` → `"notes/foo.md"` (same directory as source)
- `resolve_wikilink("foo", "other/bar.md", ["notes/foo.md", "archive/deep/foo.md"])` → `"notes/foo.md"` (shorter path, no proximity winner)
- `resolve_wikilink("notes/foo", "x.md", ["notes/foo.md", "other/foo.md"])` → `"notes/foo.md"` (exact suffix match)
- `resolve_wikilink("bar", "x.md", ["notes/foo.md"])` → `None`
- `resolve_wikilink("foo.md", "x.md", ["foo.md"])` → `"foo.md"` (already has extension)

### `resolve_relative_path(href: str, source_path: str) -> str`

Pure function. Resolves a relative markdown link path against the source file's directory.

**Algorithm:**
1. Get source directory: `posixpath.dirname(source_path)` (e.g. `"notes/sub/bar.md"` → `"notes/sub"`)
2. Join: `posixpath.join(source_dir, href)` (e.g. `"notes/sub" + "../foo.md"` → `"notes/sub/../foo.md"`)
3. Normalize: `posixpath.normpath(result)` (e.g. `"notes/sub/../foo.md"` → `"notes/foo.md"`)
4. Strip leading `./` if present

**Examples:**
- `resolve_relative_path("../foo.md", "notes/sub/bar.md")` → `"notes/foo.md"`
- `resolve_relative_path("sibling.md", "notes/bar.md")` → `"notes/sibling.md"`
- `resolve_relative_path("./local.md", "bar.md")` → `"local.md"`

### `list_vault_files(path: str = "/") -> list[str]`

Async function. Recursively lists all files in the vault (all types, not just `.md`).

**Algorithm:**
1. Normalize `path`: ensure it ends with `/` (e.g. `"notes"` → `"notes/"`)
2. Call `list_dirs([path])` to get entries from `{"files": [...]}` response
3. Separate files from directories (directories end with `/`)
4. Build full paths:
   - If path is `"/"` → use filename as-is (e.g. `"index.md"`)
   - Else → join `path + filename` (e.g. `"notes/" + "foo.md"` → `"notes/foo.md"`)
5. For each subdirectory, build full subdir path the same way, then recursively call `list_vault_files(full_subdir_path)`
6. Return flat list of all file paths

**Return:** `["index.md", "notes/foo.md", "projects/bar.md", "attachments/image.png", ...]`

**Edge cases:**
- If `list_dirs` returns an error for a subdirectory, skip it silently (don't crash the whole listing).
- Returns ALL file types (needed by `resolve_wikilink` for non-`.md` embeds like images).

### `outlinks(path: str) -> list[dict]`

Async function.

1. List all vault files via `list_vault_files("/")`
2. Read the file via `read_files([path])`
3. If read fails (content starts with `"ERROR: "`), raise `ValueError` with the error message
4. Parse links via `parse_links(content)`
5. For each wikilink: resolve target via `resolve_wikilink(link_target, path, vault_files)` and replace `target` with resolved path (keep raw target if resolution fails)
6. For each markdown link: resolve via `resolve_relative_path(link_target, path)`
7. Return the resolved links list

### `backlinks(path: str) -> list[dict]`

Async function.

1. Normalize `path`: strip leading `/`
2. List all vault files via `list_vault_files("/")`
3. Filter to `.md` files only, exclude `path` itself
4. Read `.md` files in batches of 50 via `read_files(batch)` to avoid overwhelming the API
5. For each file with successful read: parse outlinks via `parse_links(content)`
6. For each parsed link, check if it points to `path`:
   - Wikilinks: resolve via `resolve_wikilink(link_target, source_file, vault_files)`, compare resolved path to `path`
   - Markdown links: resolve via `resolve_relative_path(link_target, source_file)`, compare to `path`
7. If match: extract context and add to results
8. Context extraction:
   - Search source content for the full link syntax (e.g. `[[target]]` or `[text](href)`)
   - Take 50 chars before match start + the match itself + 50 chars after match end
   - Clamp to string boundaries (0, len)
   - One result entry per link occurrence (same file can appear multiple times)

**Return:** `[{"source": "projects/bar.md", "type": "wikilink", "context": "...text around link..."}]`

**Path normalization for comparison:** strip leading `/`, case-sensitive.

### `broken_links(path: str = "/") -> list[dict]`

Async function.

1. List ALL vault files via `list_vault_files("/")` — full vault needed for wikilink resolution
2. Build scan set: if `path != "/"`, filter to files under `path`; else use all files
3. Filter scan set to `.md` files only
4. Read `.md` files in batches of 50 via `read_files(batch)`
5. For each file with successful read: parse outlinks via `parse_links(content)`
6. For each link, try to resolve:
   - Wikilinks: `resolve_wikilink(link_target, source_file, all_vault_files)` — if `None`, it's broken
   - Markdown links: `resolve_relative_path(link_target, source_file)` — check if result is in `all_vault_files` set; if not, it's broken
7. Collect broken links

**Return:** `[{"source": "foo.md", "target": "nonexistent.md", "type": "wikilink"}]`

**Out of scope:** Heading fragment validation (`[[foo#heading]]` only checks that `foo.md` exists, not that `#heading` exists within it).

### MCP action handlers

**outlinks handler:**
- Payload: file path (string, required)
- Call `api.outlinks(payload)`, return JSON
- On missing payload, return error message

**backlinks handler:**
- Payload: file path (string, required)
- Call `api.backlinks(payload)`, return JSON
- On missing payload, return error message

**broken_links handler:**
- Payload: optional directory path (string, default `/`)
- Call `api.broken_links(payload or "/")`, return JSON

### Help topics

Add individual help topics + update overview:

```
outlinks: "# outlinks — Parse outgoing links\n\n## Payload\nFile path.\n\n## Example\n{action: \"outlinks\", payload: \"index.md\"}\n\nReturns list of {target, type, alias?, heading?, embed?}."

backlinks: "# backlinks — Find incoming links\n\n## Payload\nFile path.\n\n## Example\n{action: \"backlinks\", payload: \"topics/knowledge-management.md\"}\n\nReturns list of {source, type, context}.\nNote: scans entire vault (O(n)). Fine for vaults < 5000 files."

broken_links: "# broken_links — Find broken links\n\n## Payload\nOptional directory path (default: entire vault).\n\n## Examples\n{action: \"broken_links\"} — scan entire vault\n{action: \"broken_links\", payload: \"projects/\"} — scan one directory\n\nReturns list of {source, target, type}."
```

Update `HELP_TOPICS["overview"]` to add:
```
- **outlinks** — Parse outgoing links from a file
- **backlinks** — Find all files linking to a given file
- **broken_links** — Find broken links in vault or directory
```

## Tasks

- [x] T1: Add `parse_links()` and `resolve_relative_path()` to `obsidian_client.py`
- [x] T2: Add `resolve_wikilink()` to `obsidian_client.py`
- [x] T3: Add `list_vault_files()` to `obsidian_client.py`
- [x] T4: Add `outlinks()` to `obsidian_client.py`
- [x] T5: Add `backlinks()` to `obsidian_client.py`
- [x] T6: Add `broken_links()` to `obsidian_client.py`
- [x] T7: Add actions, handlers, help topics, update overview and Field description in `obsidian_slim_mcp.py`
- [x] T8: Add unit tests for `parse_links` (wikilink, alias, heading, `#heading|alias` combined, embed `![[...]]`, markdown link, external URL filtering, markdown image exclusion, mixed content, empty)
- [x] T9: Add unit tests for `resolve_wikilink` (unique match, proximity tiebreaker, shortest path fallback, exact suffix, no match, with extension)
- [x] T10: Add unit tests for `resolve_relative_path` (parent dir, sibling, current dir, root-level)
- [x] T11: Add unit tests for `list_vault_files` (mock `list_dirs`, recursive, error in subdir)
- [x] T12: Add tests for `outlinks` (mock HTTP, verify resolution), `backlinks` (mock multi-file vault, verify reverse lookup + context), `broken_links` (mock HTTP, verify detection)
- [x] T13: Add MCP action tests for all three new actions (routing, payloads, error cases)
- [x] T14: Run full test suite, fix any failures — 137 passed, 0 failures

**Commit strategy:** One commit per logical unit (T1-T2 together as pure functions, T3 alone, T4-T6 together as graph functions, T7 alone, T8-T13 together as tests, T14 as fixes if needed).

## Acceptance Criteria

- [x] AC1: `{action: "outlinks", payload: "index.md"}` returns list of links with type/target/alias
- [x] AC2: `{action: "backlinks", payload: "topics/knowledge-management.md"}` finds files linking to it
- [x] AC3: `{action: "broken_links"}` scans vault and reports links to non-existent files
- [x] AC4: `[[wikilink]]`, `[[wikilink|alias]]`, `[[wikilink#heading]]`, `[text](path.md)` all parsed
- [x] AC5: External URLs (http/https) excluded from results
- [x] AC6: Unit tests pass for link parsing, resolution, and all three actions
- [x] AC7: Help topics document all three new actions

## Testing Strategy

**Pure function tests (no mocks):**
- `parse_links`: all link formats including `[[target#heading|alias]]` combined, `![[embed]]`, markdown image exclusion
- `resolve_wikilink`: proximity-based tiebreaker, fallback to shortest, edge cases
- `resolve_relative_path`: `..`, `.`, root-level sources

**Mocked HTTP tests:**
- `list_vault_files`: mock `list_dirs` to return nested directory structure, test subdir error handling
- `outlinks`: mock `list_vault_files` + `read_files`, verify resolved targets
- `backlinks`: mock `list_vault_files` + `read_files` with multi-file vault, verify reverse lookup and context extraction
- `broken_links`: mock `list_vault_files` + `read_files`, verify detection of missing targets

**MCP action tests:**
- Mock client functions (`api.outlinks`, `api.backlinks`, `api.broken_links`), verify action routing, JSON output, error handling

## Files Changed

- `obsidian-slim-mcp/obsidian_client.py` — add `re` and `posixpath` imports, 7 functions (~100 lines)
- `obsidian-slim-mcp/obsidian_slim_mcp.py` — add 3 actions + handlers + help + update overview/description (~80 lines)
- `obsidian-slim-mcp/tests/test_client.py` — add test classes (~200 lines)
- `obsidian-slim-mcp/tests/test_mcp.py` — add test classes (~80 lines)
