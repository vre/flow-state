# Planning reflection: injection-defense

## What worked

- Reusing the imap-stream-mcp research dossier as a direct input — the threat model and three-layer pattern translated almost 1:1 to youtube-to-markdown's identical-shape `content_safety.py`. No fresh research needed.
- Self-review catching the NFKC-zero-width-misconception. The research doc claimed NFKC strips zero-width chars; empirical Python check showed otherwise. Adding explicit `Cf`-category strip closed the actual gap. Lesson: do not trust prose claims about Unicode behavior; verify with `python3 -c '...'` before locking the design.
- Cross-model review via codex caught four real issues across three iterations that self-review missed:
  1. The legacy-wrapper regex `</?untrusted_[a-z]*>` did not match `<untrusted_description_content>` because content type names contain underscores (blocker).
  2. Unwrap was non-structural — would strip warning-shaped or marker-shaped substrings out of unwrapped raw text. Required whole-string anchoring with backreferences.
  3. Four sibling test files asserted legacy wrapper tags. The original Files Changed section claimed only two files would change.
  4. Multiple stale `8-hex` and `token_hex(4)` references after the 64-bit nonce bump.
- Each codex iteration sharpened the plan rather than thrashing — fixes were targeted, scope stable.

## What changed during planning

- Public surface shrank: `contains_injection_patterns`, `sanitize_for_delimiters`, `INJECTION_DETECTED_NOTICE` removed (dead external API). Tests are the only consumers and are being rewritten anyway.
- Nonce went from `secrets.token_hex(4)` (32 bits) to `secrets.token_hex(8)` (64 bits). Free correctness win after codex pointed out 32-bit "cryptographically infeasible" was overstated.
- Warning syntax went from `[UNTRUSTED ...]` to `{{UNTRUSTED ...}}` to keep the unwrap regex unambiguous (no nested square brackets).
- Unwrap rewritten from "strip patterns" to "structural whole-string match with `\A...\Z` and nonce backreferences". This is stricter and predictable: unwrap is now the precise inverse of wrap, no-op on raw text.
- Files Changed grew from 2 to 6 once codex flagged the sibling test files asserting `<untrusted_*>` tags.

## What I'd do differently

- Run grep across **all** sibling tests for legacy assertions during initial discovery, not just the file under direct edit. Codex caught this on round 2; it should have been in the first cut of Files Changed.
- Verify Unicode/regex empirically before writing AC text. The first AC1 scenario claimed "NFKC removes zero-width chars" — a misconception inherited from the research doc. Two minutes with a Python REPL would have caught it during the first self-review pass instead of needing a second iteration.
- Don't paraphrase "cryptographically infeasible" without checking bit width. 32-bit random is not cryptographically infeasible — it's just hard to predict for a single attempt. Picking the right wording matters when reviewers will challenge it.

## Inputs to next phase

The plan is self-contained — IMP can implement section-by-section without rejoining HC discussion. Key invariants to preserve during implementation:
- Whole-string anchors `\A...\Z` in unwrap regex are load-bearing for the structural-only stripping behavior.
- Backreferences `\1` (TYPE), `\2` (nonce) in unwrap require START and END to match — do not relax.
- `_strip_markers` must iterate until no change (nested `<<S<<SYS>>YS>>` case).
- Lookahead `(?=[\s>/])` on role tags (NOT `\b`) — `\b` would falsely match `<system-design>`.
- `unicodedata.category(c) == 'Cf'` strip is in addition to NFKC, not redundant with it.
