# Code reflection — cut 3, rename and extract

589 tests pass (583 before; the six new ones guard repo structure), ruff clean. No behaviour changed.

## The symlink is the whole cut

A rename that delivers nothing a user can see is only acceptable if it costs them nothing. HC's
plugin runs from `/Users/vre/work/flow-state/imap-slim-mcp/.venv/bin/imap-slim`; renaming the
directory without a compatibility symlink would have broken their mail tool until they re-added the
marketplace entry — a real outage in exchange for tidiness. The previous rename in this repo left
`imap-stream-mcp -> imap-slim-mcp` committed for the same reason, so the precedent was already
there to copy.

`test_layout.py` exists because that symlink is invisible to every other test. Delete it and nothing
fails, while the user's tool stops starting. Structure tests are unusual in a plugin suite; this one
earns its place.

## `imap-slim-mcp` is two different things

The grep found 40 files, but most hits must **not** change: `imap-slim-mcp` is the marketplace
plugin name as well as the directory name. `/plugin install imap-slim-mcp@flow-state` stays exactly
as it is. Only path-shaped references moved — `--directory ./imap-slim`, `tests/imap-slim/`,
`imap-slim/README.md`. A blanket replace would have silently changed the install command users copy
out of the README.

Same distinction for history: a 2026-01 plan saying `imap-stream-mcp` was correct when written.
Editing it would make the record lie about its own past. Only instructions were updated.

## What was left undone on purpose

- **`imap_stream_mcp.py` keeps its name.** Cut 5 turns the MCP into a role of `imapctl.py`, so
  renaming the module now is churn that cut 5 undoes. Its README already described the name as
  legacy and kept for compatibility.
- **The dispatcher's inline response bodies stayed in place.** `render.py` took only what was
  already a standalone function. Extracting the f-strings from `use_mail`'s branches would mean
  inventing an interface for the CLI before the CLI exists; cut 4 can shape it around what it
  actually needs.

## One thing found while moving

`POTENTIAL_INJECTION_NOTICE` was dead — defined in `imap_stream_mcp.py`, referenced nowhere in this
plugin. Ruff caught it the moment the import moved, because an unused import is visible where an
unused module-level constant is not. It was not carried into `render.py`: a module being created
today should not be born with dead code in it. The identically-named constant in
youtube-to-markdown is a separate thing and is untouched.

## `--frozen` hid a broken manifest

The worktree ran 589 green with `uv run --frozen`, and the same tree failed to resolve on main:

```
Package metadata name `imap-slim-mcp` does not match given name `imap-slim`
```

`imap-slim-mcp` is the distribution name as well as the directory name, so the dependency entry in
`tests/pyproject.toml` had to keep it while only its path moved. My blanket replace changed both.
`--frozen` reuses the existing lock and never re-resolves, so it could not see the manifest it
would have rejected. It is the right flag for reproducing an environment and the wrong one for
proving a packaging change is sound — this cut edited packaging, and the check that mattered was
the one run without it.

## For cut 4

The directory is now named for what it will hold rather than for what it currently is, and
`render.py` is the seam the CLI will import. Cut 4 adds `imapctl.py`, `imapctl_daemon.py` and
`SKILL.md` beside them, and moves the response rendering down into `render.py` at the point where
there are genuinely two callers.
