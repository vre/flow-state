# DONE: Token Usage Optimization

## Problem

youtube-to-markdown skill cost **$3.77 per video** with Opus orchestrator and 7 subagents. Goal: optimize price/quality ratio for different use cases (AI/RAG vs. human-readable).

## Hypotheses

1. **Sonnet suffices as orchestrator** - Opus is overkill for orchestration coordination tasks
2. **Polish steps unnecessary for AI consumption** - Steps 4 (paragraph breaks), 7 (clean artifacts), 8 (topic headings) improve readability but not AI interpretation
3. **Combining steps reduces overhead** - Subagent calls bring fixed token cost

## Test Design

Tested 5 configurations on the same video ("The Assassin's Teapot Is Weird", jJL0XoNBaac):

| # | Configuration | Model | Subagents | Steps |
|---|---------------|-------|-----------|-------|
| 01 | full-opus | Opus | 7 | All (4,5,6,7,8,10a,10b) |
| 02 | full-sonnet | Sonnet | 7 | All |
| 03 | no-polish | Sonnet | 3 | 5,6,10b (no 4,7,8) |
| 04 | combined | Sonnet | 5 | Combined workflows |
| 05 | lite | Sonnet | 2 | 5+6 combined, 10a+10b combined |

## Results

### Cost Comparison

| Configuration | Cost | Savings | Duration | Subagents |
|---------------|------|---------|----------|-----------|
| 01-full-opus | **$3.77** | baseline | 521s | 7 |
| 02-full-sonnet | **$1.11** | -70% | 477s | 7 |
| 03-no-polish | **$0.60** | -46%* | 225s | 3 |
| 04-combined | **$0.89** | -20%* | 380s | 5 |
| 05-lite | **$0.52** | -53%* | 237s | 2 |

*) Savings relative to 02-full-sonnet

### Detailed Analysis

**01-full-opus ($3.77):**
```
Orchestration (opus):     $2.68 (71%)
Subagents total:          $1.09 (29%)
  Step 4: Paragraph       $0.19
  Step 5: Summarize       $0.14
  Step 6: Tighten         $0.13
  Step 7: Clean           $0.09
  Step 8: Headings        $0.18
  Step 10a: Extract       $0.22
  Step 10b: Analyze       $0.15
```

**02-full-sonnet ($1.11):**
```
Orchestration (sonnet):   $0.53 (48%)
Subagents total:          $0.58 (52%)
  Step 4: Paragraph       $0.12
  Step 5: Summarize       $0.07
  Step 6: Tighten         $0.07
  Step 7: Clean           $0.03
  Step 8: Headings        $0.10
  Step 10a: Extract       $0.13
  Step 10b: Analyze       $0.07
```

**03-no-polish ($0.60):**
```
Orchestration (sonnet):   $0.31 (52%)
Subagents total:          $0.29 (48%)
  Step 5: Summarize       $0.12
  Step 6: Tighten         $0.05
  Step 10b: Analyze       $0.12
```

**05-lite ($0.52):**
```
Orchestration (sonnet):   $0.24 (46%)
Subagents total:          $0.28 (54%)
  Step 5: Combined        $0.11
  Step 10: Combined       $0.17
```

### Cache Efficiency

| Configuration | Cache Read | Cache Saved |
|---------------|------------|-------------|
| 01-full-opus | 1.6M tokens | $18.45 |
| 02-full-sonnet | 1.7M tokens | $4.42 |
| 05-lite | 724K tokens | $1.96 |

## Conclusions

### Validated Hypotheses

1. **Sonnet suffices as orchestrator**: -70% cost ($3.77 -> $1.11), same quality
2. **Polish steps unnecessary for AI**: -46% additional savings ($1.11 -> $0.60)
3. **Combining saves**: -53% overall ($1.11 -> $0.52)

### Observations

- **Orchestration dominates**: 46-71% of total cost
- **TodoWrite calls**: 18 in full version vs. 8 in lite version
- **Caching critical**: Saves up to 94% of token "list price"

