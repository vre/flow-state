# Writing CLI Tools

Concise guide for building CLI tools optimized for both humans and LLM agents. See `Designing CLI Tools.md` for full rationale.

## Core Principles

- Design for scripting first — humans benefit from scriptable tools, scripts don't benefit from human-only features
- Follow Unix/POSIX conventions — LLMs infer standard flags without `--help`
- Default output is minimal — `--verbose` for humans, `--format json` for agents
- Errors MUST suggest fix: `"File not found. Did you mean 'config.json'?"`
- All inputs as arguments, env vars, or stdin — no required interactive prompts
- stdout = data only, stderr = logs/progress/errors
- Exit codes: 0=success, 1=error, 2=usage error

## Output

- TTY detected → human format (table). Piped → JSON
- JSON schema consistent across commands: `{"success": bool, "data": ..., "error": ...}`
- JSONL for streaming: one JSON object per line, pipe to `jq`
- Layered: `-q` (exit code only) → default (essential) → `-v` (detailed) → `--debug` (everything)

## State Management

Choose one:
- **Stateless** (default): all context per invocation. Simple, parallelizable
- **Daemon** (when connection setup is expensive): Unix socket, JSON line protocol, netcat-compatible
  - `myctl daemon` starts, `myctl send <cmd>` talks to it, `myctl daemon-stop` kills
  - Reconnect on failure: re-read config, clear session cache, retry
  - Timeout every command — stale connections hang forever without it

## Data Pipelines: CLI Over MCP

When LLM is data consumer (not orchestrator), CLI + pipes beats MCP:
- Scripts extract and transform — LLM reads final output
- MCP forces all data through LLM context (token cost, latency)
- Unix pipes compose freely: `extract.py | filter.py | format.py`
- Use MCP only when LLM needs to make decisions mid-operation

## Idempotent Sync Pattern

For CLI tools that sync data between systems:
- **Sync ID**: deterministic hash from stable fields (identifies the record)
- **Content hash**: hash from mutable fields (detects changes)
- Store both in target system (e.g., description field: `[sync:abc123:def456]`)
- Diff: `to_keep` (same ID + same content), `to_update` (same ID + different content), `to_add` (new ID), `to_delete` (gone ID)
- Scope operations to incoming data window — don't touch records outside the time range

## Security

- Credentials: keyring > env vars > config file (0600) > never CLI args
- Validate file paths against base directory — prevent traversal
- Destructive operations: require `--yes` or `--force`
- Command wrappers: explicit whitelist of allowed binaries

## Anti-Patterns

- `--silentmode` instead of `-q` — LLMs must read docs for non-standard flags
- Logging to stdout — breaks piping and MCP transport
- Credentials in arguments — visible in `ps` and shell history
- Interactive-only commands — no `--yes` flag for automation
- Silent failures — exit 0 when something went wrong
- Heavy deps for simple tasks — `requests` for one GET, use `urllib`
