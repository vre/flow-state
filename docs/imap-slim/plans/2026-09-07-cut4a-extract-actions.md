# Cut 4a: extract `actions.py` so the surface is defined once

Design record: `2026-09-07-cut4-daemon-and-cli.md`. First of the 4a/4b/4c split.

Baseline: `cd tests && uv run pytest imap-slim/ -q` → **589 passed**.

## Intent

The daemon (4b) and the CLI (4c) must reach the same 11 actions the MCP tool reaches. If they get
their own copy, the two surfaces drift and the drift is silent. This cut creates the single
definition they will both call, and does nothing else.

## Goal

`run_action(params: MailAction) -> str` is the one place the 11 actions are implemented.
`use_mail` becomes a wrapper around it with its registration, signature and docstring untouched.
No behaviour changes, and the served tool schema is provably identical.

## Situational Context

- `use_mail` (`imap-slim/imap_stream_mcp.py`) dispatches 11 actions over ~530 lines: `help`,
  `folders`, `accounts`, `list`, `read`, `search`, `edit`, `draft`, `attachment`, `flag`, `cleanup`.
- Cut 3 put the already-standalone helpers in `render.py` and deliberately left the inline response
  bodies in the dispatcher until a second caller existed.
- Cut 1a's `test_tool_description.py` already reads the **served** `inputSchema` through FastMCP's
  tool manager. That is the instrument this cut needs, and it already exists.

## Design

### 1. What moves

The body of `use_mail` becomes `actions.run_action(params)`. `MailAction`, its validators and
`HELP_TOPICS` move with it, because they are inputs to dispatch rather than to the MCP front-end.

Dependency direction, one way only:

```
imap_client / session / render / markdown_utils / injection_defense
        -> actions.py
                -> imap_stream_mcp.py   (and, later, imapctl.py)
```

`actions.py` must not import `imap_stream_mcp`, or 4b's daemon would drag FastMCP in behind it —
which is exactly the 60 MB the CLI exists to avoid paying.

### 2. What stays

`use_mail` keeps its `@mcp.tool(...)` decorator, its `async def use_mail(params: MailAction) -> str`
signature and its docstring, verbatim. FastMCP introspects the wrapper, not what the wrapper calls,
so anything moved off it changes the advertised schema.

`imap_stream_mcp` re-exports `MailAction` so existing imports keep working.

### 3. Sync or async, decided by measurement

`run_action` is synchronous **if** no dispatcher branch awaits. That is checked before the move,
not assumed. If any branch awaits, `run_action` is `async` and both callers await it.

Either way the IMAP work is blocking and occupies the calling thread exactly as it does today. That
is unchanged, not improved, and saying so here stops 4b from inheriting it as a surprise.

### 4. Patch targets move, and that is the honest cost

Tests patching `imap_stream_mcp.create_draft` intercept a module global. Once the call executes in
`actions.py`, Python resolves it in `actions.__dict__` and the patch stops intercepting — silently,
by calling the real function. Every such target becomes `actions.*`.

**No compatibility aliases.** Re-exporting the client functions from `imap_stream_mcp` purely so old
patch paths keep working would leave two names for one thing and hide exactly this class of bug next
time.

## Constraints

- Zero behaviour change. Every test assertion stays as written; only patch targets move.
- The served tool schema is byte-identical before and after.
- `actions.py` imports no front-end.

## Acceptance Criteria

- [ ] **AC1 — one definition, reached by both paths**

```gherkin
Given imap_stream_mcp
Then use_mail's body contains no action dispatch of its own, only the call to run_action

Given actions.py
Then it defines run_action and does not import imap_stream_mcp, mcp or fastmcp
```

- [ ] **AC2 — the served schema did not move**

```gherkin
Given the inputSchema of the registered use_mail tool, read through FastMCP's tool manager
Then it equals the schema recorded before the move, including the format enum,
     every field description, and the required list
```

Recorded as a literal in the test, not compared against a freshly computed copy of itself.

- [ ] **AC3 — the wrapper is still what FastMCP sees**

```gherkin
Given use_mail
Then it is a coroutine function taking one parameter annotated MailAction and returning str
And its docstring still carries the untrusted-content notice and the action examples
```

- [ ] **AC4 — dispatch behaviour is unchanged**

```gherkin
Given every existing behavioural test in the suite
Then each passes with its assertions unmodified
And the only edits are patch targets moved from imap_stream_mcp.* to actions.*,
    listed by name in the commit message
```

- [ ] **AC5 — the suite passes**

```gherkin
When `cd tests && uv run pytest imap-slim/ -q` is run
Then there are zero failures
```

## Testing Strategy

- The 589 existing tests are the instrument: a behaviour-preserving move either keeps them green or
  it did not preserve behaviour.
- **AC2 pins the schema as a literal** in `test_tool_description.py`, so a later cut that changes the
  advertised surface has to change the literal deliberately.
- **AC1's import assertion is mechanical**: read `actions.py`'s AST and assert no import names a
  front-end module. A grep would pass on a comment.
- No new behavioural tests. There is no new behaviour.

## Out of Scope

- The daemon, the socket, the CLI, `SKILL.md` — 4b and 4c.
- Structured results and any change to what the actions return.
- Renaming `imap_stream_mcp.py` — cut 5 absorbs it.

## Tasks

- [x] 1. Verified: the only `async` in the dispatcher is `use_mail`'s own `def` line, and no
      branch awaits. `run_action` is synchronous.
- [ ] 2. Create `actions.py`; move `MailAction`, its validators, `HELP_TOPICS` and the dispatcher.
- [ ] 3. `use_mail` becomes the wrapper; re-export `MailAction`.
- [ ] 4. Move patch targets in the tests; list them.
- [ ] 5. AC1's AST import test; AC2's schema literal; AC3's signature test.
- [ ] 6. Verify: zero failures.

## Files Changed

| file | change |
|---|---|
| `imap-slim/actions.py` | new — `MailAction`, `HELP_TOPICS`, `run_action` |
| `imap-slim/imap_stream_mcp.py` | keeps the tool registration and the wrapper; loses the dispatcher |
| `tests/imap-slim/*.py` | patch targets |
| `tests/imap-slim/test_tool_description.py` | schema literal, signature, import direction |

## Reflection

<!-- Written post-implementation -->
