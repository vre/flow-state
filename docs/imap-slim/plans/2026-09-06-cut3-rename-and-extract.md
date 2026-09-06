# Cut 3: rename to `imap-slim`, and extract what is already separable

Frame: `2026-08-24-frame-imap-slim-cli-daemon.md`. Cuts 1a, 1b and 2 are merged.

Baseline: `cd tests && uv run --frozen pytest imap-slim-mcp/ -q` → **583 passed**.

## Intent

The frame's target layout is one directory serving two marketplace entries — a skill-backed CLI and
an MCP server — built from a single `imapctl.py`. The directory is therefore no longer "the MCP",
and `imap-slim-mcp/` becomes the wrong name for it. This cut does the rename and the docs merge, so
cut 4 can add `imapctl.py` and `SKILL.md` to a directory that is already named for what it holds.

**This cut delivers nothing a user can see.** It exists to make cut 4 possible. That is stated
rather than dressed up.

## Goal

`flow-state/imap-slim/` holds the package; `docs/imap-slim/` holds all of its documents; nothing
that currently works stops working, including HC's installed plugin, without any reinstall.

## Situational Context

`grep` for `imap-slim-mcp` or `imap_stream_mcp` outside `.venv` and `.worktrees` finds **40 files**:
`.claude-plugin/marketplace.json`, `.mcp.json`, `CLAUDE.md`, `CLAUDE-spec.md`, `DEVELOPMENT.md`,
`README.md`, `TESTING.md`, `tests/pyproject.toml`, seven files in `tests/imap-slim-mcp/`, three in
`imap-slim-mcp/`, and the rest documents under `docs/`.

Two symlinks exist at the repo root, one of them precedent for exactly this move:

```
AGENTS.md        -> CLAUDE.md
imap-stream-mcp  -> imap-slim-mcp      committed during the previous rename
```

HC's plugin is installed from the local repo path and its MCP server runs as
`/Users/vre/work/flow-state/imap-slim-mcp/.venv/bin/imap-slim`.

## Design

### 1. The rename, with a compatibility symlink

```
git mv imap-slim-mcp imap-slim
ln -s imap-slim imap-slim-mcp          committed, as imap-stream-mcp already is
imap-stream-mcp -> imap-slim           repointed off the old name
```

The symlink is what makes this a non-event for HC: the installed plugin's path keeps resolving, the
running MCP server keeps starting, and no reinstall is needed. Without it the mail tool would break
until HC re-added the marketplace entry — an unacceptable price for a rename that delivers nothing.

`marketplace.json` `source` moves to `./imap-slim`. New installs get the real directory; the
existing one follows the symlink.

### 2. `imap_stream_mcp.py` keeps its name

It is absorbed in cut 5, when `imapctl.py mcp` becomes the MCP role. Renaming it now to
`imap_slim_mcp.py` would churn every test import and both `[project.scripts]` entries, and cut 5
would undo it. The console-script names `imap-slim` and `imap-stream` are unchanged for the same
reason.

### 3. Documents merge into `docs/imap-slim/`

`docs/imap-stream-mcp/{plans,reflections,research}` merges into the existing `docs/imap-slim/`.
Four files under `docs/plans/` and `docs/reflections/` that belong to this plugin — the June 2026
injection-hardening set — move with them; they are in the shared root only because the plugin had
no docs directory of its own at the time.

**Historical documents are not rewritten.** A 2026-01 plan that says `imap-stream-mcp` was correct
when written, and editing it to say `imap-slim` would make the record lie about its own past. Only
live references — configuration, tests, and the CLAUDE/README/TESTING documents that instruct — are
updated.

### 4. `render.py`: extract what is already separable, and nothing else

Moves out of `imap_stream_mcp.py`:

| symbol | why it belongs |
|---|---|
| `format_flags` | pure: flags list → display string |
| `_format_attachment_line` | pure: attachment dicts → one line |
| `_format_description` | pure: format name → its description |
| `classify_connection_error`, `_find_cause`, `_QUOTA_PATTERN` | pure: exception → caller-facing text |
| `POTENTIAL_INJECTION_WARNING`, `POTENTIAL_INJECTION_NOTICE` | constants both front-ends need |

**The dispatcher's inline response bodies stay where they are.** They are f-strings inside the
`use_mail` branches, and extracting them now would mean inventing an interface for a consumer that
does not exist yet. Cut 4 has the second consumer and can shape the interface around what it
actually needs. Extracting earlier is guessing.

