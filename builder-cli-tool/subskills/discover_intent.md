---
name: discover_intent
description: "Brainstorming-style discovery for CLI tool requirements."
---

# Discover Intent

Open-ended conversation to surface what the CLI tool should do.

## Key Questions

- What problem does this solve? Who uses it?
- What are the 3-5 core operations? (list, get, create, delete, search, help...)
- What data does it work with? (files, REST API, local DB, other CLIs)
- Does it need authentication? (env vars, keyring, API keys)
- Does it need MCP mode? (defer if unclear — can add later)

## Domain Categories (emerge from answers)

- **API client**: Wraps REST/GraphQL API → needs auth, network error handling
- **Data processor**: Transforms files → needs path validation, streaming
- **CLI wrapper**: Wraps git/gh/docker → needs command whitelisting
- **System utility**: Manages local resources → needs permission handling

## Output

JSON for generate_cli.py:
```json
{"name": "mytool", "operations": ["list", "get", "create", "delete", "help"]}
```
