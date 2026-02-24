# Planning Reflections

## 2026-02-15 Planning Reflection: Constrained Subagent Output

Plan: `docs/youtube-to-markdown/plans/2026-02-15-fire-and-forget-subagents.md`

### How the planning went

Three plan versions in one session. Each killed by testing or HC challenge.

**v1 — Single video_extract.md agent (all Sonnet inline)**. I proposed a new file that merges 4 subskills into one agent, doing all LLM work inline. HC caught two problems: (1) "uses same model for everything" — lost Haiku cost savings, (2) "why can't coordinator isolate context directly?" — forced me to articulate that context is append-only and Task is the only isolation mechanism, but also that isolation wasn't necessary.

**v2 — Background Tasks with status files and polling**. Keep existing subskills, add `run_in_background: true`, poll for status files via Bash. HC said "test it now" — the critical assumption about notification behavior and background task capabilities was untested. Testing revealed: (1) background agents can't use Write tool (auto-denied), (2) notifications are small (~250 chars), and (3) TaskOutput returns only the agent's final message, not the full conversation log.

**v3 — Constrained output instruction (2 lines per prompt)**. Finding #3 collapsed the entire architecture problem into a prompt engineering fix. Two lines added to 7 prompts. No new files, no new infrastructure.

### HC's part

- Challenged over-engineering twice (model diversity loss, unnecessary isolation)
- Brought external advice on subagent patterns (file-based artifacts, constrained output, isolated context)
- Insisted on testing assumptions before finalizing — "test it now, it is an assumption we have to verify now"
- Asked about output format for the constrained message — pushed for informative status on both success and failure paths
- Requested cross-model testing (Haiku + Sonnet) which caught the literal-copying behavior
- Drove the review process via external reviewer, which caught file paths, task count math, insertion anchor contradictions

### My part

- Ran the context analysis (3 background agents) that identified TaskOutput as the dominant consumer
- Proposed and iterated the three plan versions
- Designed and executed the tests (notification behavior, Write permission, TaskOutput content, success/failure cases, cross-model)
- Wrote and revised the plan through self-review and external review
- Updated docs (writing-model-specific-prompts.md, writing-skills.md) with findings
- Added the "test assumptions" rule to CLAUDE.md

### What I learned about planning

1. **Test assumptions during planning, not after.** The assumption "TaskOutput returns the full conversation log" survived two plan versions. One test disproved it and made both plans unnecessary. The cost of three quick tests (~$0.50, 5 minutes) vs implementing v1 or v2 (~hours, ~$10+) is not close.

2. **Over-engineering is the default failure mode.** Each version was more complex than needed. HC's challenges ("why can't the coordinator do this directly?") forced me to question whether the complexity was justified. It wasn't.

3. **External review catches what self-review misses.** I missed the file path issue, the task count math, and the contradictory insertion anchor. Self-review found scope creep (Task 4) and missing risks, but not factual errors in the instructions the implementing agent would follow.

4. **The plan should be writable by a skeptic.** Every claim in the plan was eventually challenged. Having test evidence inline (the results table) made the plan defensible. Claims without evidence ("~30K chars") required caveats.

## 2026-02-15 Planning Reflections: Summary Format Refactor

Plan: `docs/youtube-to-markdown/plans/2026-02-15-summary-format-refactor.md`

### How the planning went

Research-heavy session. 24 format variations tested across 3 videos before writing any plan. The plan itself went through self-review + external review with significant structural fixes.

The brainstorming phase was the real work: 8 format approaches × 3 test videos, evaluated incrementally. The winning format (Concept Card) went through 3 iterations based on HC feedback before approval. Architecture decision (routing table + separate format files) emerged organically from the format proliferation.

### HC's part

- Insisted on seeing real output before judging — "en tiedä vielä kun en näe"
- Drove parallel web research while testing existing formats
- Gave precise visual feedback: front-loading matters, em-dash overuse confuses, labels are noise when position already signals meaning
- Caught the hybrid format being identical to claim-first — quality control on test output
- Specified Concept Card v2 structure explicitly when the hybrid failed
- Proposed the architecture (separate files + routing table)
- Requested English rewrite of the plan