## Constraints

- 583 tests pass, with no test changed except its import path and the directory it lives in.
- HC's running plugin keeps working with no reinstall and no config edit.
- No behaviour change of any kind. If a diff line changes what the code does, it does not belong.

## Acceptance Criteria

- [ ] **AC1 — the package moved and still imports**

```gherkin
Given flow-state/imap-slim/
Then it holds imap_stream_mcp.py, imap_client.py, session.py, markdown_utils.py,
     bodystructure.py, injection_defense.py and the new render.py
And importing imap_stream_mcp registers the use_mail tool as before
```

- [ ] **AC2 — the old paths still resolve**

```gherkin
Given the committed symlink imap-slim-mcp -> imap-slim
Then imap-slim-mcp/imap_stream_mcp.py opens the same file as imap-slim/imap_stream_mcp.py
And imap-stream-mcp points at imap-slim, not at a symlink to a symlink
And the command HC's installed plugin runs still starts
```

- [ ] **AC3 — configuration points at the real directory**

```gherkin
Given .claude-plugin/marketplace.json
Then the imap-slim-mcp entry's source is "./imap-slim"

Given .mcp.json and tests/pyproject.toml
Then neither refers to a path that only exists through a symlink
```

- [ ] **AC4 — documents are in one place, and history is not rewritten**

```gherkin
Given docs/
Then docs/imap-stream-mcp/ no longer exists and its files are under docs/imap-slim/
And the four injection-hardening documents from docs/plans and docs/reflections moved with them
And no historical document's prose was edited to change a name it recorded correctly at the time
```

- [ ] **AC5 — render.py holds the separable helpers, and only those**

```gherkin
Given imap-slim/render.py
Then it defines format_flags, format_attachment_line, format_description,
     classify_connection_error and the injection banner constants
And imap_stream_mcp imports them rather than defining them
And no f-string response body from the use_mail branches moved into it
```

- [ ] **AC6 — nothing changed behaviour**

```gherkin
When the full suite runs from tests/imap-slim/
Then 583 tests pass
And the only test edits are the directory name and the sys.path insert in conftest
```

## Testing Strategy

- The existing 583 tests are the instrument. A pure move is proven by them passing unchanged.
- **AC2 is checked by resolving the paths**, not by assuming: `readlink` both symlinks and open a
  file through each.
- **AC5 is checked by import**, asserting the symbols resolve from `render` and that
  `imap_stream_mcp` no longer defines them.
- No new behavioural tests: there is no new behaviour.

## Out of Scope

- **Renaming `imap_stream_mcp.py`** — cut 5 absorbs it.
- **Extracting the dispatcher's inline rendering** — cut 4, when a second consumer exists.
- **Rewriting historical documents' prose.**
- **Removing the compatibility symlinks** — a later decision, once nothing references the old names.
- Cuts 4 and 5.

## Tasks

- [ ] 1. `git mv imap-slim-mcp imap-slim`; add `imap-slim-mcp` symlink; repoint `imap-stream-mcp`.
- [ ] 2. `git mv tests/imap-slim-mcp tests/imap-slim`; fix the conftest `sys.path` insert.
- [ ] 3. `marketplace.json` source; `.mcp.json`; `tests/pyproject.toml`.
- [ ] 4. Merge `docs/imap-stream-mcp/` and the four root injection-hardening documents into
      `docs/imap-slim/`.
- [ ] 5. Live references in `CLAUDE.md`, `CLAUDE-spec.md`, `DEVELOPMENT.md`, `README.md`,
      `TESTING.md`, `imap-slim/README.md`.
- [ ] 6. Create `render.py`; move the six symbols; import them back.
- [ ] 7. AC2 and AC5 checks.
- [ ] 8. Verify: 583 pass, and the installed plugin's command still starts.

## Files Changed

| file | change |
|---|---|
| `imap-slim/` | renamed from `imap-slim-mcp/`; new `render.py` |
| `imap-slim/imap_stream_mcp.py` | six symbols move out, imported back |
| `tests/imap-slim/` | renamed; `conftest.py` path insert |
| `.claude-plugin/marketplace.json`, `.mcp.json`, `tests/pyproject.toml` | paths |
| `CLAUDE.md`, `CLAUDE-spec.md`, `DEVELOPMENT.md`, `README.md`, `TESTING.md` | live references |
| `docs/imap-slim/` | absorbs `docs/imap-stream-mcp/` and four root documents |

## Reflection

<!-- Written post-implementation -->
