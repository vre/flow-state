# Code reflection — cut 4c, the skill-backed CLI

616 tests pass, ruff clean. The console script runs from the installed package.

## The frame's premise did not survive being measured again

I opened this work reporting "four MCP processes, one connection, plus Thunderbird's four". Three
plans later it had become "four processes each holding its own connection", and a daemon had been
designed, reviewed twice, and hardened against socket hijacking to solve it.

Measured on the day it was dropped: **11 processes, zero connections.** Nothing connects until an
action asks. HC's question — "why over socket?" — was what made me check, and the answer was that I
had copied `chrome-control`'s daemon along with its file layout. That daemon exists because Chrome
pops a permission dialog on every new WebSocket connection; IMAP has none. I inherited an
architecture without its reason.

The failure was not the first measurement, which was correct. It was that each restatement was
slightly stronger than the last, and nobody was wrong at any single step. That is the exact shape
the wiki's "open the source, not the statement about it" rule describes, arriving in my own plans.

**~600 lines of security-sensitive IPC deleted before being written.** The two review rounds that
hardened it were not wasted — they are why the plan is kept rather than deleted — but the cheapest
defect to fix is still the one in a design nobody built.

## The trap that would have made the whole cut pointless

`.mcp.json` at a plugin root is auto-discovered. The frame recorded that back in August; I still
left `imap-slim/.mcp.json` in place while adding the skill entry. Installing the CLI would have
started the MCP server too, loaded the same ~814 tokens the skill exists to avoid, and every test
would have stayed green.

Caught by listing the two entries side by side and reading what each would actually load — not by
any test, until I wrote one. That test asserts the *absence* of a file, which is the only way this
particular mistake can fail loudly.

## What the CLI is

`imapctl.py` is argparse over `actions.run_action` and nothing else. Cut 4a's extraction is what
makes that possible: one dispatcher, two front-ends, no drift. Two details worth keeping:

- `preview` and `format` are always passed explicitly. The model rejects a missing value, and the
  CLI turns absence of a flag into `False` or a usage error rather than letting `None` through —
  the same "no silent default" rule cut 1a established, held at a second front-end.
- Failure is detected by the rendered text's prefix, which is honest but ugly. Precise exit codes
  need structured results. The plan says so instead of promising a mapping it cannot keep.

## Where the frame ends

Cut 5 was "the MCP role and two marketplace entries". The entries are here; the MCP role does not
exist because the MCP needs no change. The frame is finished, one cut short of its own plan,
because the thing that cut was for turned out not to be a problem.
