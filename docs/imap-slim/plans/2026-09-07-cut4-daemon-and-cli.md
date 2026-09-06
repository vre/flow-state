# Cut 4 (design record): a shared connection for CLI callers, and a CLI that costs no context

**Split into 4a, 4b and 4c on 2026-09-07.** Review found the single cut carried a false goal, an
unauthenticated socket needing real path hardening, a dispatcher move that breaks every patch
target, and framing and lifecycle work that was unspecified. Too much to hold in one gate. This
file stays as the shared design record — the measurements, the threat model and the rejected
designs live here — and each cut below has its own plan and its own review:

| cut | plan | what it is |
|---|---|---|
| 4a | `2026-09-07-cut4a-extract-actions.md` | extract `actions.py`; behaviour-neutral; prerequisite for both others |
| 4b | *(planned when 4a merges)* | the daemon: socket, private directory, startup lock, framing, lifecycle, plus a thin client that proves it end to end |
| 4c | *(planned when 4b merges)* | the full CLI surface, exit-code mapping, `--format json`, `SKILL.md` |

Sections below apply to whichever cut names them.

Revision 2, after review. r1's goal claimed "one connection for the machine" and could not deliver
it: the MCP wrapper still opens its own connection until cut 5 routes it through the daemon, and a
UID-keyed socket is one daemon per OS user, not per machine. The goal below is what this cut can
actually prove.

Frame: `2026-08-24-frame-imap-slim-cli-daemon.md`. Cuts 1a, 1b, 2 and 3 are merged.

Baseline: `cd tests && uv run pytest imap-slim/ -q` → **589 passed**.

## Intent

Measured 2026-08-24: four `imap-slim` MCP processes, one per editor session, each holding its own
IMAP connection, while Thunderbird held four more to the same host. Every session that wants mail
also pays ~800 tokens of always-loaded tool schema whether it touches mail or not.

A daemon holding one connection fixes the first. A skill-backed CLI fixes the second: a session
that installs the skill pays nothing until it actually runs a command.

## Goal

One daemon per OS user owns one IMAP connection per account, and **every CLI invocation shares it**.
The action surface is defined exactly once, so the CLI and the MCP cannot drift apart.

**What this cut does not achieve:** the MCP server still opens its own connection. Running both an
installed MCP and the CLI therefore still uses two connections for one account. Routing the MCP
through the daemon is cut 5, and only after that does the connection count actually fall. Saying
otherwise in r1 was the same class of error as claiming a fix before measuring it.

## Situational Context

- `use_mail` (`imap-slim/imap_stream_mcp.py`) dispatches 11 actions across ~530 lines. Each branch
  parses its payload, calls `imap_client`, and renders a markdown response inline.
- `render.py` (cut 3) holds the helpers that were already standalone. The inline response bodies
  were deliberately left in place until a second caller existed. This cut is that caller.
- `session.py` already serialises everything behind a per-account lease (cut 2), so a daemon adds
  cross-process serialisation on top of correct in-process serialisation.
- `chrome-control/chromectl_daemon.py` and `firefox-control/firefoxctl_daemon.py` are the shape to
  copy: auto-start on first command, unix socket, JSON lines, idle watchdog, `start`/`stop`/`status`.

## Design

### 1. `imapctl.py` has two roles in this cut

```
imapctl.py list INBOX        client: ensure the daemon, send one request, print, exit
imapctl.py start             daemon: own the connection, serve the socket
```

The `mcp` role is cut 5. `firefoxctl.py start` already switches roles this way, so this is the
established shape in this repo rather than a new invention.

### 2. The daemon runs the existing dispatcher

**The daemon receives JSON, not a validated model.** FastMCP builds and validates `MailAction`
before `use_mail` sees it; a socket request decodes to a plain `dict`. The daemon must call
`MailAction.model_validate(...)` itself and return the validation error as a normal failure
response, or every `params.action` access would fail with `AttributeError` and every default and
constraint in the model would be silently skipped.

The daemon calls the **same** action dispatcher the MCP tool calls and returns its rendered text.
No second implementation of the 11 actions, which is the whole point of the frame's
"defined once".

Concretely: the body of `use_mail` moves into a new `actions.py` as
`run_action(params: MailAction) -> str`, and `use_mail` keeps its exact signature, decorator,
annotations and docstring, returning `run_action(params)`.

