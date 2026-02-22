# LLM Model Comparison for GitHub Copilot (February 2026)

**Research Date:** 2026-02-05
**Focus:** GitHub Copilot model selection for coding, planning, testing, and reasoning
**Sources:** Web research, Reddit developer experiences, benchmark data

---

## Executive Summary

No single model dominates across all dimensions. The most effective approach is **model switching based on task type** [1].

**Copilot context limit** [24]: All models capped at **64-128K tokens** regardless of native capability. Gemini's 1M context advantage is lost.

| Task Type | Model | Why |
|-----------|-------|-----|
| **Planning/Architecture** | Opus 4.5 | Best reasoning, "inventor" mindset [7] |
| **Production code** | GPT-5.2 Codex | Lowest bugs (22/MLOC), thorough [2] |
| **Daily coding** | Sonnet 4.5 | Best balance of speed/quality/cost |
| **Multi-file refactor** | Raptor mini | Purpose-built for cross-file edits [3] |
| **Code review** | GPT-5.2 Codex | Catches bugs others miss [2] |
| **Fast iteration** | Gemini 3 Flash | 7x speed at 0.33x cost |
| **Quick fixes** | Haiku 4.5 | 6x speed, zero tool-call failures [18] |

**Not recommended in Copilot:**
- Gemini 3 Pro — 1M context capped, highest bugs (200/MLOC), preview [2][24]
- GPT-5.2 (non-Codex) — not code-optimized, 470 concurrency bugs/MLOC [2]
- GPT-5 mini — Haiku 4.5 better at same price tier [18]
- Grok Code Fast 1 — available in VS Code Copilot, not CLI [22]

---

## Model Comparison Table

| Aspect | Opus 4.5 | Sonnet 4.5 | GPT-5.2 Codex | Raptor mini | Gemini 3 Flash | Haiku 4.5 |
|--------|----------|------------|---------------|-------------|----------------|-----------|
| **Style** | Creative, tolerates ambiguity | Correctness-focused | Methodical, thorough | Multi-file specialist | Speed demon | Fast agentic |
| **SWE-bench** | 80.9% ✓ | 70% | 80.0% | ~72% | 78% | ~65% |
| **Control flow bugs/MLOC** | 55 | 65 | 22 ✓ | ~40 | ~150 | ~80 |
| **Security bugs/MLOC** | 44 ✓ | 198 | ~60 | ~50 | ~120 | ~90 |
| **Math (AIME)** | 93% | ~85% | ~95% ✓ | ~70% | ~80% | ~75% |
| **Terminal ops** | 59% ✓ | ~50% | 47% | ~45% | ~45% | ~40% |
| **Speed** | 1.5x | 1.5x | 1x (base) | 2x | 7x ✓ | 6x |
| **Copilot price** | 3x | 1x | 1x | 1x | 0.33x ✓ | 0.33x ✓ |
| **Use when** | Planning, architecture, complex debug | Daily coding, tests, docs | Production code, code review | Multi-file refactor, renames | Fast iteration, boilerplate | Quick fixes, agentic tasks |

✓ = best in category

### Benchmark Explanations

- **SWE-bench** — Real GitHub issues: model must modify repo to fix. Tests practical coding [4]
- **Control flow bugs/MLOC** — Logic errors (wrong conditions, loops). Lower = better [2]
- **Security bugs/MLOC** — Vulnerabilities (injection, traversal). Lower = safer [2]
- **Math (AIME)** — American Invitational Math Exam. Tests abstract reasoning
- **Terminal ops** — CLI tasks (git, navigation, deps). Tests DevOps ability [5]

### Model Selection Guide

- **Opus 4.5** — Creative, tolerates ambiguity, 3x cost. Best when requirements unclear or you're stuck. May miss edge cases.
- **Sonnet 4.5** — Daily driver (1x). Weak security (198 bugs/MLOC) — avoid for auth/crypto
- **GPT-5.2 Codex** — Methodical, thorough, slowest. Catches subtle bugs through diligence (22/MLOC). Best when requirements are clear.
- **Raptor mini** — Purpose-built for cross-file edits. Best for refactoring, renames [3]
- **Gemini 3 Flash** — 7x speed, 0.33x cost. Use for fast iteration, boilerplate (preview)
- **Haiku 4.5** — 6x speed, 0.33x cost. Better reasoning than Flash, zero tool failures [18]