### Qualitative Comparison

Evaluated against `summary_formats.md` criteria (EDUCATIONAL format: TL;DR + What/Why/How/What Then structure, Hidden Gems, Comment Insights).

| Criterion | 01-opus | 02-sonnet | 03-no-polish | 04-combined | 05-lite |
|-----------|---------|-----------|--------------|-------------|---------|
| TL;DR | ✅ Excellent | ✅ Good | ✅ Good | ✅ Good | ✅ Good |
| What/Why/How | ✅ Complete | ✅ Complete | ✅ Complete | ✅ Complete | ✅ Complete |
| What Then | ❌ Missing | ✅ Present | ❌ Missing | ✅ Present | ✅ Present |
| Hidden Gems | ✅ 2 items | ❌ Missing | ✅ Present | ❌ Missing | ✅ Present |
| Comment depth | ✅ Excellent | ✅ Good | ⚠️ Basic | ✅ Good | ⚠️ Basic |
| Categorization | ✅ Rich | ✅ Structured | ⚠️ Flat | ✅ Subheadings | ⚠️ Flat |
| Size (bytes) | 2900 | 2400 | 1800 | 2500 | 2200 |

**Detailed observations:**

**01-full-opus** ($3.77): Most detailed comment analysis with rich categorization (EDUCATIONAL label, Corrections/Extensions, Debates, Safety Protocol, Modern Applications, Usage Concerns, Cultural References, Educational Impact, Design Improvements, Fiction Use). Best structure but missing "What Then" in main section.

**02-full-sonnet** ($1.11): Well-balanced with complete EDUCATIONAL structure including What Then. Good comment categorization but fewer subcategories than Opus. Missing Hidden Gems section.

**03-no-polish** ($0.60): Follows format correctly with Hidden Gems. Comment Insights lack subcategorization - single-level list structure. Adequate for information extraction but less scannable.

**04-combined** ($0.89): Adds separate "Physics Principle" section beyond standard format. Comment Insights use ### subheadings for clear categorization. Missing Hidden Gems.

**05-lite** ($0.52): Structurally follows format with Hidden Gems present. However, explanations are shallower - more mechanical than insightful. Comment section lacks the depth and attribution quality of full versions. The What/Why/How fills the template but lacks the analytical depth of higher-cost versions.

**Key finding**: Lite version appears structurally compliant but lacks analytical depth. The TL;DR and structure look correct, but the actual content quality - nuance, explanation depth, comment attribution - is noticeably weaker. Cost savings come from reduced reasoning, not just formatting steps.

## Recommendations

| Use Case | Variant | Cost | Rationale |
|----------|---------|------|-----------|
| Production | **full-sonnet** | $1.11 | Best price/quality - complete structure with good analytical depth |
| Budget-conscious | no-polish | $0.60 | Adequate structure, acceptable depth, skips formatting polish |
| ~~Bulk processing~~ | ~~lite~~ | ~~$0.52~~ | ~~Removed - shallow analysis despite correct structure~~ |

## Outcome

Lite variant was removed from production (commit 3f4c64d). Qualitative review revealed that while lite outputs appeared structurally compliant, they lacked analytical depth - explanations were mechanical rather than insightful, and comment analysis was superficial. The cost savings came from reduced reasoning quality, not just skipped formatting steps.

Production uses full-sonnet configuration ($1.11/video) which provides complete structure with good analytical depth.

## Files

| File | Purpose |
|------|---------|
| `research/.../code/full/SKILL.md` | 7 subagent baseline |
| `research/.../code/lite/SKILL.md` | 2 subagent optimized |
| `research/.../code/no-polish/SKILL.md` | 3 subagent, no polish |
| `research/.../code/combined/SKILL.md` | 5 subagent, combined |
| `research/.../tools/analyze_run.py` | Token analysis |
| `research/.../runs/*/analysis.txt` | Test result reports |