Three things this does **not** get for free, each of which r1 asserted:

- **Patch targets move.** Tests that patch `imap_stream_mcp.create_draft` intercept a global that
  now resolves in `actions.__dict__`. They must become `actions.create_draft`. "589 tests pass
  unchanged" was false; the honest claim is that no *assertion* changes, only patch paths.
- **The tool schema is not preserved by construction.** FastMCP introspects the wrapper, not
  `run_action`. The wrapper's signature and docstring stay put, and a test asserts the served
  `inputSchema` still matches — cut 1a already reads it, so the instrument exists.
- **`run_action` may be synchronous only if the dispatcher awaits nothing.** Verified before the
  move; if any branch awaits, `run_action` is `async` and both callers await it. Either way the
  IMAP work is blocking and still occupies the caller's thread — unchanged from today, and stated
  rather than quietly inherited.

Dependency direction is one-way: `imap_client` / `session` / `render` / `markdown_utils` →
`actions.py` → `imap_stream_mcp.py` and `imapctl.py`. `MailAction` moves with the dispatcher so
`actions.py` does not import its own front-end.

**What this cut does not do:** it does not turn the 11 branches into structured results. They keep
returning rendered markdown. See §Rejected for why, and what it costs.

### 3. Socket protocol

JSON per line, netcat-compatible, matching the two browser daemons:

```
{"cmd": "action", "params": {...}}   ->  {"ok": true, "text": "..."}   or  {"ok": false, "error": "..."}
{"cmd": "status"}                    ->  {"ok": true, "text": "..."}
{"cmd": "quit"}
```

**Framing is specified, not assumed.** Read incrementally until a newline; enforce a maximum
request size (64 KiB) and a per-client read deadline, so a client that connects and sends `{` with
no newline cannot hold the daemon forever. Reject malformed JSON, oversized lines, missing fields
and unknown commands with a normal failure response rather than by dying. Write responses with a
bounded write deadline and treat `BrokenPipeError` and friends as "client left" — a mail body can
exceed the socket buffer, and an unbounded `sendall` to a client that stopped reading would block
every other request, `status`, `quit` and the watchdog behind it.

**Serialisation is global and that is a stated limitation.** One request at a time: while a long
fetch runs, further clients sit in the listen backlog. Requests for *different accounts* could in
principle proceed in parallel, since the cut 2 lease is per account — so "no throughput to gain" was
too strong. Global serialisation is accepted here for simplicity, and the cost is named: a slow
action delays `status` and `quit` too. The client's request timeout is set above the slowest
plausible action rather than copied from the browser daemon's 60 s.

### 3b. Where the socket lives, and why not `/tmp` directly

The socket grants **full mailbox access with no further authentication** — connecting is enough,
the keychain is already unlocked by the daemon. That makes the path itself part of the threat model,
and the browser daemons' `/tmp/{name}-{uid}.sock` is not a precedent worth copying for mail.

- **A private directory, not a bare path.** `$XDG_RUNTIME_DIR/imapctl/` when it is present and owned
  by the effective UID, else `/tmp/imapctl-{uid}/` created with mode `0700`. `/tmp` is world-writable
  and sticky: another user can pre-create a predictable *file* name, and a dangling symlink there is
  invisible to `os.path.exists` while still defeating `bind`. A `0700` directory validated with
  `lstat` for type and owner is what removes the cross-user race; permissions on the socket inode
  alone do not.
- **No permission window.** `umask(0o077)` around `bind`, restored afterwards. `chmod` after `bind`
  leaves the socket briefly at the process umask, and a connection accepted in that window cannot be
  taken back.
- **Staleness is a narrow predicate.** Under a per-user startup lock: a same-UID socket that does not
  respond within a bounded retry is removed and replaced; a regular file, symlink, directory or
  other-UID entry is **refused** without being touched; a responsive same-UID socket is reused. This
  splits r1's contradictory AC3/AC4, which asked to both remove and refuse the same path.
- **The trust boundary is same-UID.** Any process running as the user can connect. That is the same
  boundary as the keychain itself and is stated rather than implied; the criterion is "another local
  UID cannot connect", not "the inode is unreadable".

