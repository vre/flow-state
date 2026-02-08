# Skill Creator Research: Competitive Analysis

## Sources Analyzed

1. [Anthropic's official skill-creator](https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md)
2. [OpenAI's skill-creator (Codex)](https://github.com/openai/skills/blob/main/skills/.system/skill-creator/SKILL.md)
3. [FrancyJGLisboa/agent-skill-creator](https://github.com/FrancyJGLisboa/agent-skill-creator)
4. [alirezarezvani/claude-code-skill-factory](https://github.com/alirezarezvani/claude-code-skill-factory)
5. [Agent Skills Specification](https://agentskills.io/specification)
6. [Context Engineering Skills](https://github.com/muratcankoylan/Agent-Skills-for-Context-Engineering)
7. [obra/superpowers writing-skills](https://github.com/obra/superpowers) (also installed locally)
8. [VoltAgent/awesome-agent-skills](https://github.com/VoltAgent/awesome-agent-skills) - 200+ skills collection
9. [ProfSynapse/PACT-prompt](https://github.com/ProfSynapse/PACT-prompt/blob/main/skills-howto.md) - Progressive disclosure guide
10. [stevenringo's comprehensive guide](https://gist.github.com/stevenringo/d7107d6096e7d0cf5716196d2880d5bb) - Meta-skill concept

---

## Comparison Matrix

| Aspect | Anthropic | OpenAI | agent-skill-creator | skill-factory | superpowers | Our Plan |
|--------|-----------|--------|---------------------|---------------|-------------|----------|
| SKILL.md size | <500 lines | <500 lines | 5000+ words | Generated | <150-500 words | <300 tokens |
| Philosophy | Token economy | Token economy | Comprehensive | Interactive | TDD for docs | Minimal |
| Scripts | init + package | init + validate | Complex 5-phase | Factory agents | render-graphs.js | generate + stub |
| Validation | package_skill.py | quick_validate.py | 25+ tests | Built-in | Subagent pressure tests | Subagent |
| Unique feature | Progressive disclosure | KV-cache aware | AgentDB learning | 4-7 Q&A wizard | **Iron Law + CSO** | Adversarial compression |

---

## Magic Sauce by Implementation

### 1. Anthropic Official

**Magic**: "Context window is a public good"

- Three-level loading: metadata (~100 tokens) → instructions (<5k) → resources (as needed)
- Explicit prohibition of auxiliary docs (README, CHANGELOG)
- Uses `init_skill.py` to generate template, `package_skill.py` to validate
- Description field is PRIMARY trigger - must include all "when to use" info

**What works**:
- Progressive disclosure is genuinely effective
- Challenging each paragraph's token cost

**What's verbose**:
- Still allows <5k words - that's ~3750 tokens
- 500 lines is generous ceiling

### 2. OpenAI Codex

**Magic**: Nearly identical to Anthropic (adopted same spec)

- Same three-level system
- Uses `quick_validate.py` for validation
- Emphasizes KV-cache optimization (stable elements first)

**Unique insight**: "Ordering stable elements first maximizes cache hits" - relevant for skill structure

### 3. FrancyJGLisboa agent-skill-creator

**Magic**: Autonomous generation + learning loop

- AgentDB stores creation episodes
- Success probability calculations
- Template recommendations with confidence scores

**What works**:
- Learning from past creations is clever
- "-cskill" naming convention for discovery

**What's problematic**:
- **5000+ word SKILL.md requirement** - exact opposite of our goal
- **1000+ lines of Python per skill** - massively over-engineered
- ~200k tokens in the skill-creator itself
- This is the anti-pattern we're fighting

### 4. Claude Code Skill Factory

**Magic**: Interactive wizard (4-7 questions)

- Routes to appropriate generator based on answers
- Smart detection: Python needed vs prompt-only
- Multiple factories: skills, agents, prompts, hooks

**What works**:
- Q&A flow reduces ambiguity upfront
- Determines complexity before generating

**What's questionable**:
- "69 professional prompt presets" - bloat indicator
- Factory per artifact type adds complexity

### 5. Superpowers writing-skills (BEST FIND)

**Magic**: "Writing skills IS Test-Driven Development applied to process documentation"

**The Iron Law**: `NO SKILL WITHOUT A FAILING TEST FIRST`

**TDD Mapping**:

| TDD Concept | Skill Creation |
|-------------|----------------|
| Test case | Pressure scenario with subagent |
| Production code | Skill document (SKILL.md) |
| Test fails (RED) | Agent violates rule without skill |
| Test passes (GREEN) | Agent complies with skill present |
| Refactor | Close loopholes while maintaining compliance |

**Critical Discovery - Description Trap**:
> "Testing revealed that when a description summarizes the skill's workflow, Claude may follow the description instead of reading the full skill content."

- Description = trigger conditions ONLY
- NEVER summarize workflow in description
- ❌ BAD: "Use when executing plans - dispatches subagent per task with code review between tasks"
- ✅ GOOD: "Use when executing implementation plans with independent tasks"

**Token Budgets (strictest found)**:
- getting-started workflows: <150 words each
- Frequently-loaded skills: <200 words total
- Other skills: <500 words

**CSO (Claude Search Optimization)**:
- Keywords throughout: error messages, symptoms, tools
- Gerund naming: `creating-skills` not `skill-creation`
- Rich triggers in description

**Rationalization Tables**:
- Document verbatim excuses from baseline testing
- Add explicit counters for each

**What's exceptional**:
- Only implementation that TESTS skills before deployment
- Strictest token budgets
- Psychological understanding of agent behavior
- Explicit anti-patterns with counters

### 6. Additional Notable Sources

**VoltAgent/awesome-agent-skills** (200+ skills):
- Shows template-first approach: `anthropics/template` as starting point
- Domain-specialization pattern: official teams publish framework-specific skills
- Composition-based design: skills as orchestration of smaller capabilities

**ProfSynapse PACT-prompt**:
- "Degree-of-freedom matching" - calibrate specificity to task fragility
- Narrow guidance for sensitive operations, flexible for context-dependent
- Challenges creators to justify every token

**stevenringo's guide**:
- "Autonomous activation model" - Claude decides when to trigger, not user
- Meta-skill concept: `skill-creator` teaching Claude to build skills
- Clear decision boundaries: skills vs slash commands vs MCP vs CLAUDE.md

---

## Patterns That Relate to Our Minimal Context Approach

### Aligned Patterns

1. **Progressive disclosure** - universal agreement: metadata → instructions → resources
2. **Description as trigger** - all implementations agree this is critical
3. **No duplication** - "information lives in EITHER SKILL.md OR references, not both"
4. **Scripts for determinism** - logic in code, orchestration in skill

### Patterns We Should Adopt

1. **KV-cache ordering** (OpenAI): Put stable elements (frontmatter, step headers) first
2. **Interactive wizard** (Skill Factory): 4-7 questions before generation reduces rework
3. **Validation script** (Anthropic/OpenAI): Quick check before deployment
4. **Challenge each paragraph** (Anthropic): Make this adversarial, not advisory

### Patterns We Reject

1. **5000+ word skills** (agent-skill-creator): Defeats the purpose
2. **Learning databases** (agent-skill-creator): Over-engineering for simple task
3. **Factory per artifact type** (skill-factory): We want one modular skill
4. **69 presets** (skill-factory): Bloat indicator, not feature

---

## Gap Analysis: What Nobody Does Well

### 1. Adversarial Token Enforcement

All implementations SAY "challenge each paragraph" but none ENFORCE it:
- Anthropic: <500 lines (generous)
- OpenAI: <500 lines (same)
- agent-skill-creator: 5000+ words (ridiculous)

**Our opportunity**: Hard fail at 300 tokens, validation by subagent

### 2. "Doesn't Need a Skill" Detection

None ask: "Should this even be a skill?"

**Our opportunity**: Gate simple tasks with "Are you sure? Could be: `{cmd}`"

### 3. Bottling Existing Workflows

agent-skill-creator mentions "batch creation from transcripts" but it's complex.

**Our opportunity**: Simple session-based extraction OR historian MCP integration

### 4. Script Existence Validation

Scripts are created WITH the skill. Nobody validates that referenced scripts exist.

**Our approach**: Don't validate existence - scripts created alongside, not pre-existing

---

## Recommendations for Our Implementation

### Keep from Research

1. **Progressive disclosure** - it's proven
2. **Description as trigger** - "Use when X. Produces Y."
3. **init script** - `generate_skill.py` to create skeleton
4. **validate flow** - subagent-based, not script (more flexible)
5. **Interactive Q&A** - reduces ambiguity

### Differentiate

1. **Hard 300 token ceiling** - not advisory 500 lines
2. **Adversarial validation** - fail on prose, not warn
3. **Simple task gate** - "Are you sure?"
4. **Bottling flows** - session and historian
5. **Modular subskills** - only load what's needed

### Avoid

1. Learning databases (AgentDB complexity)
2. Multiple factory types (keep it one skill)
3. Preset libraries (generate fresh, minimal)
4. 5000+ word requirements (absurd)

---

## Conclusion

The existing skill-creators fall into three camps:

**Camp A (Anthropic, OpenAI)**: Good principles, weak enforcement. Say "token economy" but allow 500 lines.

**Camp B (agent-skill-creator, skill-factory)**: Feature-rich, context-heavy. Built for demos, not production.

**Camp C (superpowers)**: Rigorous discipline. TDD-based, strictest token budgets, tests before deployment.

Our approach should build on **Camp C** with additional constraints:
- Adopt TDD for skills (pressure testing with subagents)
- Adopt description = trigger only (avoid workflow summaries)
- Adopt rationalization tables
- Add "doesn't need a skill" gate
- Add bottling flows (session + historian)
- Enforce <300 token hard ceiling (stricter than superpowers' <500 words)

The unique value is **discipline + constraints + gates**. The skill-creator that:
1. TESTS skills before deployment
2. Produces the LEAST tokens per skill
3. Prevents unnecessary skill creation

...wins.
