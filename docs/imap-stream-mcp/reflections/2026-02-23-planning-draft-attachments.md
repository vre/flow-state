# 2026-02-23 Planning Reflections: Draft Attachments

Plan: `docs/imap-stream-mcp/plans/2026-02-21-draft-attachments.md`

## How the planning went

Plan inherited from a previous session as a draft. This session's work was review and hardening — three review rounds that each found distinct classes of issues.

**Round 1 — My review against codebase.** Read the plan, then verified every assumption against actual code via Explore subagent. Found 8 issues: wrong temp path (`/tmp/` vs `tempfile.gettempdir()`), underestimated `modify_draft` refactoring scope, missing `MailAction` field descriptions, wrong test locations, redundant symlink checks, missing `mimetypes` import note, unspecified roundtrip test strategy. All factual verification issues — things the plan claimed about the code that were wrong or incomplete.

**Round 2 — Codex (o3) review against codebase.** Found 9 issues. Overlap with round 1 on basics, but unique finds: test path wrong (`tests/test_draft_attachments.py` vs `tests/imap-stream-mcp/`), `conftest.py` exists (plan said it didn't), `modify_draft` body semantics ambiguous, delete-before-append data loss risk, inline+filename attachments dropped by `Content-Disposition: attachment`-only filter, `html` is not a payload field (`format` is, converted via `convert_body()`), no absolute path validation, missing MCP-layer tests, base64 overhead vs 25 MB limit.

**Round 3 — Codex review post-implementation.** Found 5 issues in the built code: keyring test isolation (pre-existing), `modify_draft` response only showing new attachments (not preserved ones), overview help missing attachment/cleanup, plan saying "copy Message-ID" while code correctly generates new one, inline disposition not preserved on re-attach.

## HC's part

- Set up the codex-cli MCP integration (PATH debugging, .mcp.json config)
- Directed the review flow: "tarkista" → "päivitä" → "edetään" → "aja uusi katselmointi"
- Caught the process gap: "oletko lukenut CLAUDE.md:n?" — I had skipped the structured plan phase end
- Directed code fixes when I suggested moving to reflections with open acceptance criteria: "Jos tarvitaan koodikorjauksia, niin eikö ne pitäisi tehdä"

## My part

- Ran codebase verification (round 1) and identified 8 factual issues
- Evaluated and triaged codex review findings — separated real issues from false positives
- Applied all plan corrections across 3 rounds
- Fixed the two code issues found in round 3 (overview help, modify_draft response)
- Ran tests after each code change (154/154 passing)

## What I learned about planning

1. **Three review rounds find three different classes of bugs.** Round 1 (my verification): factual errors about the codebase. Round 2 (codex pre-implementation): design gaps and missing semantics. Round 3 (codex post-implementation): implementation-vs-plan drift. No single round would have caught all issues.

2. **External reviewers find what self-review cannot.** Codex found `conftest.py` exists, `html` vs `format` payload mismatch, and delete-before-append risk — all things I verified against the code but missed. Different eyes read the same code differently.

3. **Plan review is not implementation review.** Round 2 validated the plan was sound. Round 3 found the implementation diverged from the plan in two places (response format, help text). The plan being correct does not mean the code matches it.

4. **Process enforcement catches drift.** HC's "oletko lukenut CLAUDE.md:n?" prevented me from skipping self-review. Later, "eikö ne pitäisi tehdä" prevented me from closing with open acceptance criteria. Process rules exist because agents drift toward premature completion.
