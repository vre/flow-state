# Code reflection: injection-defense

## What went well

- Outside-in TDD via parametrized pytest worked cleanly: 17 Cf-format chars + 25 marker patterns + 7 false-positive-safe inputs all expressed as `@pytest.mark.parametrize` lists. Each AC scenario maps to one or two test cases. 78 unit tests in 0.03s.
- The structural unwrap regex (`\A...\Z` with `\1`/`\2` backreferences) was straightforward to implement and caught real bugs in design — the test for `[EXTERNAL_..._START] hello` (no END) reliably returned input unchanged.
- The pyright import warnings ("Import 'lib.content_safety' could not be resolved") are spurious — the test runner uses `sys.path.insert` in conftest.py at runtime, which pyright doesn't follow. Recognized this fast and ignored.
- `monkeypatch.setattr(content_safety.secrets, "token_hex", ...)` for deterministic nonce assertions was clean — no test depended on probabilistic uniqueness for correctness.

## What changed from plan

- **Added `\{\{UNTRUSTED CONTENT — [^}]*\}\}` to `_MARKER_PATTERNS`** as the 8th pattern. Discovered during cross-model code review (codex): wrap-then-wrap leaked the inner warning block because no marker pattern matched it. Combined with the existing `[EXTERNAL_..._START|END]` strip, this makes wrap idempotent under double-wrapping — relevant for `33_merge_tier2.py` which reads a previously-wrapped file and re-wraps after merging.
- **Added `stripped.strip()`** before placing body into delimiters. Cosmetic — without it, double-wrap output had multiple blank lines from removed inner artifacts. With it, output is canonical.
- **AC8c added** documenting double-wrap idempotency.

## Code-level lessons

- Regex pattern review with codex caught a critical issue I missed: the original `</?untrusted_[a-z]*>` did not match `<untrusted_description_content>` because content type names contain underscores. Rule: when writing regex against composite identifiers, always test the regex against the actual literal strings, not against simplified examples.
- `\b` is treacherous when role tags can be hyphenated. `<system-design>` triggers `\b` because `-` is a word boundary. Lookahead `(?=[\s>/])` is more precise — the only valid characters that can follow a role-tag name are whitespace, `>`, or `/` (for self-closing).
- NFKC alone does NOT remove zero-width characters. Required explicit `unicodedata.category(c) == 'Cf'` filtering. Verified with `python3 -c '...'` before locking the design — saved a wasted implementation cycle.
- `re.sub` is single-pass left-to-right. Iterative loop is required when pattern A's substitution can expose pattern A again (e.g., `<<S<<SYS>>YS>>` → `<<SYS>>` after first pass). Loop terminates because each pass either shortens the string or returns no change.
- Pre-commit hook (ruff-format) reformatted the implementation file after the first commit, requiring a re-stage and re-commit. This is expected — investigate and fix is the right pattern (CLAUDE.md says never amend; create new commit).
