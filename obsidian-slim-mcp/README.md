# Obsidian Slim MCP

Obsidian vault operations via Local REST API. Single-tool MCP server for Claude Desktop/Code.

- **Full vault access** — read, write, append, patch, delete, search across notes
- **Graph navigation** — outlinks, backlinks, broken link detection
- **Periodic notes** — daily/weekly/monthly/quarterly/yearly note operations
- **Multi-vault** — one MCP server instance per vault, separate port and API key
- **CLI included** — direct vault access from the terminal without Claude

## Prerequisites

- [Obsidian Local REST API](https://github.com/coddingtonbear/obsidian-local-rest-api) plugin enabled
- `OBSIDIAN_API_KEY` env var set to the plugin's API key

## Install

### As a Plugin

```bash
/plugin marketplace add vre/flow-state
/plugin install obsidian-slim-mcp@flow-state
```

### Manual

```bash
claude mcp add obsidian-slim-mcp -- uv --directory /path/to/obsidian-slim-mcp run obsidian-slim-mcp
```

Or in `settings.json` / `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "obsidian-slim-mcp": {
      "command": "uv",
      "args": ["--directory", "/path/to/obsidian-slim-mcp", "run", "obsidian-slim-mcp"],
      "env": {
        "OBSIDIAN_API_KEY": "your-api-key",
        "OBSIDIAN_API_URL": "http://127.0.0.1:27123"
      }
    }
  }
}
```

## Multiple Vaults

Each Obsidian vault runs its own REST API instance on a separate port with its own API key. Configure the port in each vault's plugin settings (Settings → Local REST API).

Register one MCP server per vault with different `OBSIDIAN_API_URL`:

```json
{
  "mcpServers": {
    "obsidian-wiki": {
      "command": "uv",
      "args": ["--directory", "/path/to/obsidian-slim-mcp", "run", "obsidian-slim-mcp"],
      "env": {
        "OBSIDIAN_API_KEY": "wiki-vault-key",
        "OBSIDIAN_API_URL": "http://127.0.0.1:27123"
      }
    },
    "obsidian-work": {
      "command": "uv",
      "args": ["--directory", "/path/to/obsidian-slim-mcp", "run", "obsidian-slim-mcp"],
      "env": {
        "OBSIDIAN_API_KEY": "work-vault-key",
        "OBSIDIAN_API_URL": "http://127.0.0.1:27125"
      }
    }
  }
}
```

CLI supports the same via flags or env vars:

```bash
obsidian-cli --vault-url http://127.0.0.1:27125 --api-key work-key list
```

## Actions

**Vault**
- `list` — list vault root or a directory
- `read` — read a file (markdown or JSON with frontmatter/tags)
- `write` — create or replace a file
- `append` — append content to a file
- `patch` — partial update targeting a heading, block, or frontmatter key
- `delete` — delete a file

**Search**
- `search` — simple text search across the vault
- `search_advanced` — Dataview DQL or JsonLogic search
- `tags` — list all tags with occurrence counts

**Graph**
- `outlinks` — parse outgoing wikilinks and markdown links from a file
- `backlinks` — find all files that link to a given file
- `broken_links` — detect links pointing to non-existent files (vault-wide or directory-scoped)

**Obsidian UI**
- `commands` — list available Obsidian commands
- `command_run` — execute an Obsidian command by ID
- `open` — open a file in the Obsidian UI
- `active_read` — read the currently active file
- `active_write` — replace the active file's content

**Periodic Notes**
- `periodic_read` — read a periodic note (daily/weekly/monthly/quarterly/yearly)
- `periodic_write` — replace a periodic note
- `periodic_append` — append to a periodic note

**Help**
- `help` — built-in documentation; use `payload` for topic-specific help

## Usage

```
{action: "help"}                                           # overview
{action: "list"}                                           # vault root
{action: "read", payload: "index.md"}                      # read markdown
{action: "read", payload: "index.md|json"}                 # read with metadata
{action: "search", payload: "meeting notes"}               # text search
{action: "outlinks", payload: "index.md"}                  # outgoing links
{action: "backlinks", payload: "topics/zettelkasten.md"}   # incoming links
{action: "broken_links"}                                   # broken links vault-wide
{action: "help", payload: "patch"}                         # help on patch action
```

## CLI

```bash
uv run obsidian-cli list
uv run obsidian-cli read index.md
uv run obsidian-cli search "meeting notes"
uv run obsidian-cli --help
```

## Development

```bash
uv sync
uv run obsidian-slim-mcp          # start MCP server
uv run obsidian-cli help     # CLI help
uv run pytest tests/ -v      # run tests
```

## License

MIT, See [LICENSE](LICENSE) for more information.
