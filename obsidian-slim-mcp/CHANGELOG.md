# Changelog

## [0.2.0] - 2026-05-04

### Added
- `outlinks` action — parse outgoing wikilinks and markdown links from a file
- `backlinks` action — find all vault files that link to a given file
- `broken_links` action — detect links pointing to non-existent files, scoped to vault or directory
- PyYAML dependency for frontmatter parsing and validation

## [0.1.0] - 2026-04-25

### Added
- Single-tool MCP server for Obsidian vault operations via Local REST API plugin
- `list` — list vault root or a directory
- `read` — read markdown or JSON with frontmatter/tags
- `write` — create or replace a file
- `append` — append content to a file
- `patch` — partial update targeting a heading, block, or frontmatter key
- `delete` — delete a file
- `search` — simple text search across the vault
- `search_advanced` — Dataview DQL or JsonLogic search
- `tags` — list all tags with occurrence counts
- `commands` / `command_run` — list and execute Obsidian commands
- `open` — open a file in the Obsidian UI
- `active_read` / `active_write` — read or replace the currently active file
- `periodic_read` / `periodic_write` / `periodic_append` — periodic note operations (daily/weekly/monthly/quarterly/yearly)
- `help` — built-in documentation with per-action topics
- CLI (`obsidian-cli`) for direct vault access from the terminal
- Multi-vault support via `OBSIDIAN_API_URL` environment variable
