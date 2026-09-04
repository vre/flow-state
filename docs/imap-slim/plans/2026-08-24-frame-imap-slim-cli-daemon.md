# Frame: imap-slim — markdown contract, shared daemon, CLI + MCP from one entrypoint

Status: framing complete, HC approved 2026-08-24. Plan review gate: **all cuts**.

## Problem

Four defects, all reproduced against the running code on 2026-08-24.

### 1. Nothing in the model's context says the body is markdown

`convert_body(body, format_type="markdown")` (`markdown_utils.py:132`) renders markdown to
HTML by default. What a session actually loads is the `use_mail` docstring
(`imap_stream_mcp.py:424-441`, ~355 tok) plus the `MailAction` field descriptions
(`imap_stream_mcp.py:145-163`, ~453 tok). The word "markdown" appears in neither; the payload
description says `format?` and stops. The contract lives in `HELP_TOPICS["draft"]`
(`imap_stream_mcp.py:288-292`), delivered only if the model first calls
`{action:"help", payload:"draft"}` — which it has no reason to do before drafting. The success
response (`imap_stream_mcp.py:849-855`) does not mention rendering either, so there is no
feedback in either direction.

Observed consequence: a session wrote `Otsikko\n=======` as plain-text decoration and got
`<h1>`; `* item` lines became `<ul>`. It then concluded "this draft is pure text" and stripped
its formatting — the opposite of the correct fix.

### 2. Hard line breaks are lost, and the plain part is corrupted

`MARKDOWN_EXTENSIONS` (`markdown_utils.py:14-20`) has no `nl2br`. A signature block:

```
input   Terveisin \n Ville Reijonen \n Itio Consulting Oy
HTML    <p>Terveisin\nVille Reijonen\nItio Consulting Oy</p>   → one running line
plain   line breaks intact
```

The two alternatives of the `multipart/alternative` therefore disagree, and Thunderbird renders
the broken one. Standard markdown offers only trailing double-space (invisible, stripped by
editors and models) as a hard break.

Separate bug, same file: `markdown_to_plain` runs `re.sub(r"==(.+?)==", r"\1", text)`
(`markdown_utils.py:126`). Input `=======` comes out as `===`; `==korostus== ja =====` comes
out as `korostus ja =`. Runs of `~` fail the same way. An ASCII rule line in the plain part is
silently chewed.

### 3. One IMAP connection per Claude Code session; the server allows few

Measured 2026-08-24: **4 `imap-slim` server processes**, one per open session, and `lsof` showed
one holding an established socket to `:993` while **Thunderbird held 4 more to the same host**.
The per-user connection quota is shared with the mail client.

Inside one process the code is correct — `session.py` pools one connection per account and every
`imap_client` function goes through `session.connection_ctx()`. The coordination layer *above*
the process does not exist. Four aggravating factors:

- `CONNECTION_IDLE_TIMEOUT = 300` (`session.py:16`) is checked only inside `get_connection()`
  (`session.py:120`), i.e. on the *next* call. A session that goes quiet holds its socket until
  the process dies. There is no reaper.
- No `atexit` or signal handler anywhere in the package — the process is killed without sending
  `LOGOUT`, so the server holds the slot until its own timeout expires.
- `get_connection()` (`session.py:117-137`) runs outside `self.lock`; the lock guards only the
  caches. Two concurrent tool calls can each build a connection, the second overwrites
  `self.connection`, and the first leaks.
- A connection-limit rejection falls through to
  `except Exception: return f"Error: {type(e).__name__}: {e}"` (`imap_stream_mcp.py:966`). No
  retry, no backoff, no message naming the cause.

### 4. MCP-shaped where a CLI would also serve

An installed MCP costs ~800 tokens of always-loaded schema per session plus a resident process.
Sessions that only occasionally touch mail pay that unconditionally.

## Goal

One `imap-slim` plugin directory exposing two marketplace entries — a skill-backed CLI and an
MCP server — both driven by a single `imapctl.py` entrypoint, both clients of one daemon that
holds **exactly one IMAP connection per account for the whole machine**. Markdown behaviour is
stated where the model can see it, and hard line breaks survive to the rendered mail.

## Constraints and measured facts

Measurements taken 2026-08-24 on this machine, `imap-slim-mcp/.venv` (Python 3.13):

| import | peak RSS | import time |
|---|---|---|
| bare interpreter | 19.2 MB | — |
| `mcp.server.fastmcp` | 60.2 MB | 0.227 s |
| `imapclient, markdown, html2text, pymdownx` | 29.2 MB | 0.029 s |
| both | 61.8 MB | 0.142 s |

Consequences that bind the design:

- **The weight is FastMCP/pydantic, not the IMAP stack.** A "thin MCP shim" that avoided the
  IMAP imports would still cost ~60 MB. This killed an earlier two-front-end design; there is no
  memory argument for splitting the code.
- Therefore `import mcp` **must** be lazy, inside the `mcp` role handler — otherwise every CLI
  invocation pays 41 MB and 0.23 s for nothing. Lazy-importing the IMAP stack is pointless at
  10 MB / 29 ms and is not required.
- The memory win is not "MCP gets smaller"; it is that a skill-only session runs **no** resident
  process, and that N sessions share one daemon and one connection instead of N of each.

