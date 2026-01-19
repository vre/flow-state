# Claude Code Plugin Execution Research

**Date:** 2026-01-17
**Topic:** How Python MCP servers are executed in Claude Code plugins

## Executive Summary

Claude Code uses **`uv`** (or **`uvx`**) as the recommended way to execute Python MCP servers. Claude Code does NOT bundle `uv` - users must install it separately. The `uv` command must be accessible in the system PATH or specified with an absolute path in the configuration.

## Key Findings

### 1. Claude Code Does NOT Bundle `uv`

- Claude Code calls `uv` as an **external process**
- Users must install `uv` separately (e.g., `curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Common error: `spawn uv ENOENT` indicates `uv` is not found in PATH
- **Solution**: Either add `uv` to system PATH via symlink (`sudo ln -s ~/.local/bin/uv /usr/local/bin/uv`) or use absolute paths in config

**Source:** [Mac MCP Claude Fix for spawn uv ENOENT error](https://gist.github.com/gregelin/b90edaef851f86252c88ecc066c93719)

### 2. Recommended Commands

| Scenario | Command | Notes |
|----------|---------|-------|
| Python (local project) | `uv` | For local development with dependencies |
| Python (published package) | `uvx` | For running packages from PyPI or git repos |
| Node.js | `npx` | Equivalent to uvx for JavaScript |
| Docker | `docker` | Alternative for containerized servers |
| Direct Python | `python` | Requires manual venv/dependency management |

**Pattern:** `uvx` is to Python what `npx` is to Node.js - a way to run tools in temporary environments.

### 3. Official Plugin Examples

#### From `anthropics/claude-plugins-official` repository:

**Serena plugin** (`external_plugins/serena/.mcp.json`):
```json
{
  "serena": {
    "command": "uvx",
    "args": ["--from", "git+https://github.com/oraios/serena", "serena", "start-mcp-server"]
  }
}
```

**GitHub plugin** (`external_plugins/github/.mcp.json`) - HTTP-based (no command):
```json
{
  "github": {
    "type": "http",
    "url": "https://api.githubcopilot.com/mcp/",
    "headers": {
      "Authorization": "Bearer ${GITHUB_PERSONAL_ACCESS_TOKEN}"
    }
  }
}
```

**Source:** [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official)

### 4. Configuration Patterns

#### Pattern A: Local Python project with `uv`
```json
{
  "mcpServers": {
    "my-server": {
      "command": "uv",
      "args": ["--directory", "/path/to/project", "run", "server.py"]
    }
  }
}
```

#### Pattern B: Published package with `uvx`
```json
{
  "mcpServers": {
    "my-server": {
      "command": "uvx",
      "args": ["package-name@latest"]
    }
  }
}
```

#### Pattern C: Git-based package with `uvx`
```json
{
  "mcpServers": {
    "my-server": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/org/repo", "entrypoint", "args"]
    }
  }
}
```

#### Pattern D: FastMCP with dependencies
```json
{
  "mcpServers": {
    "my-server": {
      "command": "uv",
      "args": [
        "run",
        "--python", "3.11",
        "--project", "/path/to/project",
        "--with", "fastmcp",
        "--with-requirements", "requirements.txt",
        "fastmcp", "run", "server.py"
      ]
    }
  }
}
```

#### Pattern E: Direct Python (not recommended)
```json
{
  "mcpServers": {
    "my-server": {
      "command": "/path/to/venv/bin/python",
      "args": ["/path/to/server.py"]
    }
  }
}
```

### 5. Plugin Variable Expansion

Claude Code supports variable expansion in `.mcp.json`:
- `${CLAUDE_PLUGIN_ROOT}` - Root directory of the plugin
- `${ENV_VAR_NAME}` - Environment variables

**Example from this project:**
```json
{
  "imap-stream": {
    "command": "uv",
    "args": ["--directory", "${CLAUDE_PLUGIN_ROOT}", "run", "imap-stream"]
  }
}
```

### 6. How Dependencies Are Handled

| Approach | Dependency Management |
|----------|----------------------|
| `uv run --directory` | Uses project's `pyproject.toml` / `uv.lock` |
| `uv run --with pkg` | Installs specified packages temporarily |
| `uv run --with-requirements` | Reads from requirements file |
| `uvx package@version` | Uses published package dependencies |
| `uvx --from git+url` | Clones and installs from git |

### 7. Windows Considerations

On Windows (not WSL), `npx` requires the `cmd /c` wrapper:
```json
{
  "mcpServers": {
    "my-server": {
      "command": "cmd",
      "args": ["/c", "npx", "-y", "@some/package"]
    }
  }
}
```

For `uv` on Windows, use `uv tool run`:
```json
{
  "mcpServers": {
    "my-server": {
      "command": "uv",
      "args": ["tool", "run", "--from", "package@latest", "entrypoint.exe"]
    }
  }
}
```

### 8. Configuration Scopes

| Scope | Location | Visibility |
|-------|----------|------------|
| Local | In-memory / `~/.claude.json` | Only current user, current project |
| Project | `.mcp.json` in project root | Shared via version control |
| User | `~/.claude.json` | All projects for current user |

**Priority:** Local > Project > User

### 9. Model Context Protocol Python SDK Recommendations

The [official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) recommends:

1. **Use `uv` to manage Python projects** (minimum version 0.9.5)
2. **Install with:** `uv add "mcp[cli]"`
3. **Run with:** `uv run mcp`
4. **Install to Claude Desktop:** `uv run mcp install server.py`

**Source:** [modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk)

## Recommendations for This Project

### Current Configuration (Good)
```json
{
  "imap-stream": {
    "command": "uv",
    "args": ["--directory", "${CLAUDE_PLUGIN_ROOT}", "run", "imap-stream"]
  }
}
```

This follows best practices:
- Uses `uv` (the recommended tool)
- Uses `${CLAUDE_PLUGIN_ROOT}` for portability
- References an entry point defined in `pyproject.toml`

### Considerations

1. **Documentation should note**: Users need `uv` installed globally
2. **Alternative for users without `uv`**: Could provide `python -m streammail` fallback
3. **For PyPI publication**: Consider `uvx` pattern once package is published

### Troubleshooting Tips to Document

1. If `spawn uv ENOENT`: Install uv or use absolute path
2. If PATH issues on macOS: Create symlink to `/usr/local/bin/uv`
3. Use `which uv` to find absolute path if needed

## Sources

- [Claude Code MCP Documentation](https://code.claude.com/docs/en/mcp)
- [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official)
- [anthropics/claude-code plugins README](https://github.com/anthropics/claude-code/blob/main/plugins/README.md)
- [FastMCP Claude Code Integration](https://gofastmcp.com/integrations/claude-code)
- [MCP JSON Configuration](https://gofastmcp.com/integrations/mcp-json-configuration)
- [modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk)
- [Mac MCP Claude Fix for spawn uv ENOENT error](https://gist.github.com/gregelin/b90edaef851f86252c88ecc066c93719)
- [AWS Labs MCP Server Examples](https://github.com/awslabs/mcp/blob/main/src/core-mcp-server/README.md)
- [Beginner's Guide to Building MCP Server with uv](https://mahendranp.medium.com/beginners-guide-to-building-and-testing-your-first-mcp-server-with-uv-and-claude-3bfc6198212a)
