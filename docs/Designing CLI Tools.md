# Designing CLI Tools: Good Practices (2026)

> **Deep reference.** This document explains the *why* behind CLI tool design decisions with full rationale and references. For the condensed instruction set, see the "Writing CLI Scripts" section in `CLAUDE.md`.

This document outlines principles for building command-line tools optimized for both human users and LLM agents.

---

# Part I: The Strategy (Why)

CLI tools exist in a unique position: they serve humans at terminals, scripts in pipelines, and increasingly, AI agents orchestrating complex workflows.

## 1. Dual Audience Design

A well-designed CLI serves two masters simultaneously:

| Aspect | Human User | LLM Agent |
| :--- | :--- | :--- |
| **Output** | Readable, formatted | Parseable, structured |
| **Errors** | Helpful message | Actionable suggestion |
| **Discovery** | `--help`, man pages | Self-documenting, predictable |
| **State** | Interactive session | Stateless by default |

**Goal:** Design for scripting first—humans benefit from scriptable tools, but scripts don't benefit from human-only features.

## 2. LLMs Know Unix Conventions

LLMs are trained extensively on Unix/GNU/Linux documentation, man pages, and shell scripts. This is a context economy advantage:

- **Standard flags are free.** `-v` for verbose, `-q` for quiet, `-f` for force, `-o` for output—LLMs infer these without reading `--help`.
- **Standard verbs are free.** `list`, `get`, `create`, `delete`, `show`, `describe`—familiar from kubectl, git, aws-cli.
- **Standard patterns are free.** `command [options] <resource> [id]`—LLMs predict argument order.

**Implication:** Following conventions reduces discovery tokens to near zero. Inventing novel flag names (`--silentmode` instead of `-q`) forces the LLM to read documentation.

```bash
# LLM can guess these without --help
myctl list users -o json
myctl get user 123 --verbose
myctl delete user 123 --force

# LLM must read docs for these
myctl users enumerate --output-format=jsonified
myctl user fetch --identifier=123 --chattiness=high
```

## 3. Context Economy Applies

LLM agents consume CLI output as context tokens. Same principles as MCP:

- **Verbose output wastes tokens.** Default to minimal; offer `--verbose` for humans.
- **Structured output enables parsing.** JSON/YAML beats prose for programmatic use.
- **Predictable format enables automation.** Consistent output structure across commands.

**Pattern:** `command --format json` for agents, pretty-print for humans (detect TTY).

## 4. Scriptability Over Interactivity

Interactive prompts break automation. Design for non-interactive use:

- **All inputs as arguments or stdin.** No required interactive prompts.
- **Confirmations via flags.** `--yes` or `--force` for destructive actions.
- **Progress to stderr.** Keep stdout clean for piping.
- **Logs to stderr. Always.** stdout is for data output only—never diagnostics.

```bash
# Bad: requires human
myctl delete resource
> Are you sure? [y/N]

# Good: scriptable
myctl delete resource --yes
```

---

# Part II: The Architecture (What)

## 5. Output Design

### 5.1 Layered Verbosity

Provide multiple output levels:

| Flag | Output | Use Case |
| :--- | :--- | :--- |
| `--quiet` / `-q` | Exit code only | Scripts checking success |
| (default) | Essential info | Normal operation |
| `--verbose` / `-v` | Detailed progress | Debugging |
| `--debug` | Everything | Development |

### 5.2 Structured Output

Support machine-readable formats:

```bash
myctl list --format json    # For scripts/agents
myctl list --format yaml    # For config files
myctl list --format table   # For humans (default if TTY)
myctl list --format csv     # For spreadsheets
```

**Auto-detection:** If stdout is a TTY, default to human format. If piped, default to JSON.

### 5.3 Consistent Schema

Every command's JSON output should follow predictable structure:

```json
{
  "success": true,
  "data": { ... },
  "metadata": { "count": 10, "truncated": false }
}
```

Or on error:
```json
{
  "success": false,
  "error": { "code": "NOT_FOUND", "message": "Resource 'x' not found" },
  "suggestion": "Did you mean 'xy'? Run: myctl list"
}
```

## 6. Error Design

### 6.1 Fail Helpfully

Same principle as MCP (see *Designing MCP Servers.md-§2)—guide toward valid input:

```bash
# Bad
$ myctl get user
Error: missing required argument

# Good
$ myctl get user
Error: missing required argument <user-id>

Usage: myctl get user <user-id> [--format json|yaml|table]

Try: myctl list users    # to see available user IDs
```

### 6.2 Exit Codes

Use meaningful exit codes for scripting:

| Code | Meaning |
| :--- | :--- |
| 0 | Success |
| 1 | General error |
| 2 | Usage/argument error |
| 3 | Resource not found |
| 4 | Permission denied |
| 5 | Connection/network error |