Plugin-loader facts, verified against
[plugins-reference](https://code.claude.com/docs/en/plugins-reference) and
[plugin-marketplaces](https://code.claude.com/docs/en/plugin-marketplaces):

- An MCP server starts only if that plugin is installed.
- Auto-discovery per plugin root: `skills/`, `commands/`, `agents/`, `hooks/hooks.json`, and
  **`.mcp.json` at the plugin root**. A root `SKILL.md` is *not* auto-discovered — hence
  chrome-control's explicit `"skills": ["./"]`.
- Marketplace entries may carry their own `skills` / `mcpServers`, and two entries may share one
  `source`. So the MCP config must **not** be named `.mcp.json` at the root, or it would fire for
  the CLI entry too.

Repo constraints: worktree for every file modification; tests in `tests/<plugin>/`, never in
`<plugin>/tests/`; `uv` for the environment; type hints and Google-style docstrings; no comments
that restate the code.

## Design

### Target layout

```
flow-state/imap-slim/                    (git mv from imap-slim-mcp)
├── SKILL.md                 entry "imap-slim-cli"  → skills: ["./"]
├── imapctl.py               roles: client (default) | start (daemon) | mcp (stdio server)
├── imapctl_daemon.py        auto-start, socket path, ensure_running, quit
├── render.py                shared rendering + injection wrap, extracted from imap_stream_mcp.py
├── imap_client.py  session.py  bodystructure.py  markdown_utils.py  injection_defense.py
├── pyproject.toml           console_script: imap-slim-cli = imapctl:main
└── mcp-server.json          entry "imap-slim-mcp" → mcpServers: "./mcp-server.json"
```

```json
{ "name": "imap-slim-cli", "source": "./imap-slim", "skills": ["./"] },
{ "name": "imap-slim-mcp", "source": "./imap-slim", "mcpServers": "./mcp-server.json" }
```

### Three roles, one entrypoint

```
imapctl.py list INBOX   → client: ensures daemon, sends one JSON line, exits
imapctl.py start        → daemon: owns the single IMAP connection per account
imapctl.py mcp          → MCP server on stdio; also a client of the daemon
```

`firefoxctl.py start` already switches roles this way, so this is the established shape in this
repo rather than a new invention. The CLI role and the MCP role share the same client path and
differ only in renderer, so **the action surface is defined once** — the decisive argument, more
than any byte count. Two front-ends would have been two drift surfaces.

Modelled on `chrome-control/chromectl_daemon.py` and `firefox-control/firefoxctl_daemon.py`:
Unix socket `/tmp/imapctl-{uid}.sock`, JSON lines, netcat-compatible, idle watchdog
(`IMAPCTL_IDLE_TIMEOUT`, default 300 s), clean `LOGOUT` on quit, auto-start on first command,
stale-socket detection and removal.

CLI conventions from `builder-cli-tool`'s `writing-cli-tools.md`: `--format json|table`, `-q`,
`-v`, stdout for data and stderr for logs, exit codes 0=ok 1=error 2=usage 3=not-found
4=permission 5=network, and every error naming the fix.

### Accepted consequences

- **The daemon serialises IMAP.** One connection behind one lock: two sessions fetching at once
  queue. Correct given the server's quota, but it is a behaviour change and must be documented.
- Keychain unlocks once for the daemon rather than once per MCP process.
- `imap-slim-mcp@flow-state` is currently enabled in HC's settings; after the split HC reinstalls.

### Rejected alternatives

- **Two directories, thin MCP shim importing only `mcp`.** Rejected: measurement showed the shim
  saves 1.6 MB, not 40, and it doubles the surface that can drift.
- **One directory, one entry shipping both `.mcp.json` and `SKILL.md`.** Rejected: `.mcp.json` at
  the plugin root is auto-discovered, so the CLI-only install would still start the server.
- **Trailing double-space or `pymdownx.escapeall` hardbreak for line breaks.** Rejected as the
  default: invisible and routinely stripped, or requires the writer to know a non-obvious
  convention. `nl2br` matches how mail is actually written and makes HTML agree with plain.

## Cut sequence

Detailed plans are written one cut at a time, immediately before execution, per the repo's
one-cut-at-a-time rule. HC reviews **every** cut plan before it executes.

1. **Markdown contract.** `nl2br`; the `==`/`~~` regex fix; markdown stated in the tool docstring
   *and* the `payload` field description; draft response echoes the format used. Mergeable alone,
   no architecture change.
2. **Connection safety, still in-process.** `get_connection()` under the lock; active idle reaper;
   `atexit` + SIGTERM → `LOGOUT`; connection-limit rejections mapped to a real message with one
   backoff retry. Helps immediately and de-risks cut 4.
3. **Rename and extract.** `git mv imap-slim-mcp imap-slim`, repoint the `imap-stream-mcp`
   symlink, `git mv docs/imap-stream-mcp/* docs/imap-slim/`, extract `render.py`.
4. **Daemon and CLI.** `imapctl.py` client + `start` roles, `imapctl_daemon.py`, `SKILL.md`.
   The cut where the design can still go wrong.
5. **MCP role and packaging.** `imapctl.py mcp`, `mcp-server.json`, two marketplace entries,
   versions, CHANGELOG, README, ADR for the daemon split.

## Open risk to settle empirically

Installing both marketplace entries from one `source` is documented as supported but untested
here. Cut 5 verifies it on this machine. If the two installs collide on plugin identity, the
fallback is a two-directory split, which costs the shared-`render.py` import path and nothing
else.

## Verified fixes carried into cut 1

```
'======='              current '==='        fixed '======='
'==korostus== ja ====='current 'korostus ja =' fixed 'korostus ja ====='
'a ==x== b'            current 'a x b'      fixed 'a x b'      (highlight still works)
regex: (?<!=)==(?!=)(.+?)(?<!=)==(?!=)

nl2br: 'Terveisin\nVille\nItio Oy' → '<p>Terveisin<br />Ville<br />Itio Oy</p>'
       lists, headings and paragraph separation unaffected
```
