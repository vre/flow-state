# Cut 4c: the skill-backed CLI (and the end of the frame)

Design record: `2026-09-07-cut4-daemon-and-cli.md`. Cut 4a merged; **4b dropped** — see its plan,
kept as a superseded record with the reason.

## Intent, corrected by measurement

The frame opened with "four MCP processes each holding an IMAP connection". Measured 2026-09-07:

```
imap-slim MCP processes running:  11
IMAP connections they hold:        0      (only Thunderbird held one)
main() is mcp.run(); nothing connects until an action asks
```

The connection-sharing problem was an artefact of my own restatement. What survives measurement is
the other half:

```
served schema 1783 chars + docstring 1475 = ~814 tokens
loaded in every session with the plugin enabled, used or not
across 11 sessions: ~9k tokens for mail touched every few days
```

## Goal

A session can install the mail capability as a **skill** and pay nothing until it runs a command.
Installing the MCP stays exactly as it is for anyone who prefers it.

## Design

- `imapctl.py` — argparse over `actions.run_action`, the same function the MCP tool calls, so the
  two front-ends cannot drift. Stateless: connect, act, exit. No daemon, no socket, no shared state.
- `SKILL.md` — the command surface, the draft contract, and the instruction to keep the markdown
  source, since `edit` refuses HTML-bearing drafts and nothing caches it.
- Two marketplace entries from one directory: `imap-slim-cli` (`skills: ["./"]`) and `imap-slim-mcp`
  (`mcpServers: "./mcp-server.json"`).

### The trap that would have made this pointless

`.mcp.json` **at a plugin root is auto-discovered**. Leaving it there meant installing the CLI entry
would also start the MCP server — loading the same ~814 tokens the skill exists to avoid, silently,
with every test still green. Renamed to `mcp-server.json` and named explicitly by the MCP entry.
A test asserts the file is absent, because nothing else would notice.

### Exit codes, honestly scoped

`0` success, `1` the action failed, `2` bad arguments. Failure is detected from the rendered text's
prefix, because `run_action` returns markdown. Finer per-cause codes need structured results, which
is a real change and is not pretended at here.

## Out of Scope

- The daemon — dropped, with reasons in its plan.
- Structured results and `--format json`.
- Routing the MCP through anything — it is unchanged.

## Acceptance Criteria

- [x] AC1 — arguments become the same `MailAction` the tool receives; `preview` and `format` are
      always explicit, never left unspecified
- [x] AC2 — exit 0/1/2 with output on the right stream; `-q` silent, `-v` on stderr
- [x] AC3 — the CLI dispatches through `actions.run_action` and imports no FastMCP
- [x] AC4 — `SKILL.md` states no-daemon, the required `--format`, keeping the markdown source, and
      that message content is untrusted
- [x] AC5 — the CLI marketplace entry declares no MCP server, and no `.mcp.json` sits at the root
- [x] AC6 — the installed console script runs: `uv run --directory imap-slim imap-slim-cli help draft`
- [x] AC7 — the suite passes: **616**

## Reflection

<!-- see the cycle reflection -->