### Task-by-Task Recommendations

**For Planning** I would use:
- **Opus 4.5** — creative, tolerates ambiguity. Best when requirements unclear [7]
- **GPT-5.2 Codex** — "Plan Mode" for architectural changes is unmatched [13]. Best when requirements are clear.
- ❌ **NOT Haiku/Flash** — too shallow for architectural decisions; ❌ **NOT Gemini Pro** — high error rate (200/MLOC) [2]

**For Codebase Architecture Research** I would use:
- **Opus 4.5** — best reasoning within Copilot's 64-128K context cap [24]
- **GPT-5.2 Codex** — methodical analysis, questions assumptions [5]
- ❌ **NOT Gemini Pro** — 1M context capped in Copilot, only weakness (200 bugs/MLOC) remains [2]; ❌ **NOT Haiku** — too shallow

**For Codebase Refactoring** I would use:
- **Raptor mini** — purpose-built for multi-file edits, understands rename/move implications across modules [3]
- **Opus 4.5** — for architectural refactors requiring judgment calls about design tradeoffs
- ❌ **NOT Gemini Pro** — 200 control flow bugs/MLOC means refactors may break things [2]

**For Test Creation** I would use:
- **Sonnet 4.5** — fast, reliable test generation, good cost/quality balance for bulk test writing [19]
- **GPT-5.2 Codex** — when tests need to cover subtle edge cases, more thorough but slower
- ❌ **NOT Opus** — overkill expensive for test boilerplate; ❌ **NOT Gemini Pro** — error-prone tests

**For Running/Validating Tests** I would use:
- **Haiku 4.5** — fastest tool-calling, zero failures in agentic workflows, keeps you in flow [18]
- **Gemini 3 Flash** — 7x speed, good for CI pipelines where latency matters [20]
- ❌ **NOT Opus/GPT-5.2 xhigh** — too slow (1x speed) for rapid test-fix cycles

**For Debugging** I would use:
- **Opus 4.5** — best at holding complex state in mind, traces causality through multiple files [8]
- **GPT-5.2 Codex** — when bug involves subtle logic errors, lowest control flow mistake rate [2]
- ❌ **NOT Flash/Haiku** — too shallow for complex bugs; ❌ **NOT Gemini Pro** — misses control flow issues

**For Bug Fixing** I would use:
- **Opus 4.5** — understands codebase context, produces targeted fixes without collateral damage
- **Sonnet 4.5** — for straightforward fixes where speed matters more than deep analysis
- ❌ **NOT Gemini Pro** — high bug rate means fixes may introduce new bugs [2]

**For Code Review** I would use:
- **GPT-5.2 Codex** — catches most bugs (22 vs 200 control flow errors/MLOC), pedantic in good way [2]
- **Opus 4.5** — for architectural review, catches design issues GPT misses
- ❌ **NOT Gemini Pro** — misses 9x more control flow bugs than GPT [2]; ❌ **NOT Haiku** — too fast/shallow

**For Documentation** I would use:
- **Sonnet 4.5** — balanced quality/speed for docstrings, READMEs, inline comments
- **GPT-5.2** — when docs need technical precision, better at consistent terminology
- ❌ **NOT Opus** — expensive overkill for docs; ❌ **NOT Flash** — may produce shallow explanations

**For Quick Iterations/Boilerplate** I would use:
- **Gemini 3 Flash** — 7x faster than GPT-5.2, cheapest fast option [20]
- **Haiku 4.5** — when you need better reasoning than Flash but still fast [18]
- ❌ **NOT Opus/GPT-5.2 xhigh** — 1x speed kills iteration velocity, overkill for boilerplate

