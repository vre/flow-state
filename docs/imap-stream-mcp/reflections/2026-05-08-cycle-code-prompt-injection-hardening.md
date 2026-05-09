# Code Reflection: prompt-injection-hardening

## What went well
- Module-level compiled regex tuple keeps the hot path tight and side-effect-free; AC2 four-step pipeline maps directly to four code paragraphs in `sanitize_external_text`.
- Outside-In TDD on the BDD scenarios caught one regex edge before any wiring: the role XML pattern would have stripped `<user@example.com>` if the second alternation had been written too loosely. Tightening the tail to `(?:/?>|\s+[^>]*?/?>)` fixed it on first compile.
- The integration tests doubled as a wiring checklist — every AC4 surface (read/list/search/folders/accounts/attachment) has at least one test that asserts banner aggregation and that markers do not survive to the output. No surface was left wired by accident.
- All 402 plugin tests green after migration; no flaky tests introduced.

## What changed from plan
- Reordered the role XML alternation from `(?:system|user|assistant|tool|tool_call|tool_calls|tool_results)` to `(?:tool_results|tool_calls|tool_call|assistant|system|user|tool)`. Plan order relies on `re` backtracking when `tool` matches a prefix of `tool_calls`; longest-first removes that backtracking dependency. Functionally equivalent, behaviorally more predictable.
- `POTENTIAL_INJECTION_NOTICE` is defined per AC5 but currently unused. The original `INJECTION_DETECTED_NOTICE` was inlined inside the wrapper header alongside the warning; with the new nonce wrapper there is no "header section" inside the wrapper to attach a short label to. Kept the constant because AC5 calls for the rename, but it's effectively dead.
- Existing test file had two surfaces affected beyond the explicit task-4 line ranges: the snippet-injection tests (`test_list_hides_injection_like_snippet`, `test_search_hides_injection_like_snippet`) used the old `[content hidden]` placeholder behavior, and three `TestReadActionWrapping` tests (`test_read_shows_attachments_outside_wrapper`, `test_read_truncation_notice_outside_wrapper_before_attachments`, plus the two listed in the plan) referenced `</untrusted_email_content>` as a position marker. Rewrote all of these to use the new nonce delimiters and the new "sanitize, don't hide" behavior.
- Skipped task 7 (manual smoke against live IMAP) — no IMAP credentials available in the autonomous environment. AC7 integration tests cover the same code path against a mocked `read_message`.

## Lessons
- For non-greedy regex alternation under `re.IGNORECASE`, prefer longest-prefix-first ordering. It avoids subtle backtracking dependencies and makes the pattern read in the same direction the matcher tries it.
- "Sanitize and warn" is a strictly better display posture than "hide and warn": the LLM sees what was attempted, the banner explains it was defanged, and there is no information loss for the user. The `[content hidden]` placeholder from 0.7.0 was harder to debug because the trigger was invisible in the response.
- A randomized-nonce wrapper is cheap insurance: 8 hex chars per call (`secrets.token_hex(4)`) makes it impractical for an attacker to pre-compute the boundary string, even though they could in theory enumerate 4 billion variants. The wrapper sentence in `use_mail`'s docstring is the second half of the defense — without telling the LLM what the markers mean, the markers themselves are just decoration.
- The aggregation pattern (`suspicious_patterns_found |= flag` per surface, single banner at top) keeps the user response readable when many rows are flagged. Per-row banners would dominate the output and dilute the signal.
- Removing `_contains_injection_patterns` and `_sanitize_for_delimiters` cost zero coverage — every behavior they had is now tested in `test_injection_defense.py` against the new module's contract instead of the old helpers' implementation. Tests followed the contract, not the function names, which made the migration a deletion rather than a rewrite.