### My part

- Ran web research (10 formats from literature) and all format tests via parallel subagents
- Designed 5 new formats based on research findings and HC feedback
- Iterated Concept Card v1→v2→v3 based on precise feedback
- Wrote research document (488 lines) documenting all findings
- Self-reviewed plan and found 5 issues (handoff gap, cross-cutting placement, format rules, regression, header level rule)
- Incorporated external review's 8 findings into final plan version

### What I learned about planning

1. **Research before planning.** The plan was trivial to write after 24 test variations were done. Without the tests, it would have been speculation about which format to use. Testing cost ~$15 in API calls but eliminated all format selection risk.

2. **HC visual judgment is irreplaceable.** I couldn't have determined that em-dash overuse was a problem, or that labels add noise when position signals meaning. These are aesthetic judgments that require human scanning behavior.

3. **External review catches execution contracts.** Self-review found structural gaps (handoff, cross-cutting). External review found execution-level issues: preserved constraints list, reproducible test criteria, status message contract drift, classification ambiguity handling. Different review perspectives find different categories of bugs.

4. **Separate the decision from the implementation.** The research phase and the plan phase were cleanly separate sessions. The research doc captures WHY (format evaluation), the plan captures WHAT (implementation steps). This separation meant the plan didn't need to re-justify format choices.

## 2026-02-23 Planning Reflections: Draft Attachments

Plan: `docs/imap-stream-mcp/plans/2026-02-21-draft-attachments.md`

### How the planning went

Plan inherited from a previous session as a draft. This session's work was review and hardening — three review rounds that each found distinct classes of issues.

**Round 1 — My review against codebase.** Read the plan, then verified every assumption against actual code via Explore subagent. Found 8 issues: wrong temp path (`/tmp/` vs `tempfile.gettempdir()`), underestimated `modify_draft` refactoring scope, missing `MailAction` field descriptions, wrong test locations, redundant symlink checks, missing `mimetypes` import note, unspecified roundtrip test strategy. All factual verification issues — things the plan claimed about the code that were wrong or incomplete.