Document these in `--help` output.

## 7. Session and State

### 7.1 The Stateless Challenge

Unlike MCP servers that maintain connections, CLI invocations are isolated. Each call starts fresh.

**Implications:**
- No built-in session memory
- Connection overhead on every call
- Authentication must be re-established or cached

### 7.2 State Strategies

**Option A: Stateless (Recommended)**
Pass all context per invocation. Simple, predictable, parallelizable.

```bash
myctl query --token "$TOKEN" --context "$CONTEXT" "SELECT -FROM users"
```

**Option B: State File**
Store session in file, pass pointer:

```bash
myctl init --session /tmp/myctl-session.json
myctl query --session /tmp/myctl-session.json "SELECT -FROM users"
```

**Option C: Daemon Mode**
Long-running background process maintains state:

```bash
myctl daemon start                    # Start background process
myctl --socket /tmp/myctl.sock query  # Fast IPC, session maintained
myctl daemon stop
```

**When daemon is essential:**
- Underlying connection has high setup cost (auth dialogs, handshakes, OAuth flows)
- Connection must stay alive across many short-lived commands
- Protocol requires persistent session (WebSocket, authenticated TCP)

**Daemon design principles:**
- **Protocol:** JSON line in → JSON line out → disconnect. netcat-compatible: `echo '{"cmd":"list"}' | nc -U /tmp/myctl.sock`
- **Socket:** `/tmp/<tool>-<uid>.sock` with `0600` permissions
- **CLI wrapper:** `myctl send <cmd>` translates argparse → JSON → socket → stdout
- **Reconnect:** detect connection loss → re-establish → clear stale caches → retry original command
- **Status:** `myctl send status` returns connection state, session count, PID

```bash
# Three equivalent ways to use a daemon:
echo '{"cmd":"list"}' | nc -U /tmp/myctl-501.sock     # netcat
myctl send list                                        # CLI wrapper
python3: asyncio.open_unix_connection(sock_path)       # scripting
```

**Trade-offs:**

| Strategy | Startup | Parallelism | Complexity |
| :--- | :--- | :--- | :--- |
| Stateless | Slow (auth each time) | Easy | Low |
| State File | Medium | Careful (locking) | Medium |
| Daemon | Fast | Easy (multiplexed) | High |

### 7.3 Connection Resilience

For network-dependent tools:

- **Retry with backoff.** Don't fail on first timeout.
- **Reconnect on failure.** Re-read config (ports, tokens may change), rebuild sessions, retry command.
- **Timeout every command.** Wrap dispatch in `asyncio.wait_for()` — stale connections hang forever without timeouts.
- **Checkpoint long operations.** Resume from last successful point.
- **Offline mode.** Queue operations when disconnected.

### 7.4 MCP Compatibility Mode

A CLI tool can also serve as an MCP server, enabling use from Claude Desktop, Claude Code, or other MCP clients. This "dual-mode" pattern provides maximum flexibility.

**Pattern: Flag-based mode switching**

```python
def main():
    if "--mcp" in sys.argv:
        from .mcp_server import run_mcp
        run_mcp()  # stdio transport, JSON-RPC
    else:
        run_cli()  # Normal argparse CLI
```

**Critical: stdout discipline**

MCP's stdio transport uses stdout exclusively for JSON-RPC messages. Any non-protocol output corrupts the message stream—the #1 cause of MCP debugging issues [7].

```python
import sys
import logging

# WRONG - breaks MCP transport
print("Starting...")           # Pollutes stdout
logging.basicConfig()          # Defaults to stderr, but verify

# CORRECT - explicit stderr
logging.basicConfig(stream=sys.stderr)
print("Debug", file=sys.stderr)
```

**Entry points in pyproject.toml:**

```toml
[project.scripts]
mytool = "mytool.cli:main"      # CLI mode (default)
mytool-mcp = "mytool.mcp:main"  # MCP mode (explicit)
```

Both entry points can coexist. The `--mcp` flag on the main entry provides convenience; the separate `mytool-mcp` entry provides clarity for MCP config files.

---

# Part III: Operations (How)

## 8. Discovery and Documentation

### 8.1 Self-Documenting Commands

```bash
myctl                     # Show available commands
myctl <command> --help    # Show command usage
myctl help <topic>        # Detailed documentation
myctl completion bash     # Shell completion scripts
```

### 8.2 Consistent Patterns

Use predictable verb-noun structure:

```bash
myctl list <resource>     # List resources
myctl get <resource> <id> # Get single resource
myctl create <resource>   # Create resource
myctl update <resource>   # Update resource
myctl delete <resource>   # Delete resource
```

LLMs learn patterns quickly—consistency reduces errors.

### 8.3 Action Dispatcher Pattern