### 3c. Startup is serialised

Two CLI invocations starting at once must not both spawn a daemon, and — worse — one must not
mistake the other's freshly bound but not-yet-answering socket for a stale one and unlink it,
leaving an orphaned daemon holding IMAP connections and no way to reach it. An atomic per-user lock
file guards the whole check-remove-bind sequence; the loser connects to the winner.

### 4. Lifecycle

`imapctl_daemon.py`, modelled on `chromectl_daemon.py`: `send_command`, `ensure_daemon_running`
(idempotent), stale-socket detection and removal, `daemon_context`. Idle timeout
`IMAPCTL_IDLE_TIMEOUT`, default 300 s. On idle exit the daemon closes its connections with a real
`LOGOUT`, which is safe because they are live — the cut 2 rule about never sending `LOGOUT` to a
connection believed dead still holds on the failure path.

### 5. CLI conventions

From `builder-cli-tool`'s `writing-cli-tools.md`: stdout is data, stderr is logs, `-q` and `-v`,
errors name the fix, and exit codes `0` ok, `1` error, `2` usage, `3` not found, `4` permission,
`5` network. Subcommands mirror the actions one to one.

### 6. `SKILL.md`

Modelled on `chrome-control/SKILL.md`: what it is, that the daemon auto-starts, the socket path and
idle timeout, the command list, and — carrying HC's decision from cut 1a — **that the caller keeps
the markdown source of any draft it writes**, because `edit` refuses HTML-bearing drafts and there
is no cache.

## Rejected

- **Structured results plus a rendering layer** (`run(action) -> dict`, then `render`). This is the
  better architecture and would give `--format json`. Rejected *for this cut*: it rewrites all 530
  dispatcher lines, and the thing being rewritten is the tool HC uses daily. The daemon and the CLI
  are worth having before that risk is taken, and they do not depend on it.
- **Structured *domain* results** — deferred as above. But `--format json` is **not** rejected:
  the daemon already returns `{"ok", "text"}`, and exposing that envelope costs nothing and gives
  stable success/failure parsing. Markdown stays the default; `--format json` emits the envelope.
  r1 conflated the two and dropped a cheap thing along with an expensive one.
- **Threading the daemon.** Accepted as a limitation, not justified by the lease — see §3.
- **A socket per account.** One daemon, one socket, accounts selected per request as today.

## Acceptance Criteria

- [ ] **AC1 — the action surface is defined once**

```gherkin
Given the MCP tool and the CLI
Then both reach the 11 actions through the same run_action function
And use_mail contains no dispatch logic of its own
And the existing 589 tests pass unchanged, proving the MCP behaviour did not move
```

- [ ] **AC2 — CLI callers share one connection**

```gherkin
Given a running daemon and three sequential CLI invocations for one account, within the idle window
Then the connection factory is invoked exactly once

Given requests for two different accounts
Then one connection per account is created, not one per request

Given the daemon is restarted between two invocations
Then a new connection is created, and only one
```

Deliberately not asserted: that the daemon is the only process on the machine holding a connection.
It is not, until cut 5 routes the MCP through it.

- [ ] **AC3 — auto-start is idempotent, including under a race**

```gherkin
Given no daemon and no socket, when a CLI command runs
Then a daemon starts, the command succeeds, and the socket exists

Given two CLI processes released simultaneously by a barrier
Then exactly one daemon exists afterwards
And neither unlinks the other's socket

Given a same-UID socket with no responder
Then it is removed under the startup lock and replaced
```

- [ ] **AC4 — the path cannot be hijacked, and other users cannot connect**

```gherkin
Given the runtime directory
Then it exists with mode 0700, is a real directory by lstat, and is owned by the effective UID

Given a freshly bound socket
Then its mode is 0600, and the umask was restrictive across the bind

Given a regular file, a symlink or a directory at the socket path
Then the daemon refuses to start and does not modify or unlink it

Given an entry at the socket path owned by another UID
Then the daemon refuses, and never connects to it
```

- [ ] **AC5 — the daemon idles out and releases the server slot**

```gherkin
Given a daemon with IMAPCTL_IDLE_TIMEOUT set low and no requests
Then it exits, and LOGOUT is sent on each live connection before it does
```

