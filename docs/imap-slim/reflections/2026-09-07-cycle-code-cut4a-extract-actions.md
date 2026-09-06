# Code reflection — cut 4a, extract `actions.py`

593 tests pass (589 before, plus four structural guards), ruff clean. No behaviour changed, and the
served tool schema is byte-identical to the copy recorded before the move.

## The split was the right call

Review of the single cut 4 produced fourteen blockers across a false goal, an unauthenticated
socket, a dispatcher move, socket framing and lifecycle. Splitting it put the refactor on its own
gate, where its one real hazard — patch targets — could be dealt with without competing for
attention against umask windows and startup races.

This cut ran clean as a result: schema pinned, imports checked, 57 predicted failures appeared
exactly where the plan said they would.

## The predicted failure, and why predicting it mattered

Moving the dispatcher moved where `create_draft` resolves. 57 tests failed instantly, all patching
`imap_stream_mcp.create_draft` while the call now looks it up in `actions.__dict__`. The plan said
so, so this was bookkeeping rather than a debugging session.

The dangerous version of this bug is the one that *doesn't* fail: a patch that silently stops
intercepting and lets a test call the real function. These failed loudly only because the real
functions need credentials. A test whose real implementation happened to succeed would have gone
green while testing nothing.

**No compatibility aliases**, deliberately. Re-exporting the client functions from
`imap_stream_mcp` so old patch paths kept working would have left two names for one thing and
hidden exactly this class of bug next time.

## What the guards actually guard

- **The schema literal.** `use_mail_schema.json` was recorded *before* the move. Comparing the
  schema against a freshly computed copy of itself would have proved nothing; a committed literal
  is what makes a future change to the advertised surface a deliberate edit rather than a side
  effect.
- **The import check reads the AST**, not the text. A grep for "fastmcp" would pass on a comment.
  If `actions.py` ever imports FastMCP, the CLI in 4c starts paying the 40 MB it exists to avoid,
  and nothing else would notice.
- **The wrapper signature test.** FastMCP introspects `use_mail`, not what it calls, so the
  annotations and docstring staying put is what keeps the tool description intact. "Unchanged by
  construction" was wrong in the r1 plan; this is the check that makes it true.

## Small correction made during the work

A blanket regex moving `"imap_stream_mcp.X"` patch targets also rewrote the string
`"imap_stream_mcp.py"` in a filename assertion. Same mistake in shape as the one in cut 1a, where a
regex added a `format` argument to the one test that had to omit it: a mechanical edit across tests
needs its exceptions listed before it runs, not discovered afterwards.

## For 4b

`actions.run_action(params: MailAction) -> str` is the seam. The daemon calls it after running
`MailAction.model_validate` on decoded JSON itself — FastMCP does that validation today, and a
socket request will not.
