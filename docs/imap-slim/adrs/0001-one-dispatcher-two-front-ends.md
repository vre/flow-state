# 0001 — One dispatcher, two front-ends

Status: accepted (v1.1.0)

## Context

The plugin ships as both an MCP server and a skill-backed CLI. An MCP tool schema loads into every
session that enables it (~814 tokens); a skill costs ~41 until invoked. Two implementations of the
same eleven actions would drift apart without anything failing.

## Decision

`actions.run_action(params: MailAction) -> str` is the only implementation. `imap_stream_mcp.py`
wraps it for FastMCP; `imapctl.py` wraps it for the CLI.

`actions.py` must import no front-end — importing FastMCP there costs the CLI ~40 MB it exists to
avoid. Enforced on the AST, since a grep passes on a comment.

## Consequences

- Anything that patches or imports a dispatcher dependency must target `actions.*`, not the
  front-ends.
- FastMCP introspects the wrapper, not what it calls, so the wrapper's decorator, signature and
  docstring are load-bearing. `tests/imap-slim/use_mail_schema.json` pins the served schema, so
  changing the advertised surface requires editing that literal deliberately.