- [ ] **AC6 — CLI conventions, with a stated exception-to-exit-code mapping**

| condition | code |
|---|---|
| success | 0 |
| action ran and failed | 1 |
| unknown subcommand, bad flags, model validation error | 2 |
| message, folder or account not found | 3 |
| credentials not configured, or login rejected | 4 |
| `ConnectionFailure`, or the daemon cannot be reached | 5 |

```gherkin
Given a command that succeeds, exit code 0 and the result on stdout, nothing on stderr
Given an unknown subcommand, exit code 2 and a message listing the valid ones
Given a MailAction validation error, exit code 2 naming the field
Given a ConnectionFailure from the daemon, exit code 5
Given credentials are not configured, exit code 4 and the setup guidance
Given -q, stdout is empty and the exit code carries the outcome
Given -v, diagnostics appear on stderr and stdout is unchanged
Given --format json, stdout is the {"ok", "text"} envelope and parses
```

The eleven subcommand signatures are enumerated in the implementation notes before task 4 begins;
"mirrors the actions" is not a specification.

- [ ] **AC7 — the skill states what the caller must keep**

```gherkin
Given SKILL.md
Then it says the daemon auto-starts, names the socket path and the idle timeout
And it says the caller must keep the markdown source of drafts it writes
And it states that output is markdown, not machine-parseable
```

- [ ] **AC8 — lifecycle is bounded on every exit path**

```gherkin
Given a quit command, an idle expiry, and a SIGTERM
Then in each case live connections get LOGOUT with a bounded timeout,
     the socket file is removed, and the process exits

Given LOGOUT fails or times out
Then the daemon still exits and still removes its socket

Given a connection already classified as dead by the cut 2 predicate
Then it is discarded with shutdown(), not sent LOGOUT
```

- [ ] **AC9 — the full suite passes**

```gherkin
When `cd tests && uv run pytest imap-slim/ -q` is run
Then there are zero failures
And the only changes to existing tests are patch targets moved from
    imap_stream_mcp.* to actions.*, listed in the commit message
```

## Testing Strategy

- **Unit, no IMAP**: AC1 by asserting both front-ends call the same function; AC3, AC4 against a
  daemon started with a stubbed action layer, so no credentials and no network are involved.
- **Integration, stubbed backend**: AC2 with a fake connection factory that counts calls, exercised
  through three real CLI invocations against a real socket.
- **AC5** in a subprocess with a one-second idle timeout, asserting exit and the `LOGOUT`.
- **AC6** by invoking the CLI as a subprocess and reading exit codes, not by calling `main()`.
- **The 589 existing tests are the regression instrument for AC1** — the dispatcher move is
  behaviour-preserving or they fail.
- No test touches HC's real mailbox.

## Out of Scope

- Structured results and `--format json` — see §Rejected.
- The `mcp` role and the second marketplace entry — cut 5.
- Reducing the MCP's token cost — that comes from installing the skill instead, which cut 5 packages.
- Windows: the socket is POSIX.

## Tasks

- [ ] 1. Move the dispatcher into `actions.py::run_action`; `use_mail` becomes a wrapper. Suite green.
- [ ] 2. `imapctl_daemon.py`: socket path, send_command, ensure_daemon_running, stale detection.
- [ ] 3. `imapctl.py start`: accept loop, 0600 socket, idle watchdog, LOGOUT on exit.
- [ ] 4. `imapctl.py` client role: argparse subcommands, exit codes, `-q`/`-v`.
- [ ] 5. Tests AC1–AC6.
- [ ] 6. `SKILL.md`; AC7.
- [ ] 7. `pyproject.toml` console script `imap-slim-cli`; `CHANGELOG.md`.
- [ ] 8. Verify: full suite, plus one real command against HC's account only if HC asks.

## Files Changed

| file | change |
|---|---|
| `imap-slim/actions.py` | new — the dispatcher, moved |
| `imap-slim/imap_stream_mcp.py` | `use_mail` becomes a wrapper |
| `imap-slim/imapctl.py`, `imapctl_daemon.py`, `SKILL.md` | new |
| `imap-slim/pyproject.toml` | console script |
| `tests/imap-slim/test_daemon.py`, `test_cli.py` | new |

## Reflection

<!-- Written post-implementation -->