**For Security-Critical Code** I would use:
- **Opus 4.5** — 44 blockers/MLOC vs Sonnet's 198, significant safety gap [2]
- **GPT-5.2 Codex** — second best on security (~60/MLOC), good for validation pass
- ❌ **NOT Sonnet 4.5** — 198 security blockers/MLOC [2]; ❌ **NOT Gemini Pro** — high error rate

---

## Models Overview

### Tier 1: Flagship Reasoning Models

#### Claude Opus 4.5 (Anthropic)
**Best for:** Ambiguous problems, creative solutions, when you're stuck

- **SWE-bench Verified:** 80.9% (first model to exceed 80%) [4]
- **Terminal operations:** 59.3% (11.7pp lead over GPT-5.2) [5]
- **Context window:** 200K tokens (Copilot: 64-128K cap applies)
- **Speed:** 1.5x relative to GPT-5.2 Codex [6]
- **Copilot price:** 3x (premium tier)

**Developer sentiment:**
> "Opus is a creator/inventor while Codex is a diligent engineer." [7]

> "Claude doesn't actually win 95% of benchmarks, yet universally developers find it problem-solves better than every other solution." [8]

**Characteristics:**
- Creative problem solver, tolerates ambiguity
- Faster than Codex (1.5x)
- May miss edge cases — use Codex for final review
- Good when requirements are unclear

**Known issues:**
- Performance degradation reported late January 2026 (likely due to Sonnet 5 training resource allocation) [9]
- European users report better performance during off-peak US hours [9]
- Expensive for high-volume usage

**When to use:**
- Requirements unclear or evolving
- Complex debugging when you're stuck
- Multi-file refactoring with architectural understanding
- Creative problem solving

---

#### GPT-5.2 Codex (OpenAI)
**Best for:** Production code, clear requirements, catching subtle bugs

**Model variants:**
- **GPT-5.2** - general purpose reasoning model (not recommended — see above)
- **GPT-5.2 Codex** - code-specialized variant (fine-tuned for software engineering)
- **Reasoning tiers:** standard, high, xhigh (ascending cost/depth)

*Benchmarks below are for GPT-5.2 Codex unless noted.*

