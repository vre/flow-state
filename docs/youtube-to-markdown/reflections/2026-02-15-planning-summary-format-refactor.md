# 2026-02-15 Planning Reflections: Summary Format Refactor

Plan: `docs/youtube-to-markdown/plans/2026-02-15-summary-format-refactor.md`

## How the planning went

Research-heavy session. 24 format variations tested across 3 videos before writing any plan. The plan itself went through self-review + external review with significant structural fixes.

The brainstorming phase was the real work: 8 format approaches × 3 test videos, evaluated incrementally. The winning format (Concept Card) went through 3 iterations based on HC feedback before approval. Architecture decision (routing table + separate format files) emerged organically from the format proliferation.

## HC's part

- Insisted on seeing real output before judging — "en tiedä vielä kun en näe"
- Drove parallel web research while testing existing formats
- Gave precise visual feedback: front-loading matters, em-dash overuse confuses, labels are noise when position already signals meaning
- Caught the hybrid format being identical to claim-first — quality control on test output
- Specified Concept Card v2 structure explicitly when the hybrid failed
- Proposed the architecture (separate files + routing table)
- Requested English rewrite of the plan

## My part

- Ran web research (10 formats from literature) and all format tests via parallel subagents
- Designed 5 new formats based on research findings and HC feedback
- Iterated Concept Card v1→v2→v3 based on precise feedback
- Wrote research document (488 lines) documenting all findings
- Self-reviewed plan and found 5 issues (handoff gap, cross-cutting placement, format rules, regression, header level rule)
- Incorporated external review's 8 findings into final plan version

## What I learned about planning

1. **Research before planning.** The plan was trivial to write after 24 test variations were done. Without the tests, it would have been speculation about which format to use. Testing cost ~$15 in API calls but eliminated all format selection risk.

2. **HC visual judgment is irreplaceable.** I couldn't have determined that em-dash overuse was a problem, or that labels add noise when position signals meaning. These are aesthetic judgments that require human scanning behavior.

3. **External review catches execution contracts.** Self-review found structural gaps (handoff, cross-cutting). External review found execution-level issues: preserved constraints list, reproducible test criteria, status message contract drift, classification ambiguity handling. Different review perspectives find different categories of bugs.

4. **Separate the decision from the implementation.** The research phase and the plan phase were cleanly separate sessions. The research doc captures WHY (format evaluation), the plan captures WHAT (implementation steps). This separation meant the plan didn't need to re-justify format choices.
