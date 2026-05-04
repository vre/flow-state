# Frame: Graph & Link Support for obsidian-slim-mcp

## Problem

Obsidian's value is in linked notes. The MCP server can read/write files but has no awareness of the link graph. Cannot answer "what links to this file?", "are there broken links?", or safely rename a file without breaking references.

## Goal

Add graph-aware actions to obsidian-slim-mcp: backlinks, outlinks, broken_links, rename.

## Cut 1: Read-only graph actions (this frame)

### outlinks

Parse `[[wikilinks]]` and `[text](path.md)` from a file's content. Return list of link targets.

- payload: file path
- Parse patterns: `[[target]]`, `[[target|alias]]`, `[[target#heading]]`, `[text](relative/path.md)`
- Ignore external URLs (http/https)
- Return: `[{"target": "notes/foo.md", "type": "wikilink", "alias": "...", "heading": "..."}]`

### backlinks

Find all files that link to a given file.

- payload: file path
- Strategy: list entire vault recursively, read each .md file, parse outlinks, filter for target
- Return: `[{"source": "projects/bar.md", "type": "wikilink", "context": "...surrounding text..."}]`
- Performance: this is O(n) over vault size. Fine for vaults < 5000 files. Add note in help.

### broken_links

Find links pointing to non-existent files across the vault.

- payload: optional directory path (default: entire vault)
- Strategy: list vault → read each .md → parse outlinks → check existence via vault listing
- Return: `[{"source": "foo.md", "target": "nonexistent.md", "type": "wikilink"}]`
- Skip external URLs

## Cut 2: rename (future, not this frame)

Depends on backlinks working. Will be separate frame.

## Implementation

### obsidian_client.py

Add link parsing functions (pure, no HTTP):

```python
def parse_links(content: str) -> list[dict]:
    """Parse wikilinks and markdown links from content."""

def resolve_wikilink(target: str, source_path: str, vault_files: list[str]) -> str | None:
    """Resolve a wikilink target to a vault file path.
    Obsidian resolves shortest unique match."""
```

Add graph functions (HTTP + parsing):

```python
async def outlinks(path: str) -> list[dict]:
    """Parse outgoing links from a file."""

async def backlinks(path: str) -> list[dict]:
    """Find all files linking to the given file."""

async def broken_links(path: str = "/") -> list[dict]:
    """Find broken links in the vault or directory."""
```

### obsidian_slim_mcp.py

Add actions: `outlinks`, `backlinks`, `broken_links` to:
- Action validator set
- Action handlers
- Help topics

### Tests

- `parse_links`: unit tests with various link formats (wikilink, alias, heading, markdown, mixed, external URLs filtered)
- `resolve_wikilink`: shortest match, exact match, no match
- `outlinks`: mock HTTP, verify parsed results
- `backlinks`: mock HTTP with multi-file vault, verify reverse lookup
- `broken_links`: mock HTTP, verify detection of missing targets

## Acceptance criteria

- [ ] AC1: `{action: "outlinks", payload: "index.md"}` returns list of links with type/target/alias
- [ ] AC2: `{action: "backlinks", payload: "topics/knowledge-management.md"}` finds files linking to it
- [ ] AC3: `{action: "broken_links"}` scans vault and reports links to non-existent files
- [ ] AC4: `[[wikilink]]`, `[[wikilink|alias]]`, `[[wikilink#heading]]`, `[text](path.md)` all parsed
- [ ] AC5: External URLs (http/https) excluded from results
- [ ] AC6: Unit tests pass for link parsing, resolution, and all three actions
- [ ] AC7: Help topics document all three new actions

## Notes

- Wikilink resolution in Obsidian uses "shortest unique path" — `[[foo]]` matches `notes/foo.md` if unique. Implement this.
- Vault file listing is already available via `list_dirs`. Use recursive listing for backlinks/broken_links.
- Keep link parsing as pure functions — testable without HTTP mocks.
