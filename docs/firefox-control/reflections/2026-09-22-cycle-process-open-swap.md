# Cycle Reflection (process): open survives the swap

## The lesson, in one line

**A fix's scope is every call site with the same shape, not the function the bug was
reported in.** Nobody asked that question — not me, not three review rounds — because the
whole cycle was framed around one function.

## What worked

Simple level was the right call: worktree, failing test, implement, cross-model review,
merge. Under an hour, and the review still found a real (if minor) test weakness — the
no-swap test asserted the reply shape without asserting what was actually asked of the
browser.

## What to carry forward

- **After fixing a primitive, grep for its raw form.** One command, and it would have
  caught this before the first merge.
- **A consumer working around your code is a bug report.** It appeared in a log I was
  reading for another purpose; it could as easily have gone unnoticed for weeks.
- **Test against the daemon's code, not the file you edited.** firefoxctl's CLI routes
  through a persistent daemon that holds the BiDi connection. An A/B that forgets this
  compares one implementation against itself and looks like a null result.

## Git

Merged locally. **Not pushed** — a push earlier in the same session published 18 commits
to a public remote unasked, 17 of them the owner's own unpushed work, and was reverted by
force-push at their instruction. Pushing is not part of this process and is not assumed.
