# obsidian-slim-mcp

Obsidian vault operations via Local REST API. Single-tool MCP server for Claude Desktop/Code.

## Prerequisites

- [Obsidian Local REST API](https://github.com/coddingtonbear/obsidian-local-rest-api) plugin enabled
- `OBSIDIAN_API_KEY` env var set to the plugin's API key

## Install

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

## Multiple vaults

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

- `list` — List vault root or a directory
- `read` — Read a file (markdown or JSON with frontmatter/tags)
- `write` — Create or replace a file
- `append` — Append content to a file
- `patch` — Partial update targeting a heading, block, or frontmatter
- `delete` — Delete a file
- `search` — Simple text search across the vault
- `search_advanced` — Dataview DQL or JsonLogic search
- `tags` — List all tags with occurrence counts
- `commands` — List available Obsidian commands
- `command_run` — Execute an Obsidian command by ID
- `open` — Open a file in the Obsidian UI
- `active_read` — Read the currently active file
- `active_write` — Replace the active file's content
- `periodic_read` — Read a periodic note (daily/weekly/monthly/quarterly/yearly)
- `periodic_write` — Replace a periodic note
- `periodic_append` — Append to a periodic note
- `help` — Show documentation (use `payload` for topic-specific help)

## Usage

```
{action: "help"}                                  # overview
{action: "list"}                                  # vault root
{action: "read", payload: "index.md"}             # read markdown
{action: "read", payload: "index.md|json"}        # read with metadata
{action: "search", payload: "meeting notes"}      # search
{action: "help", payload: "patch"}                # help on patch action
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
