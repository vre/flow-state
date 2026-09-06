# Planning reflection: prompt injection defense hardening

## What went well

- HC steered early: rejected over-engineered backwards-compat thinking, narrowed scope to plugin-local module, deferred logging.
- Codex review caught real bugs: legacy wrapper regex (`[a-z]*` vs `[A-Za-z0-9_:-]+`) would have missed the actual `<untrusted_email_content>` tag; role XML regex would have stripped email addresses.
- Three rounds of self-review + two rounds of codex review iterated on a tight feedback loop. Each round surfaced 5–15 distinct issues; after round 3 codex moved from REJECT to ACCEPT.

## What changed during planning

- Initial signature `wrap_untrusted(text, kind)` dropped — YAGNI for one consumer. Hardcoded `EMAIL` in the delimiter.
- AC4 grew from 5 integration points to 7 after codex pointed out folders, accounts, inline_images, content_type, folder echoes in error strings.
- AC8 added explicitly for migrating existing tests in `test_imap_stream_mcp.py` — would have been a CI break otherwise.
- Boolean trigger logic refined: NFKC alone does NOT trigger banner (would fire on legitimate `½ price`); zero-width and BIDI strip DO trigger (always indicate something suspicious).

## Lessons learned

- **Security regex is unforgiving.** Three iterations to land on patterns that are both broad enough (uppercase tokens, numeric variants, attributes) and narrow enough (no false-positives on email addresses). Hand-written security regex without test cases is a footgun.
- **Codex catches regex bugs better than self-review.** The `[a-z]*` vs `[A-Za-z0-9_:-]+` mismatch and the `\b[^>]*>` email-address false-positive were both spotted by codex, missed by self-review.
- **"Out of Scope" sections cause friction.** First version excluded folders; codex flagged it as contradiction with the goal ("every place untrusted text reaches LLM"). Better to either include or have a strong reason for exclusion.
- **Spotlighting nonce alone isn't enough.** Research mentioned this; codex enforced it. Need to also strip fake `[EXTERNAL_*]` patterns from input or attacker can break out.

## Inputs to next phase

- Implementation phase plan is self-contained — IMP can work from the plan alone.
- `kind` parameter dropped means `wrap_untrusted` is single-purpose. If daily-pipeline reuses module later, refactor at that point.
- Banner aggregation (top-level once for list/search) is a small UX choice that could surprise users with mixed-content lists. Watch for HC feedback in implementation.
