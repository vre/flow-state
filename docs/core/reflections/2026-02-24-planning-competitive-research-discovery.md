# 2026-02-24 Planning Reflections: Competitive Research + Three Discovery Plans

Plans:
- `docs/youtube-to-markdown/plans/2026-02-24-long-transcript-chunking.md`
- `docs/imap-stream-mcp/plans/2026-02-24-attachment-indicator.md`
- `docs/imap-stream-mcp/plans/2026-02-24-list-search-snippet.md`

## How planning went

Session started as competitive research (YouTube MCPs, IMAP MCPs, skill/MCP builders) and evolved into three discovery plans. The research phase produced three survey documents; the planning phase produced three implementation-ready plans at different maturity levels.

**Competitive research (3 parallel subagents).** Mapped 20+ YouTube MCPs, 35+ email MCPs, and builder tools. Key finding: our single-tool action routing pattern is unique across all surveyed projects (0/35 email MCPs, 0/20 YouTube MCPs use it). This validated our architecture but also identified gaps: no attachment indicator in list/search, no body preview snippet, no long transcript handling.

**YouTube chunking plan.** HC identified the problem from real usage (peliteoreetikko 173KB transcript) and proposed the continuation approach. I analyzed the transcript, identified the output token limit as the bottleneck (not Read tool, not input context), and structured 6 research questions. HC corrected my self-review: the plan is discovery-phase, not implementation — research questions are the deliverable.

**IMAP plans.** Initially one combined plan. HC asked to split into two: attachment indicator (simpler, no deps) and snippet preview (complex, depends on indicator). Good call — different maturity levels and different implementation timelines.

**Discovery phase for attachment indicator.** Two parallel subagents researched IMAPClient BODYSTRUCTURE format: one explored our codebase (found zero BODYSTRUCTURE usage, existing attachment logic in 3 places), the other researched IMAPClient's API (found BodyData structure, disposition indices, nested multipart handling). This gave concrete data to replace assumptions in the plan.

**Codex review.** Found 7 issues. Three were high severity: contradictory attachment definition (plan text said "only attachment" but algorithm counted inline+filename), `.is_multipart` not available on plain tuples (breaks tests), and `msg_data[b"BODYSTRUCTURE"]` KeyError risk. The internal contradiction had survived two self-reviews — I had written the algorithm correctly but the surrounding text and acceptance criteria used different language.

## HC's part

- Directed the research scope and parallel execution ("hyödynnä liberaalisti subgentteja")
- Identified long transcript problem from real usage (peliteoreetikko)
- Proposed continuation approach for chunking (let LLM run to output limit, resume)
- Corrected plan maturity: "discovery-vaiheen plani, ei implementaatioplani"
- Split IMAP plans: "jaa nuo imap jutut kahteen planiin" — different scopes, different timelines
- Iterated snippet plan during session: corrected activation mechanism (payload conflict with search), changed fetch size (400→600 for base64), added IMAP FETCH constraint (same data items for all messages in set)
- Directed Codex review via codex-session skill

## My part

- Ran competitive research (3 parallel subagents)
- Deep-dived jkawamoto pagination and marlinjai compact search
- Analyzed peliteoreetikko transcript (173KB, 515 lines, ~42k tokens)
- Wrote all three plans with research questions, architecture context, and acceptance criteria
- Ran BODYSTRUCTURE discovery (2 parallel subagents: codebase + API research)
- Self-reviewed all plans (found and fixed ~15 issues across three plans)
- Applied Codex review findings (7 issues, all corrected)

## What I learned about planning

1. **Discovery plans need different structure than implementation plans.** HC corrected me: the YouTube chunking plan is discovery-phase — research questions are the deliverable, not implementation steps. I kept trying to write implementation details before the research was done. Plan maturity must match the phase.

2. **Internal contradictions survive self-review.** The attachment definition contradiction (algorithm correct, surrounding text wrong) survived two self-reviews. I wrote the algorithm from the codebase but wrote the text from the competitive analysis (which said "only attachment"). Different source material → different conclusions → contradiction. Codex caught it because it cross-checked text against code systematically.

3. **`.is_multipart` on plain tuples** — a concrete example of untested assumptions. I wrote "plain tuples work in tests" without testing it. Codex proved `hasattr(tuple(), 'is_multipart')` is False. The fix (`isinstance(body[0], list)`) was trivial but the assumption would have blocked every test.

4. **HC's plan splits prevent scope creep.** The combined IMAP plan would have been implemented as one feature. Splitting revealed that attachment indicator is standalone (no IMAP body fetch, no decoding pipeline) while snippet has significant complexity (part numbering, charset decoding, HTML stripping, activation mechanism). Different risk profiles → different implementation timelines.

5. **Parallel subagents for discovery are high-value.** The BODYSTRUCTURE research took 2 subagents ~5 minutes and produced concrete data (BodyData structure, disposition indices, nested examples) that replaced 4 "UNVERIFIED" markers in the plan. Cost: ~$1. Alternative: guess and fix during implementation.