**Round 2 — Codex (o3) review against codebase.** Found 9 issues. Overlap with round 1 on basics, but unique finds: test path wrong (`tests/test_draft_attachments.py` vs `tests/imap-stream-mcp/`), `conftest.py` exists (plan said it didn't), `modify_draft` body semantics ambiguous, delete-before-append data loss risk, inline+filename attachments dropped by `Content-Disposition: attachment`-only filter, `html` is not a payload field (`format` is, converted via `convert_body()`), no absolute path validation, missing MCP-layer tests, base64 overhead vs 25 MB limit.

**Round 3 — Codex review post-implementation.** Found 5 issues in the built code: keyring test isolation (pre-existing), `modify_draft` response only showing new attachments (not preserved ones), overview help missing attachment/cleanup, plan saying "copy Message-ID" while code correctly generates new one, inline disposition not preserved on re-attach.

### HC's part

- Set up the codex-cli MCP integration (PATH debugging, .mcp.json config)
- Directed the review flow: "tarkista" → "päivitä" → "edetään" → "aja uusi katselmointi"
- Caught the process gap: "oletko lukenut CLAUDE.md:n?" — I had skipped the structured plan phase end
- Directed code fixes when I suggested moving to reflections with open acceptance criteria: "Jos tarvitaan koodikorjauksia, niin eikö ne pitäisi tehdä"

### My part

- Ran codebase verification (round 1) and identified 8 factual issues
- Evaluated and triaged codex review findings — separated real issues from false positives
- Applied all plan corrections across 3 rounds
- Fixed the two code issues found in round 3 (overview help, modify_draft response)
- Ran tests after each code change (154/154 passing)

### What I learned about planning

1. **Three review rounds find three different classes of bugs.** Round 1 (my verification): factual errors about the codebase. Round 2 (codex pre-implementation): design gaps and missing semantics. Round 3 (codex post-implementation): implementation-vs-plan drift. No single round would have caught all issues.

2. **External reviewers find what self-review cannot.** Codex found `conftest.py` exists, `html` vs `format` payload mismatch, and delete-before-append risk — all things I verified against the code but missed. Different eyes read the same code differently.

3. **Plan review is not implementation review.** Round 2 validated the plan was sound. Round 3 found the implementation diverged from the plan in two places (response format, help text). The plan being correct does not mean the code matches it.

4. **Process enforcement catches drift.** HC's "oletko lukenut CLAUDE.md:n?" prevented me from skipping self-review. Later, "eikö ne pitäisi tehdä" prevented me from closing with open acceptance criteria. Process rules exist because agents drift toward premature completion.

## 2026-02-24 Planning Reflections: IMAP MCP UX Improvements

Plan: `docs/imap-stream-mcp/plans/2026-02-23-ux-improvements.md`

### How planning went

HC identified the three problems from real usage (VikingPLoP2026 session) and brought concrete pain points: LLM doesn't find modify, attachments flood context, draft editing is slow. My role was to mine the session data for evidence, quantify the problems (22 draft calls, 43KB read results, 177s worst case), and propose solutions.

HC steered key design decisions:
- Inline images should still be listed (not hidden) so they're retrievable
- Edit action should follow Claude's Edit tool pattern (old_string/new_string)
- Format validation should reject everything except `plain` and `markdown`
- Challenged my initial "show first 3 + count" inline image display — all should be addressable

I proposed three options for edit (MCP action, tmp file + Edit tool, replace field in draft action). HC picked the standalone action, which was also my recommendation.

### Codex review value

Codex (o4-mini fallback to default) found 9 issues. Most valuable findings:
- `except Exception` already catches `ValueError` — my plan claimed it didn't (factual error against code)
- Attachment schema inconsistency: I said `{filename, content_type, size}` then later required index without updating the schema
- Missing test for `download_attachment` index preservation with mixed parts — the highest regression risk
- HTML text-node editing is infeasible — I had a half-baked "preserve tags" approach that would have been brittle

Less valuable: scope concern about `_rebuild_draft` refactor was valid but I had already flagged it in self-review.

### Lessons

1. **Real session data beats hypotheticals.** The 967-line JSONL analysis gave precise numbers (22 drafts, 24 inline images, 43KB per read) that made the plan concrete. Without this, the plan would have been "read is too verbose" instead of "Outlook signature images produce 24 useless metadata lines."

2. **HC's domain knowledge is irreplaceable.** I would have hidden inline images entirely. HC knew they should be visible but compact — email users sometimes need signature images. This is domain knowledge that no amount of code analysis provides.

3. **Codex catches factual errors against code.** My ValueError claim was wrong — I didn't check the outer exception handler. The reviewer's first instinct was to verify claims against actual source, which caught the error immediately.

## 2026-02-24 Planning Reflections: Competitive Research + Three Discovery Plans

Plans:
- `docs/youtube-to-markdown/plans/2026-02-24-long-transcript-chunking.md`
- `docs/imap-stream-mcp/plans/2026-02-24-attachment-indicator.md`
- `docs/imap-stream-mcp/plans/2026-02-24-list-search-snippet.md`

### How planning went

Session started as competitive research (YouTube MCPs, IMAP MCPs, skill/MCP builders) and evolved into three discovery plans. The research phase produced three survey documents; the planning phase produced three implementation-ready plans at different maturity levels.

**Competitive research (3 parallel subagents).** Mapped 20+ YouTube MCPs, 35+ email MCPs, and builder tools. Key finding: our single-tool action routing pattern is unique across all surveyed projects (0/35 email MCPs, 0/20 YouTube MCPs use it). This validated our architecture but also identified gaps: no attachment indicator in list/search, no body preview snippet, no long transcript handling.

**YouTube chunking plan.** HC identified the problem from real usage (peliteoreetikko 173KB transcript) and proposed the continuation approach. I analyzed the transcript, identified the output token limit as the bottleneck (not Read tool, not input context), and structured 6 research questions. HC corrected my self-review: the plan is discovery-phase, not implementation — research questions are the deliverable.

**IMAP plans.** Initially one combined plan. HC asked to split into two: attachment indicator (simpler, no deps) and snippet preview (complex, depends on indicator). Good call — different maturity levels and different implementation timelines.

**Discovery phase for attachment indicator.** Two parallel subagents researched IMAPClient BODYSTRUCTURE format: one explored our codebase (found zero BODYSTRUCTURE usage, existing attachment logic in 3 places), the other researched IMAPClient's API (found BodyData structure, disposition indices, nested multipart handling). This gave concrete data to replace assumptions in the plan.

**Codex review.** Found 7 issues. Three were high severity: contradictory attachment definition (plan text said "only attachment" but algorithm counted inline+filename), `.is_multipart` not available on plain tuples (breaks tests), and `msg_data[b"BODYSTRUCTURE"]` KeyError risk. The internal contradiction had survived two self-reviews — I had written the algorithm correctly but the surrounding text and acceptance criteria used different language.

### HC's part

- Directed the research scope and parallel execution ("hyödynnä liberaalisti subgentteja")
- Identified long transcript problem from real usage (peliteoreetikko)
- Proposed continuation approach for chunking (let LLM run to output limit, resume)
- Corrected plan maturity: "discovery-vaiheen plani, ei implementaatioplani"
- Split IMAP plans: "jaa nuo imap jutut kahteen planiin" — different scopes, different timelines
- Iterated snippet plan during session: corrected activation mechanism (payload conflict with search), changed fetch size (400→600 for base64), added IMAP FETCH constraint (same data items for all messages in set)
- Directed Codex review via codex-session skill

### My part

- Ran competitive research (3 parallel subagents)
- Deep-dived jkawamoto pagination and marlinjai compact search
- Analyzed peliteoreetikko transcript (173KB, 515 lines, ~42k tokens)
- Wrote all three plans with research questions, architecture context, and acceptance criteria
- Ran BODYSTRUCTURE discovery (2 parallel subagents: codebase + API research)
- Self-reviewed all plans (found and fixed ~15 issues across three plans)
- Applied Codex review findings (7 issues, all corrected)

### What I learned about planning

1. **Discovery plans need different structure than implementation plans.** HC corrected me: the YouTube chunking plan is discovery-phase — research questions are the deliverable, not implementation steps. I kept trying to write implementation details before the research was done. Plan maturity must match the phase.

2. **Internal contradictions survive self-review.** The attachment definition contradiction (algorithm correct, surrounding text wrong) survived two self-reviews. I wrote the algorithm from the codebase but wrote the text from the competitive analysis (which said "only attachment"). Different source material → different conclusions → contradiction. Codex caught it because it cross-checked text against code systematically.

3. **`.is_multipart` on plain tuples** — a concrete example of untested assumptions. I wrote "plain tuples work in tests" without testing it. Codex proved `hasattr(tuple(), 'is_multipart')` is False. The fix (`isinstance(body[0], list)`) was trivial but the assumption would have blocked every test.

4. **HC's plan splits prevent scope creep.** The combined IMAP plan would have been implemented as one feature. Splitting revealed that attachment indicator is standalone (no IMAP body fetch, no decoding pipeline) while snippet has significant complexity (part numbering, charset decoding, HTML stripping, activation mechanism). Different risk profiles → different implementation timelines.

5. **Parallel subagents for discovery are high-value.** The BODYSTRUCTURE research took 2 subagents ~5 minutes and produced concrete data (BodyData structure, disposition indices, nested examples) that replaced 4 "UNVERIFIED" markers in the plan. Cost: ~$1. Alternative: guess and fix during implementation.