For tools with many operations, consider a single entry point with action parameter. This pattern, common in MCP servers, reduces cognitive load and simplifies both CLI and programmatic use.

```bash
# Traditional: many subcommands
myctl list-users
myctl get-user 123
myctl create-user

# Action dispatcher: one command, action parameter
myctl --action list --resource users
myctl --action get --resource users --id 123
myctl --action help --topic search
```

**Implementation:**

```python
ACTIONS = {
    "list": list_items,
    "get": get_item,
    "create": create_item,
    "delete": delete_item,
    "help": show_help,
}

def dispatch(action: str, **kwargs) -> Result:
    if action not in ACTIONS:
        valid = ", ".join(ACTIONS.keys())
        return Result(error=f"Unknown action '{action}'. Valid: {valid}")
    return ACTIONS[action](**kwargs)
```

**Benefits:**
- Single dispatcher serves both CLI and MCP modes
- Help action provides progressive documentation
- Easier to extend (add action to dict)
- ~70% token savings when used as MCP tool [4]

**When to use:** Tools with 5+ operations, or tools that will also serve as MCP servers.

## 9. CLI Over MCP for Data Pipelines

When an LLM consumes data rather than orchestrating actions, CLI tools with Unix pipes outperform MCP servers:

| Aspect | MCP | CLI + Pipes |
| :--- | :--- | :--- |
| Data path | Source → MCP → LLM context → LLM processes | Source → script → file/stdout → LLM reads |
| Token cost | Every byte passes through context | LLM sees only final output |
| Composability | Limited to tool parameters | Full Unix pipeline |
| Processing | LLM transforms data (slow, expensive) | Scripts transform (fast, free) |

**Pattern:** Scripts extract and transform independently. LLM invokes via Bash tool and reads the result.

```bash
# LLM runs this — data never enters LLM context until final output
extract-events.py | grep "keyword"

# vs. MCP approach — LLM processes every event in context
mcp_call("calendar", action="list") → LLM filters in context
```

**When to use CLI over MCP:**
- Data extraction (scraping, API polling, log parsing)
- Data transformation (filtering, aggregating, reformatting)
- Scheduled/batch operations
- When output format is well-defined

**When MCP is still better:**
- LLM needs to make decisions mid-operation (explore → decide → act)
- Interactive workflows requiring LLM judgment per step
- Tool discovery — LLM doesn't know which script to call

## 10. Pipeline Integration

### 10.1 Unix Philosophy

- **Do one thing well.** Compose with other tools.
- **Text streams as interface.** stdin/stdout/stderr.
- **No side effects on read.** `list` and `get` are safe to run.

### 10.2 Streaming Support

For large outputs:

```bash
myctl export --stream | while read -r line; do
  process "$line"
done
```

Stream JSON Lines (JSONL) for parseable streaming:
```bash
myctl export --format jsonl | jq -c 'select(.status == "active")'
```

## 11. Security

CLI tools execute with user privileges and may handle sensitive data. Design defensively.

### 11.1 Credential Handling

```bash
# WRONG - credentials in command history
myctl --password "secret123" login

# CORRECT - environment variable
export MYCTL_PASSWORD="secret123"
myctl login

# BETTER - prompt or keyring
myctl login  # prompts for password, stores in keyring
```

**Hierarchy (most to least preferred):**
1. System keyring (macOS Keychain, Windows Credential Manager)
2. Environment variables (never logged, but visible in `/proc`)
3. Config file with restricted permissions (`chmod 600`)
4. Never: command-line arguments (visible in `ps`, shell history)

### 11.2 Path Validation

For tools that accept file paths, prevent directory traversal attacks:

```python
from pathlib import Path

def safe_path(user_input: str, base_dir: Path) -> Path:
    """Resolve path safely within base directory."""
    resolved = (base_dir / user_input).resolve()

    # Ensure path doesn't escape base directory
    if not str(resolved).startswith(str(base_dir.resolve())):
        raise SecurityError(f"Path escapes allowed directory: {user_input}")

    return resolved
```

### 11.3 Command Whitelisting (for CLI wrappers)

When building tools that execute other commands (e.g., wrapping `git` or `gh`), use explicit whitelists:

```python
import os
import shlex

ALLOWED_COMMANDS = os.getenv("ALLOWED_COMMANDS", "git,gh").split(",")

def execute_safe(cmd: str) -> str:
    parts = shlex.split(cmd)
    if not parts:
        raise SecurityError("Empty command")

    binary = parts[0]
    if binary not in ALLOWED_COMMANDS:
        raise SecurityError(f"Command not allowed: {binary}")

    # Execute with timeout, capture stderr
    ...
```

