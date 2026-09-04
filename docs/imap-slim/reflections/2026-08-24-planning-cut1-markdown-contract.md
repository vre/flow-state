# Planning reflection — cut 1, markdown contract

## What the review actually cost, and why it was worth it

Four review passes, three rejected designs. Every rejection came from a case I had not thought to
run, and every one was reproduced before I acted on it:

| design | killed by | the case |
|---|---|---|
| r1 lookaround guards | codex pass 1 | `***bold italic***` → guard matches nothing, breaks an existing test; `~~a~~~~b~~` → `a~~~~b` instead of `ab` |
| r2 per-line substitutions | codex pass 2 | `[long label\ncontinued](url)` — the link regex spans newlines, per-line processing silently drops it |
| r3 naive sentinel | codex pass 3 | token `\x00{nonce}{index}\x00` collides with a body containing `\x0001\x00`; restore rewrites user text |

I would have shipped r1. It passed my own skeptic pass, and its defect only shows on inputs I had
not enumerated — triple emphasis and adjacent spans. The lesson is not "review is good"; it is
that **my self-review tested the cases the design was built from**, which is exactly the set that
cannot falsify it.

## What worked

- **Reproducing every finding before acting.** Codex's arithmetic was wrong twice (payload delta,
  docstring delta) and one of its "regressions" was my own malformed test string. Taking findings
  on trust would have put wrong numbers into the plan; running them cost seconds and caught both.
- **Measuring before designing.** The frame's whole two-front-end architecture died on one
  measurement: FastMCP is 60 MB, the IMAP stack is 10 MB. The "thin shim saves memory" argument I
  had already written into a proposal was simply false. Measure first, then choose.
- **Pinning literal expected values in the ACs** rather than "same as before". After three design
  changes, "same as before" would have been ambiguous about *which* before.

## What I got wrong in planning

- **Asserted a negative from one sample.** "`__` is not used for ASCII rules and the current form
  is not defective" — the second clause was a guess stated as fact. `_____` → `*_*`. I had tested
  `**`, `~~`, `==` and generalised to `__` without running it.
- **Leaned on constructs that do not exist.** AC2 in r1 asserted fenced code blocks and tables
  were unaffected. Neither extension is enabled, so both were never supported. I had asserted
  behaviour for a feature the renderer does not have.
- **Budget with no baseline.** AC5 pinned a ceiling against a number I had measured from raw
  source blocks, not from the quantity the test would read. Two different measurements sharing one
  name.

The common shape: each was a statement *about* the code rather than a statement *from* it — the
failure mode the wiki's "open the source" rule names, arriving in a plan rather than in prose.

## Process note

`session-codex` is marked deprecated and its first invocation failed — the execution host timed
out on every read attempt and it correctly refused to invent findings rather than fabricating a
review. Inlining the files into the prompt removed the need for a tool host entirely and worked on
every subsequent pass. That is the cheaper mode for review work regardless: a reviewer that cannot
read files also cannot wander off into the repo.

## Input to cut 2

- Cut 2 touches `session.py` connection handling, where the equivalent of "the cases the design
  was built from" is concurrency. Enumerate the adversarial cases *first* this time: two callers
  racing `get_connection()`, a reaper firing mid-request, SIGTERM during a fetch, a server that
  rejects login for connection limits rather than credentials.
- The `430 passed` baseline moves once cut 1 lands. Re-measure rather than quote this plan.
