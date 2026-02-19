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