- **SWE-bench Verified:** 80.0% [4]
- **AIME (math):** 100% without tools (vs Claude's ~93%) [10]
- **Control flow bugs:** 22 per MLOC (lowest in cohort) [2]
- **Speed:** 1x (baseline) [6]
- **Copilot price:** 1x (standard tier)

**Developer sentiment:**
> "GPT-5.2 with xhigh reasoning is better at coding. However, the overall experience in Claude Code is better—it's faster, has more tools, can run background agents." [12]

> "Use GPT 5.2 for long-running tasks and Opus for short ones." [7]

> "Codex works with the context window much more efficiently and doesn't get cluttered as easily as Opus." [12]

**Characteristics:**
- Methodical, thorough — catches subtle bugs through diligence (22/MLOC)
- Slower but more reliable for production code
- "Plan Mode" for architectural changes is unmatched [13]
- Better CI/CD integration (cleaner linter/formatter compatibility)

**When to use:**
- Requirements are clear and well-defined
- Final code review — catches subtle errors
- Production code where bug rate matters most
- Math-heavy algorithms requiring precision

---

#### ~~Gemini 3 Pro (Google)~~ — Not recommended in Copilot
**Status:** Preview. Only advantage (1M context) is capped in Copilot.

- **SWE-bench Verified:** 74.2% [4]
- **Context window:** 1M tokens natively — **Copilot caps at 64-128K** [24]
- **Control flow bugs:** 200 per MLOC (highest in cohort) [2]
- **Copilot price:** 1x

**Why not recommended in Copilot:**
- 1M context (its only strength) is capped to 64-128K [24]
- Highest bug rate (200/MLOC control flow errors) [2]
- Still in preview — stability concerns
- At equal context, other models are strictly better

**Developer sentiment:**
> "Gemini 3.0 Pro... sounds like a dumb junior dev. Have to make it understand all the time." [16]

**When it might work:** Frontend generation reportedly avoids "AI gradient style" [15]. But for most Copilot tasks, use Opus/Sonnet/Codex instead.

---

### Tier 2: Fast/Mid-Tier Models

#### Claude Sonnet 4.5 (Anthropic)
**Best for:** Daily coding work, balanced cost/performance

- **Speed:** 1.5x relative to GPT-5.2 Codex [6]
- **Context window:** 200K tokens (Copilot: 64-128K cap applies)
- **Copilot price:** 1x (standard tier)
- **Security vulnerabilities:** 198 blockers/MLOC — avoid for security-critical code [2]

**When to use:**
- Set as default for daily development
- Writing functions, unit tests, small refactors
- Document summarization
- When Opus is overkill

---

#### ~~GPT-5 mini (OpenAI)~~ — Not recommended in Copilot
**Status:** Available but outperformed by Haiku 4.5 at same price tier.

- **Speed:** Fast first-token latency
- **Copilot price:** 0.33x (budget tier)

**Comparison to Haiku 4.5:** [18]
- GPT-5 mini: Better concurrency safeguards, lower hallucination rates
- Haiku 4.5: Faster, more features, better tool calling, zero failures
- **In Copilot: Use Haiku 4.5 instead** — same price, better for coding

---

#### Claude Haiku 4.5 (Anthropic)
**Best for:** Fast tasks, lightweight code explanations, agentic workflows

- **Speed:** 6x relative to GPT-5.2 Codex [6]
- **Context window:** 200K tokens (Copilot: 64-128K cap applies)
- **Copilot price:** 0.33x (budget tier)

**Characteristics:**
- Near-frontier reasoning at fraction of Sonnet price [19]
- Lowest initial latency (keeps users in "flow state")
- Best for multi-step "agentic" workflows with high reliability
- Zero tool-calling failures in comparisons [18]

---

#### Gemini 3 Flash (Google)
**Best for:** Speed-critical applications, fast iteration
**Status:** Preview

- **Speed:** 7x relative to GPT-5.2 Codex [20]
- **Context window:** 1M tokens natively (Copilot: 64-128K cap applies)
- **Copilot price:** 0.33x (budget tier)
- **SWE-bench:** 78% (outperforms larger Gemini Pro at 74.2%) [20]

**Characteristics:**
- Terminal-native AI integration [21]
- Real-time PR automation
- 60-70% lower latency than Claude Sonnet [6]
- Still in preview — may have stability issues

---

### Tier 3: Specialized Models

#### ~~Grok Code Fast 1 (xAI)~~ — Not available in Copilot
**Status:** Only available via xAI API, not in GitHub Copilot.

- **SWE-bench Verified:** 70.8% [22]
- **LiveCodeBench:** 80.0% [22]
- **Speed:** ~92 tokens/sec

**Characteristics:**
- Mixture-of-experts architecture (314B parameters)
- Built from scratch for agentic coding
- Excellent for iterative, small-task workflows

**Note:** Included for completeness. If using xAI API directly, competitive for budget agentic coding.

---

#### Raptor mini (Microsoft/GitHub)
**Best for:** Multi-file edits, large-scale refactoring, cross-file operations
**Status:** Public preview (November 2025)

- **Context window:** ~264K tokens [3]
- **Speed:** 2x relative to GPT-5.2 Codex
- **Copilot price:** 1x (standard tier)
- **Platform:** VS Code, GitHub.com, Visual Studio, JetBrains

**Characteristics:**
- Purpose-built for cross-file operations
- Designed for "edit across many files", "refactor whole modules" [3]
- Based on GPT-5-mini with code-editing focus

---

## Benchmark Summary

### SWE-bench Verified (Real-world software engineering) [4]

| Model | Score | Notes |
|-------|-------|-------|
| Claude Opus 4.5 | 80.9% | First to exceed 80% |
| GPT-5.2 Codex | 80.0% | Statistical parity with Opus |
| Claude Opus 4.5 + Live-SWE-agent | 79.2% | Scaffolding matters |
| Gemini 3 Flash | 78.0% | Faster than Pro |
| Gemini 3 Pro | 74.2% | Large context advantage |
| Grok Code Fast 1 | 70.8% | Budget option |
| Claude Sonnet 4.5 | 70.0% | Daily driver |

### Code Quality (SonarSource Evaluation) [2]

| Metric | Best Model | Worst Model |
|--------|-----------|-------------|
| Control flow bugs/MLOC | GPT-5.2 Codex (22) | Gemini 3 Pro (200) |
| Resource leaks/MLOC | GPT-5.2 Codex (51) | Sonnet 4.5 (195) |
| Security vulnerabilities/MLOC | Opus 4.5 (44) | Sonnet 4.5 (198) |

### Speed (Tokens per Second) [6]

| Model | Speed | First Token | Relative |
|-------|-------|-------------|----------|
| Gemini 3 Flash | 300-400 t/s | 500-800ms | 7x |
| Haiku 4.5 | 300-350 t/s | Sub-second | 6x |
| Grok Code Fast 1 | ~92 t/s | - | 1.8x |
| Claude Sonnet | 77 t/s | 2.0s | 1.5x |
| GPT-5.2 Codex | ~50 t/s | 0.60s | 1x (base) |

---

## Cross-Model Workflows

### Recommended Pipeline [7] [12]

```
Planning     → Claude Opus 4.5 (creative, architectural)
     ↓
Spec Review  → GPT-5.2 Codex (diligent, finds issues)
     ↓
Implementation → Claude Sonnet 4.5 or Gemini Flash (fast, reliable)
     ↓
Code Review  → GPT-5.2 Codex (lowest bug rate)
     ↓
Quick Fixes  → Haiku 4.5 or Gemini Flash (speed)
```

### Task-Based Model Selection

| Scenario | Primary | Fallback | Why |
|----------|---------|----------|-----|
| "Fix this bug" | Opus 4.5 | GPT-5.2 Codex | Deep reasoning needed |
| "Generate boilerplate" | Gemini Flash | Haiku 4.5 | Speed over reasoning |
| "Refactor this module" | Raptor mini | Opus 4.5 | Multi-file understanding |
| "Review this PR" | GPT-5.2 Codex | Opus 4.5 | Catches more bugs [2] |
| "Explain this code" | Sonnet 4.5 | Haiku 4.5 | Balanced, fast |
| "Analyze large codebase" | Opus 4.5 | GPT-5.2 Codex | Best reasoning at 64-128K cap |

---

## Copilot Pricing Multipliers [1]

| Model | Multiplier | Speed | Notes |
|-------|------------|-------|-------|
| Claude Opus 4.5 | 3x | 1.5x | Premium tier |
| Claude Sonnet 4.5 | 1x | 1.5x | Standard tier |
| GPT-5.2 Codex | 1x | 1x | Standard tier |
| Raptor mini | 1x | 2x | Standard tier |
| Gemini 3 Pro | 1x | 1.5x | Preview, not recommended |
| Gemini 3 Flash | 0.33x | 7x | Budget tier, preview |
| Claude Haiku 4.5 | 0.33x | 6x | Budget tier |

*Multiplier = relative cost vs standard models. Speed relative to GPT-5.2 Codex baseline.*

---

## Key Developer Insights (Reddit Synthesis)

### What Developers Actually Experience

1. **Benchmarks don't tell the whole story** [8]
   > "Claude doesn't actually win 95% of benchmarks, yet universally developers find it problem-solves better."

2. **Model degradation is real** [9]
   - Opus 4.5 quality reportedly declined late January 2026
   - Community theory: Resources reallocated for Sonnet 5 training
   - Workaround: Use during off-peak hours (European morning)

3. **Context management matters more than model choice**
   - Aggressive context pruning improves all models
   - Never exceed 100K tokens even if model supports more
   - Fresh sessions often outperform long conversations

4. **The "listens better" factor** [12]
   > "Codex works with the context window much more efficiently and doesn't get cluttered. It also 'listens' better."

5. **Microsoft uses Claude internally** [8]
   > "Microsoft told employees across Windows, Teams, M365, and other divisions to install Claude Code for internal testing alongside Copilot."

6. **Speed vs Intelligence trade-off is real** [12]
   > "Codex 5.2 with xhigh reasoning is better at coding. However, the overall experience in Claude Code is better—it's faster, it has more tools."

---

## Practical Recommendations

### For Individual Developers

1. **Default:** Claude Sonnet 4.5 for daily work [19]
2. **Complex tasks:** Escalate to Opus 4.5 for architecture/debugging (3x cost)
3. **Speed-critical:** Haiku 4.5 or Gemini Flash (0.33x cost)
4. **Code review:** GPT-5.2 Codex for final pass [2]

### For Teams

1. **Hybrid approach:** Route simple tasks to cheap/fast models, complex to flagship [1]
2. **Code quality gates:** Use GPT-5.2 for automated review (lowest bug rate) [2]
3. **Planning sessions:** Opus 4.5 for architectural decisions
4. **CI/CD integration:** Gemini Flash for speed, GPT-5.2 for quality checks

### Cost Optimization

1. **Cache aggressively:** Gemini and Claude support prompt caching
2. **Batch similar requests:** Reduces per-request overhead
3. **Use appropriate tier:** Don't use Opus for tasks Haiku can handle
4. **Monitor usage:** Track tokens by task type

---

## Just Released (February 5, 2026)

### Claude Opus 4.6 [25]

Benchmarks vs other models:

| Benchmark | Opus 4.6 | Opus 4.5 | GPT-5.2 | Winner |
|-----------|----------|----------|---------|--------|
| Terminal-Bench 2.0 | 65.4% | 59.8% | 64.7% | GPT-5.3 (77.3%) |
| SWE-bench Verified | 80.8% | **80.9%** | 80.0% | Opus 4.5 |
| OSWorld | **72.7%** | 66.3% | — | Opus 4.6 |
| GDPVal-AA Elo | **1606** | 1416 | 1462 | Opus 4.6 |
| ARC AGI 2 | **68.8%** | 37.6% | 54.2% | Opus 4.6 |
| BrowseComp | **84.0%** | 67.8% | 77.9% | Opus 4.6 |
| Humanity's Last Exam | **53.1%** | 43.4% | 50.0% | Opus 4.6 |

Key changes:
- **1M token context** (beta) — but Copilot still caps at 64-128K [24]
- Effort levels (low/medium/high/max) to balance intelligence vs speed
- May "overthink simpler tasks" — use lower effort for routine work
- Same pricing as 4.5 (3x in Copilot)

Monitor Copilot for availability. Until then, Opus 4.5 analysis above applies.

### GPT-5.3 Codex [26]

OpenAI released GPT-5.3 Codex same day. Benchmarks (xhigh reasoning):

| Benchmark | 5.3 Codex | 5.2 Codex | 5.2 (non-Codex) |
|-----------|-----------|-----------|-----------------|
| SWE-Bench Pro | 56.8% | 56.4% | 55.6% |
| Terminal-Bench 2.0 | **77.3%** ✓ | 64.0% | 62.2% |
| OSWorld-Verified | **64.7%** | 38.2% | 37.9% |
| Cybersecurity CTF | **77.6%** | 67.4% | 67.7% |
| SWE-Lancer IC Diamond | **81.4%** | 76.0% | 74.6% |
| GDPval (wins/ties) | 70.9% | - | 70.9% |

Key: **Leads Terminal-Bench** (77.3% vs Opus 4.6's 65.4%), OSWorld +26pp. Speed TBD (benchmarks at xhigh).

Monitor Copilot for availability. Until then, GPT-5.2 Codex analysis above applies.

## Watch: Claude Sonnet 5

Rumors suggest Claude Sonnet 5 ("Fennec") coming later:
- 50% cheaper than Opus
- Outperforms Opus 4.5 across metrics (claimed)
- 1M token context window
- Faster than current Sonnet

If released to Copilot, may shift recommendations.

---

## References

[1]: https://docs.github.com/en/copilot/reference/ai-models/model-comparison "GitHub Docs: AI Model Comparison"

[2]: https://www.sonarsource.com/blog/new-data-on-code-quality-gpt-5-2-high-opus-4-5-gemini-3-and-more/ "SonarSource: Code Quality Evaluation - GPT-5.2, Opus 4.5, Gemini 3"

[3]: https://github.blog/changelog/2025-11-10-raptor-mini-is-rolling-out-in-public-preview-for-github-copilot/ "GitHub Changelog: Raptor mini public preview"

[4]: https://llm-stats.com/benchmarks/swe-bench-verified "SWE-bench Verified Leaderboard"

[5]: https://vertu.com/lifestyle/claude-opus-4-5-vs-gpt-5-2-codex-head-to-head-coding-benchmark-comparison/ "Claude Opus 4.5 vs GPT-5.2 Codex: Head-to-head benchmark"

[6]: https://dev.to/superorange0707/choosing-an-llm-in-2026-the-practical-comparison-table-specs-cost-latency-compatibility-354g "DEV.to: Choosing an LLM in 2026 - Practical Comparison Table"

[7]: https://reddit.com/r/cursor/comments/1qdfzzy/ "r/cursor: GPT 5.2 vs Opus 4.5 discussion"

[8]: https://reddit.com/r/ClaudeAI/comments/1qk4up5/ "r/ClaudeAI: Microsoft using Claude Code internally (1125 upvotes)"

[9]: https://reddit.com/r/ClaudeAI/comments/1qui12b/ "r/ClaudeAI: Opus 4.5 really is done - quality decline discussion (949 upvotes)"

[10]: https://www.glbgpt.com/hub/gpt-5-2-vs-claude-opus-4-5/ "GPT 5.2 vs Claude Opus 4.5 - Which AI Model Is Truly Better?"

[12]: https://reddit.com/r/ClaudeAI/comments/1qu7vyj/ "r/ClaudeAI: Codex vs Claude Code - 5 days running in parallel (175 upvotes)"

[13]: https://www.klavis.ai/blog/claude-opus-4-5-vs-gemini-3-pro-vs-gpt-5-the-ultimate-agentic-ai-showdown-for-developers "Klavis: Ultimate Agentic AI Showdown for Developers"

[15]: https://reddit.com/r/ClaudeAI/comments/1qhasdf/ "r/ClaudeAI: Claude Opus 4.5 vs GPT 5.2 High vs Gemini 3 in production"

[16]: https://reddit.com/r/Bard/comments/1qe6dir/ "r/Bard: Gemini 2.5 pro actually better than 3.0 (129 upvotes)"

[18]: https://www.keywordsai.co/blog/fast-model-comparison "Keywords AI: GPT-5 mini vs Gemini 3 Flash vs Claude 4.5 Haiku"

[19]: https://claudelog.com/faqs/claude-4-sonnet-vs-opus/ "ClaudeLog: Claude Sonnet 4.5 vs Opus for Claude Code"

[20]: https://docsbot.ai/models/compare/gemini-3-flash/claude-haiku-4-5 "DocsBot: Gemini 3 Flash vs Claude Haiku 4.5 comparison"

[21]: https://www.financialcontent.com/article/tokenring-2026-1-21-gemini-3-flash-redefines-the-developer-experience-with-terminal-native-ai-and-real-time-pr-automation "Gemini 3 Flash: Terminal-Native AI and Real-Time PR Automation"

[22]: https://x.ai/news/grok-code-fast-1 "xAI: Grok Code Fast 1 announcement"

[24]: https://dev.to/dr_furqanullah_8819ecd9/github-copilot-model-context-sizes-nov-2025-3nif "GitHub Copilot Model Context Sizes (Nov 2025)"

[25]: https://www.anthropic.com/news/claude-opus-4-6 "Anthropic: Claude Opus 4.6 announcement"

[26]: https://openai.com/index/introducing-gpt-5-3-codex/ "OpenAI: Introducing GPT-5.3-Codex"
