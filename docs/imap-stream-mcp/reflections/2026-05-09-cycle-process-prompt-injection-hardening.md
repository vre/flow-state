# Process Reflection: prompt-injection-hardening

## Plan → implementation translation

- IMP completed all 8 tasks autonomously in a single session (~15 min wall, 90 turns). The 9-AC, 17-BDD-scenario plan was self-contained enough that IMP needed no clarifications.
- Two micro-deviations from plan, both judgment calls inside scope:
  - Role XML alternation reordered (longest-prefix-first) — better regex behavior, no spec change.
  - 3 extra existing tests migrated beyond the explicit task-4 line ranges, because they referenced the old `[content hidden]` snippet placeholder which the new "sanitize don't hide" behavior eliminated.
- Skipped task 7 (live IMAP smoke) — correctly identified that no credentials were available in the autonomous environment and that AC7 mocked integration tests cover the same path.
- IMP wrote 60 unit + integration tests against ~17 BDD scenarios. Test density (60 vs 17) is appropriate — each BDD scenario maps to multiple invariants.

## Delegation effectiveness

- session-sandvault was the right choice. session-codex is deprecated for worktree implementation due to git-write sandbox constraints. Sandvault's full OS sandbox + bridged bare git repo handled all 5 commits cleanly.
- Initial sandvault host setup was broken (`/opt/homebrew/opt/sandvault/guest/home` missing). HC fixed in one round, no scope impact.
- The bridged-bare-repo pattern (host `sandbox` remote ↔ sandbox `host` remote) worked first try after the env fix. No permission issues, no merge conflicts.
- IMP's final report was structured: ACs done, plan deviations, skipped tasks, open questions. Made ORC review immediate — ORC verified 402 tests + read 4 files + cross-checked AC4 surfaces in ~10 minutes.

## Process improvements

- **Plan review iteration paid off.** Three rounds of self-review + three rounds of codex-review found 20+ real issues before implementation started. Two were genuine security bugs (legacy wrapper regex didn't match the actual `<untrusted_email_content>` tag; role XML would strip email addresses). Cost: ~30 min planning. Saved: at least one full re-implementation cycle.
- **Banner aggregation strategy wasn't in the original plan.** Codex flagged it during plan review ("how does the boolean propagate?"). The "top-level once, never per-row" pattern is now the de facto standard for any future per-row sanitization in this codebase.
- **Sandvault host-remote naming inconsistency.** Skill docs assume sandbox sees `origin` pointing at the bridge, but our sandbox sees `host` (named differently). IMP adapted by reading actual remotes; harmless friction but worth noting in the skill.
- **`POTENTIAL_INJECTION_NOTICE` is dead code.** AC5 mandated the rename, but the new wrapper has no inline header where the old `INJECTION_DETECTED_NOTICE` used to attach. Decision: keep for symmetry; remove in a follow-up if it stays unused. Better outcome: AC5 should have been "rename only if still in use" or explicit about deletion.

## Lessons for next planning cycle

- For security features, always have codex re-review after first iteration — single-pass plans miss subtle regex bugs that look right.
- "Out of Scope" sections under-specified the first time (IMP would have skipped folder-name sanitization). Codex caught it. Future plans: list every text path that reaches the LLM, then explicitly justify any exclusion.
- Test density of 3-4 unit tests per BDD scenario is the sweet spot for security features. Less misses edge cases; more bloats maintenance.
- IMP's reflection was higher quality when delegation skill produced output as JSON with structured `result` field — easier to parse, less context lost between IMP and ORC.