**Configuration via environment:**
- `ALLOWED_COMMANDS=git,gh,docker` - whitelist (or `all` to disable)
- `ALLOWED_DIR=/path/to/workspace` - restrict file operations
- `COMMAND_TIMEOUT=30` - prevent hangs

### 11.4 Destructive Operations

Require explicit confirmation for operations that can't be undone:

```bash
# Require --yes or --force
myctl delete user 123 --yes

# Or prompt when interactive (TTY detected)
myctl delete user 123
> This will permanently delete user 123. Continue? [y/N]
```

Document destructive operations clearly in `--help` output.

## 12. Dependency Management

### 12.1 Minimal Dependencies

Every dependency is a security risk and maintenance burden. Prefer standard library:

| Need | stdlib | Avoid |
|------|--------|-------|
| CLI parsing | `argparse` | click, typer |
| JSON | `json` | orjson, ujson |
| Paths | `pathlib` | pathlib2, pathtools |
| HTTP | `urllib.request` | requests (if simple) |
| Config | `configparser`, env vars | dynaconf, python-dotenv |

**When external deps are justified:**
- Complex HTTP (auth, retries): `httpx` or `requests`
- Async: `asyncio` + `aiohttp`
- Validation: `pydantic` (if already using for MCP)
- Keyring: `keyring` (for credential storage)

### 12.2 Supply Chain Security

- **Audit dependencies.** Know what you're installing.
- **Pin versions.** Use `uv.lock` or `requirements.txt` with hashes.
- **Minimize transitive deps.** Each dep brings its own tree.
- **Prefer well-maintained packages.** Check commit activity, security advisories.

Python stdlib + minimal vetted deps > npm-style dependency trees.

## 13. Anti-Patterns

- **❌ Interactive-only commands.** Always support non-interactive mode.
- **❌ Unparseable output.** Mixing formats, inconsistent structure.
- **❌ Silent failures.** Exit 0 when something went wrong.
- **❌ Required positional arguments.** Prefer explicit flags for clarity.
- **❌ Pager by default.** Breaks piping; use only when TTY detected.
- **❌ No suggestions on error.** User types invalid command → show similar valid commands [5].
- **❌ Single error handling strategy. `check(err)` that always aborts.** Different errors need different responses (retry, ignore, notify).
- **❌ Novel flag names. `--silentmode` instead of `-q`.** LLMs must read docs for non-standard flags.
- **❌ Long cryptic docs. Too few examples, no "what not to do".** Users make avoidable mistakes.
- **❌ No defaults. Require all options instead of sensible defaults.** Prompt for missing input when interactive.
- **❌ Logging to stdout.** Breaks piping and MCP transport. Always stderr for diagnostics.
- **❌ Credentials in arguments.** Visible in `ps` and shell history. Use env vars or keyring.
- **❌ Hardcoded paths.** Breaks portability. Use env vars or XDG conventions.
- **❌ Heavy dependencies for simple tasks.** `requests` for one GET? Use `urllib`.

---

# Part IV: Reference

## 14. CLI Standards and Conventions

- **POSIX conventions:** Short flags (`-v`), long flags (`--verbose`), `--` to end flags.
- **GNU conventions:** `--flag=value` syntax, combined short flags (`-abc`).
- **12-Factor App:** Config from environment variables.
- **XDG Base Directory:** `~/.config/mytool/`, `~/.local/share/mytool/` for config and data.

## 15. References

- [1] [Command Line Interface Guidelines](https://clig.dev/) - Comprehensive CLI design principles
- [2] [12-Factor App: Config](https://12factor.net/config) - Environment-based configuration
- [3] [POSIX Utility Conventions](https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/V1_chap12.html) - Standard argument syntax
- [4] [Designing MCP Servers.md](Designing%20MCP%20Servers.md) - Shared principles: fail helpfully, context economy, output filtering
- [5] Lucas F. Costa (2022): [UX Patterns for CLI Tools](https://lucasfcosta.com/2022/06/01/ux-patterns-cli-tools.html) - Suggestions, discoverability
- [6] Atlassian (2024): [10 Design Principles for Delightful CLIs](https://www.atlassian.com/blog/it-teams/10-design-principles-for-delightful-clis) - Defaults, prompting
- [7] [MCP Troubleshooting Guide](https://www.mcpstack.org/learn/mcp-server-troubleshooting-guide-2025) - stdout/stderr discipline, Error -32000
- [8] [MCP Security Survival Guide](https://towardsdatascience.com/the-mcp-security-survival-guide-best-practices-pitfalls-and-real-world-lessons/) - Credential handling, security patterns
- [9] [cli-mcp-server](https://github.com/MladenSU/cli-mcp-server) - Command whitelisting pattern
- [10] [gh-mcp](https://github.com/munch-group/gh-mcp) - CLI wrapper as MCP server example
