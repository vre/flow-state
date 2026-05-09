# Process reflection: injection-defense

## Plan → implementation translation

The plan was self-contained enough to implement directly without reopening discussion with HC. All ten ACs (plus AC8b/c) had Gherkin scenarios that mapped 1:1 to test cases. No "what does this mean?" moments during implementation.

One signal that the plan was right-sized: the implementation file (`content_safety.py`) is 117 lines, the test file is 277 lines. Plan was ~290 lines. Plan/code/test ratio was roughly 1:1:1, which felt appropriate — when plans get to 3× the code size, they tend to be over-specified and over-fit to current understanding.

## Cross-model review effectiveness

Three iterations of codex plan review caught problems self-review missed:
1. Round 1 — legacy wrapper regex didn't match `<untrusted_description_content>` (underscore not in `[a-z]*`); unwrap stripped legitimate user-content lookalikes; test_merge_tier2 et al. needed wrapper assertion updates; nonce-width overstatement.
2. Round 2 — stale 8-hex references after the 64-bit nonce bump.
3. Round 3 — PASS.

Code review also caught a real bug: double-wrap leaks inner warning. This happens in production (`33_merge_tier2.py` reads a wrapped file and re-wraps). Self-review didn't catch it because I was thinking about "input is fresh untrusted text" — never tested the case where input is already-wrapped output.

The pattern: cross-model review catches bugs that come from one's own assumptions. Worth the iteration cost (each round was ~5 minutes of wall-time).

## Delegation effectiveness

Sandvault was unavailable (`sv build` not run on this machine), so I implemented as ORC rather than delegating to IMP. This was fine for a single-cut, well-scoped change. The plan-was-self-contained proof: I executed it without any conversation context except the plan and codebase.

For larger changes, delegation matters more — IMP starting fresh on the plan validates that the plan is unambiguous. Self-implementation lets ambiguities slide because the implementer (me) carries unwritten assumptions.

If sandvault setup becomes routine, the workflow could be: ORC writes plan → codex reviews plan → sandvault-IMP implements → ORC reviews code → codex reviews code → merge. That's the full process. Skipping IMP delegation (as I did here) shaves ~10 minutes but loses the plan-self-containment audit.

## Process improvements

- **Initial Files Changed audit needs grep across siblings.** The plan's first-cut Files Changed listed only the two files I was directly editing. Codex caught that four sibling test files asserted legacy `<untrusted_*>` tags. A grep at the start of planning would have caught this. Note for future plans: when changing any module, grep `tests/` for assertions on observable outputs of that module.
- **Verify research-doc claims before locking AC text.** The 2026-05-07 research doc claimed NFKC strips zero-width chars. Empirically false. AC1's first draft inherited the misclaim. Rule: any research-doc claim about Unicode/regex/encoding behavior gets a 2-minute REPL verification before becoming an AC.
- **Version bumping is decoupled from feature work.** The previous commit `fccd4f8` had "v2.16.0" in its title but didn't bump pyproject.toml or CHANGELOG.md. This left the repo in an inconsistent state I had to navigate. For future cuts: either always bump versions in the same commit that adds features, or never put version numbers in commit titles. Don't mix.
- **Pre-commit hook reformat caused a stale commit cycle.** My first commit was rejected by ruff-format. Re-stage + re-commit worked. CLAUDE.md's "never amend" rule made this clean. No issue, but future ORCs should expect this on first commit of a session.

## Worth keeping

- Three-iteration codex plan review pattern (write → fix → resubmit). Each iteration was tight and produced concrete findings, not vague hand-waving.
- Empirical verification of regex/Unicode claims (`python3 -c '...'`) before AC text. Cheap, high-value.
- Outside-in parametrized tests with ACs as docstring section headers. Tests double as AC documentation.
