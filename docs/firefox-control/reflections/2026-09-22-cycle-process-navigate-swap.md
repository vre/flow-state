# Cycle Reflection (process): navigate context swap

## Process violations, and the remediation

The first attempt at this fix broke five rules: edited on main instead of a worktree,
added `Co-Authored-By` (the project says no co-authors), an over-long unwrapped commit
body, no test-first, and no cross-model review. HC chose full remediation rather than
a patch-up. The work was redone in a worktree, tests first, reviewed.

Cause: the change felt small and urgent — a scheduled job was down. "Small and urgent"
is exactly when the process is skipped and exactly when skipping costs most; the
redone version found defects the first one shipped.

## Cross-model review earned its cost

Six findings across three rounds, five real. Two mattered:

- the container-leakage escalation, which killed a design (`accept_redirect`) I had
  defended twice
- `None == None` as a window match, which no amount of self-review had flagged because
  I wrote both the code and the test that pinned it as correct

A reviewer that argues back is worth more than one that lists issues. Two of the
rounds ended with me disagreeing and having to produce evidence — one of those I won
(the snapshot race is inside the accepted residual risk), one I lost.

## What to do differently

- **Measure the mechanism before designing the fix.** Days went into narrowing a
  heuristic that the mechanism made unnecessary.
- **Distrust compatibility fallbacks in safety checks.** Both blocking findings were
  a "degrade gracefully" branch that silently voided the property being claimed.
- **A test written alongside the code it tests inherits its blind spot.** The
  residual-risk test survived review; the fallback test it sat next to did not.
