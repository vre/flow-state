# Designing Initial Project Setup: Good Practices (2026)

This document outlines the workflow for setting up new projects optimized for LLM-assisted development.

---

# Part I: The Strategy (Why)

## 1. The Setup Tax

Every project has a setup cost. For LLM-assisted development, poor setup compounds:
- **Wasted tokens:** LLM debugging environment issues instead of building features.
- **Inconsistent quality:** No linting means LLM wastes tokens on formatting.
- **Slow feedback:** No tests means bugs surface late, requiring expensive context rebuilds.

**Goal:** Front-load deterministic infrastructure so LLM work stays in the creative/analytical domain [6].

## 2. Deterministic vs. Probabilistic Work

| Work Type | Examples | Who Does It |
| :--- | :--- | :--- |
| **Deterministic** | Formatting, linting, type checking | Tools (linters, formatters) |
| **Probabilistic** | Architecture, logic, problem-solving | LLM |

**Principle:** Never send an LLM to do a linter's job. Configure tools for deterministic work upfront.

## 3. The SDD Debate (Meta-Discussion)

Spec-Driven Development (SDD) emerged in 2025 as a response to chaotic "vibe coding." Tools like Kiro, Spec-kit, and BMAD promised structure: write detailed specs → generate implementation → verify against spec.

**The criticism is substantial:**

> "SDD produces too much text. Developers spend most of their time reading long Markdown files, hunting for basic mistakes hidden in overly verbose, expert-sounding prose." — [Marmelab: The Waterfall Strikes Back](https://marmelab.com/blog/2025/11/12/spec-driven-development-waterfall-strikes-back.html)

> "Spec-driven development for AI is a form of technical masturbation... I burned a massive amount of tokens doing it! Context drift and pollution. The LLMs are not that smart." — [Reddit r/ChatGPTCoding](https://www.reddit.com/r/ChatGPTCoding/comments/1o6j1yr/) (59 upvotes)

> "Code is deterministic, specs are not. Specs are always open for interpretation. Me, you, your dog and your AI assistant will all interpret them differently."

> "Kiro was way too verbose for the small bug... the workflow was like using a sledgehammer to crack a nut." — [Martin Fowler's SDD analysis](https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html)

**The alternative gaining traction: RPI (Research → Plan → Implement)**

> "AVOID THE 'DUMB ZONE.' That's the last ~60% of a context window. Once the model is in it, it gets stupid. Stop arguing with it. NUKE the chat and start over." — [Reddit r/ClaudeAI](https://www.reddit.com/r/ClaudeAI/comments/1pkvque/) (188 upvotes)

| Approach | Tokens | Flexibility | When to Use |
| :--- | :--- | :--- | :--- |
| **Full SDD** | High (verbose specs) | Low (rigid) | Compliance, audit trails |
| **RPI** | Medium (lightweight plans) | Medium | Most projects |
| **Tests as Spec** | Low | High | Iterative development |

**This document advocates Tests as Spec:** Define acceptance criteria, let LLM implement, verify with tests. The test is the spec. The conversation is the design doc.

**When SDD might work:** Greenfield projects with clear bounded scope, team alignment needs, or regulatory compliance. But for most work, it's overkill [7].

---

# Part II: The Architecture (What)

## 4. The Setup Sequence

```
AGENTS.md → Tool Discovery → Hello World → Implement
```

### 4.1 Phase 1: AGENTS.md

Create behavioral configuration first. This anchors all subsequent LLM interactions.

```markdown
# AGENTS.md (minimal starter)

You are an expert engineer building [project type].

## Rules
- NO CODE before tests
- Use [language] with [framework]
- Run tests before every commit

## Tech Stack
- Language: [X]
- Test framework: [Y]
- Linter: [Z]
```

See *Designing AGENTS.md.md* for full guidance.

### 4.2 Phase 2: Project Scaffolding

Establish conventional structure before writing code. LLMs are trained on millions of repos—familiar layouts reduce explanation overhead [21].

**Start with large-codebase conventions even for small projects.** See §10 for full guidance. The cost of good structure on day 1 is zero; the cost of retrofitting later is massive. Projects that succeed often grow.

**Root directory files:**
```
README.md           # What this is, how to use it
ARCHITECTURE.md     # System design, tech stack, key decisions
CHANGELOG.md        # What changed, when (keep in sync)
DEVELOPMENT.md      # How to set up dev environment
TESTING.md          # How to run tests, what to test
LICENSE             # Legal terms
.gitignore          # What to exclude from git
```

**ARCHITECTURE.md is critical.** When LLMs "forget" past decisions, they revert code to old patterns. Document architectural decisions so new sessions can read them [8].

**Directory structure:**
```
project/
├── src/            # Source code (or lib/, pkg/, app/)
├── tests/          # All tests
│   ├── unit/
│   └── integration/
├── docs/           # Documentation, plans, research
│   └── decisions/  # Architectural decision records
├── scripts/        # Build/deploy/utility scripts
└── [config files]  # pyproject.toml, package.json, etc.
```

**Decision documentation pattern:** After any architectural change (auth flow, API design, data model), update `docs/decisions/` or the relevant .md file. Write it so a new LLM session can follow what was done [8]:

```
docs/decisions/
├── auth-flow.md        # "We use Google OAuth, not API keys"
├── data-model.md       # Entity relationships
└── api-design.md       # REST conventions used
```

**Principles:**
- **Minimal root clutter.** Config files are unavoidable, but code belongs in subdirectories.
- **Predictable locations.** 'tests/' not 'test/' or 'spec/'. 'docs/' not 'documentation/'.
- **Separation of concerns.** Source, tests, docs, scripts—each has a home.

**Language conventions:**

| Language | Source Dir | Config File |
| :--- | :--- | :--- |
| Python | 'src/' or package name | 'pyproject.toml' |
| TypeScript | 'src/' | 'package.json', 'tsconfig.json' |
| Go | root or 'cmd/', 'internal/' | 'go.mod' |
| Rust | 'src/' | 'Cargo.toml' |

### 4.3 Phase 3: Tool Discovery

Brainstorm with LLM about suitable tools for your project:

**Prompt pattern:**
```
I'm building [project description].
Requirements: [list key requirements]
Constraints: [language, platform, team size]

What tools would you recommend for:
1. Testing (unit, integration, e2e)
2. Linting and formatting
3. Build/dependency management
4. CI/CD
```

**Plugins can accelerate this.** MCP servers for package registries, documentation, or code search provide context the LLM lacks post-training.

**Output:** Tool selection documented in AGENTS.md or project README.

### 4.4 Phase 4: Initial Functionality Map

Before code, sketch the terrain:

```
Core entities: User, Order, Product
Key flows: checkout, inventory_update
External integrations: payment_api, shipping_api
```

This isn't a spec—it's orientation. Helps LLM understand scope without over-engineering.

### 4.5 Phase 5: Hello World Implementation

The hello world isn't about functionality—it's about infrastructure validation.

**Must establish:**

**A) Testing Framework**
```
tests/
├── unit/           # Fast, isolated
├── integration/    # Component boundaries
└── e2e/            # Full system (sparingly)
```

**The Test Triangle [5]:**
- **Unit (70%):** Pure functions, fast, many.
- **Integration (20%):** Component interactions, medium speed.
- **E2E (10%):** Full workflows, slow, few.

**B) Linting & Formatting**
- Configure once, run automatically.
- Pre-commit hooks enforce consistency.
- LLM never touches formatting—tools handle it.

**Validation:** Hello world passes lint, has one test per level, CI runs green.

---

# Part III: Operations (How)

## 5. The Checklist

### 5.1 Before First Feature

- [ ] AGENTS.md exists with tech stack and rules
- [ ] Testing framework configured (unit + integration at minimum)
- [ ] Linter configured and passing
- [ ] Formatter configured (auto-fix on save or pre-commit)
- [ ] CI pipeline runs tests and lint
- [ ] Hello world implementation proves stack works

### 5.2 Tool Recommendations by Language

| Language | Test Framework | Linter | Formatter |
| :--- | :--- | :--- | :--- |
| Python | pytest | ruff | ruff format |
| TypeScript | vitest / jest | eslint | prettier |
| Go | go test | golangci-lint | gofmt |
| Rust | cargo test | clippy | rustfmt |

**Package management:**
- Python: `uv` (fast, reliable)
- Node: `pnpm` or `npm`
- Go: go modules
- Rust: cargo

### 5.3 CI Minimum

```yaml
# .github/workflows/ci.yml (example)
on: [push, pull_request]
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Lint
        run: make lint
      - name: Test
        run: make test
```

## 6. Context Management

LLM performance degrades as context fills. Practitioners report a "dumb zone" threshold [9].

**The 40-60% Rule:**
- At 40% context: model starts missing details
- At 60% context: model gets "stupid"—stop arguing, nuke the chat
- Check with `/context` command in Claude Code

**Tactics:**
- Single-purpose conversations—one feature per session
- Subagents for context isolation, not role-play [9]
- After compaction: confirm task state before resuming

**Freeze Working Features:**
> "Your biggest enemy is not bugs. It's mutation. AI preserves output, not intent." — [Reddit r/cursor](https://www.reddit.com/r/cursor/comments/1qaz5mw/) (121 upvotes)

Rule: **working + users happy = frozen.** New ideas go into a separate branch, never into live logic. Don't re-prompt features that already work.

## 7. Common Pitfalls

- **❌ Skipping tests "to move fast."** You'll move slower. LLM needs test feedback to iterate.
- **❌ No linter.** LLM spends tokens on formatting instead of logic.
- **❌ Over-specifying upfront.** You're not writing a spec—you're having a conversation.
- **❌ Complex architecture before hello world.** Prove the stack works first.
- **❌ Manual formatting reviews.** Automate. Never discuss tabs vs spaces with an LLM.
- **❌ Skipping AGENTS.md.** LLM defaults to generic patterns. Your project has specific needs.
- **❌ No decision documentation.** LLM "forgets" past sessions. Document architectural choices in .md files so new sessions can read them [8].
- **❌ Re-prompting working features.** Mutation breaks things. Freeze what works.
- **❌ Offloading all cognition.** "You are not a programmer, you are a product manager" [10]. You own the decisions; LLM executes.

## 8. After Setup: The Development Loop

```
1. Define acceptance criteria (in conversation or plan)
2. Write failing test (TDD)
3. LLM implements
4. Tests pass
5. Lint/format (automatic)
6. Commit
7. Repeat
```

No separate spec phase. The test is the spec. The conversation is the design doc.

## 9. Scaling: Parallel Sessions

For larger projects, run multiple LLM sessions in parallel on separate features.

**Boris's approach (Claude Code creator):** 5 separate git checkouts of the same repo, each with its own Claude session [11]. Not worktrees—full checkouts for complete isolation.

```bash
# Setup parallel workspaces
git clone myrepo myrepo-feature-a
git clone myrepo myrepo-feature-b
git clone myrepo myrepo-feature-c
```

**Why this works:**
- Each session has clean context (no pollution from other features)
- Merge conflicts resolved at git level, not LLM level
- Can use different models for different task types

**Caveat:** Boris has unlimited tokens. For token-constrained users, use worktrees and shorter sessions instead.

## 10. Large Codebase Navigation

When code exceeds context size, structure becomes the LLM's map. Good conventions let the model pinpoint locations without re-analyzing everything [19].

**Establish these conventions from day one.** Retrofitting structure is expensive—you're refactoring while the LLM struggles to understand the old layout. Starting clean costs nothing; migrating later costs everything.

### 10.1 File-Level Conventions

**Size limits:**
- Target <300 lines per file (fits comfortably in context with room for conversation)
- Split when file serves multiple purposes
- Exception: generated code, data files

**Single responsibility:**
- One reason to change per file
- 'user_auth.py' not 'user_utils.py' (what's in "utils"?)
- If explaining what's in a file requires "and", split it

**Predictable naming:**
```
# Good: LLM can guess file location from task description
src/
├── auth/
│   ├── login.py           # Login flow
│   ├── logout.py          # Logout flow
│   ├── oauth_google.py    # Google OAuth specifics
│   └── session.py         # Session management
├── users/
│   ├── create.py
│   ├── delete.py
│   └── profile.py

# Bad: LLM must read files to understand contents
src/
├── utils.py               # What's in here?
├── helpers.py             # How is this different from utils?
├── common.py              # ???
└── misc.py                # The junk drawer
```

**Verb-noun patterns:**
- Actions: 'create_user.py', 'send_email.py', 'validate_input.py'
- Entities: 'user.py', 'order.py', 'product.py'
- Avoid: 'user_stuff.py', 'order_helpers.py'

### 10.2 Directory-Level Conventions

**README.md per directory:**
```
src/payments/README.md:
# Payments Module

Handles all payment processing. Stripe integration.

## Files
- checkout.py - Cart to payment flow
- refund.py - Refund processing
- webhooks.py - Stripe webhook handlers

## Key decisions
- All amounts in cents (integer)
- Idempotency keys required for all mutations
```

LLM reads this first, knows where to look.

**Flat over deep:**
```
# Good: 2-3 levels max
src/auth/login.py
src/auth/oauth/google.py

# Bad: archaeology required
src/modules/core/auth/providers/oauth/implementations/google/handler.py
```

**Feature-based over layer-based:**
```
# Good: related code together
features/
├── checkout/
│   ├── checkout_handler.py
│   ├── checkout_test.py
│   └── checkout_types.py
├── inventory/
│   └── ...

# Problematic for LLMs: feature scattered across layers
controllers/checkout_controller.py
services/checkout_service.py
repositories/checkout_repository.py
models/checkout_model.py
tests/checkout_test.py
```

### 10.3 Code-Level Conventions

**Type definitions in dedicated files:**
```
src/users/
├── types.py          # User, UserCreate, UserUpdate
├── create.py         # from .types import UserCreate
└── repository.py     # from .types import User
```

LLM can read 'types.py' to understand data shapes without reading implementation.

**Barrel/index files for modules:**
```python
# src/auth/__init__.py
from .login import login_user
from .logout import logout_user
from .session import create_session, destroy_session

__all__ = ["login_user", "logout_user", "create_session", "destroy_session"]
```

LLM sees module's public API at a glance.

**Consistent patterns everywhere:**
- If handlers are in `handle_*.py`, all handlers follow this
- If tests are `*_test.py`, no exceptions
- Pattern breaks force the LLM to re-analyze

### 10.4 Navigation Aids

**ARCHITECTURE.md with module map:**
```markdown
## Module Overview

| Module | Purpose | Key Files |
|:---|:---|:---|
| auth/ | Authentication, sessions | login.py, session.py |
| users/ | User CRUD, profiles | create.py, profile.py |
| payments/ | Stripe integration | checkout.py, webhooks.py |
```

**Consistent cross-references:**
```python
# At top of complex files
"""
Checkout handler.

Related:
- src/payments/stripe_client.py - Stripe API wrapper
- src/cart/cart.py - Cart operations
- docs/decisions/payment-flow.md - Architecture decision
"""
```

**Search-friendly comments:**
```python
# DECISION: Using cents for all amounts (see docs/decisions/money.md)
# TODO(auth): Add rate limiting
# FIXME: Race condition when concurrent updates
```

### 10.5 The Navigation Checklist

- [ ] Files under 300 lines
- [ ] One responsibility per file
- [ ] Names describe contents (no 'utils.py')
- [ ] README.md in each major directory
- [ ] Max 3 directory levels
- [ ] Types in dedicated files
- [ ] Barrel files for module APIs
- [ ] ARCHITECTURE.md with module map
- [ ] Consistent patterns (no exceptions)

### 10.6 Enterprise Scale: Advanced Tooling

At enterprise scale (500k+ LOC), even good structure isn't enough. Additional tooling helps:

| Tool | Purpose | Works Better With |
| :--- | :--- | :--- |
| **RAG (Retrieval)** | Find relevant code chunks | Clean file boundaries, good naming |
| **Semantic search** | Natural language queries | Descriptive names, docstrings |
| **Code graph DBs** | Dependency analysis | Clear module boundaries |
| **Embeddings** | Similarity search | Consistent patterns |
| **AST indexing** | Structure-aware search | Single-responsibility files |

**These tools amplify good structure—they don't fix bad structure.**

A RAG system searching 'utils.py' (2000 lines, 47 functions) retrieves noise. The same system searching 'auth/login.py' (80 lines, login flow only) retrieves signal.

Semantic search on `process_data()` returns garbage. On `validate_user_email()` returns exactly what you need.

**The investment sequence:**
1. **Day 1:** Establish conventions (this section) — free
2. **Growth:** Maintain conventions as you scale — discipline
3. **Enterprise:** Add RAG/search tooling — the conventions make it work

Skipping to step 3 with bad structure gives you expensive tools that return garbage.

### 10.7 Research: What Actually Works at Scale

**Measured impact of AGENTS.md files** [17]:
- 28.64% faster execution (median wall-clock time)
- 16.58% fewer output tokens
- "Agents require fewer planning iterations and less exploratory navigation when provided with structured guidance"

**The "context rot" problem** [18]:
> "Even though modern LLMs have million-token context windows, their performance actually degrades with longer inputs. Simply feeding more code doesn't improve understanding—it can make it worse."

Smart tooling elevates from file-level to architectural-level understanding.

**Enterprise tool context windows** [19]:

| Tool | Context | Approach |
| :--- | :--- | :--- |
| GitHub Copilot | 64k chat / 8k completion | Neighboring tabs, @workspace |
| Sourcegraph Cody | ~100k lines fed | Vector embeddings, on-prem |
| Augment Code | 200k tokens | Indexes 400-500k files at once |
| Cursor | Large (RAG-based) | Semantic chunking, shadow workspace |

**For codebases over 500k LOC:**
- Augment: "Change this function and it knows which others might break" [19]
- Cody: "Semantic search and navigation across massive repositories" [19]
- Claude Code: Grep-based (no RAG), relies on good structure [20]

**GitHub's findings from 2,500+ repositories** [21]:
> "Hitting six core areas puts you in the top tier: commands, testing, project structure, code style, git workflow, and boundaries."

Most effective constraint across all repos: "Never commit secrets."

**The 80-90% rule** [19]:
> "For large codebases (100K+ lines), developers spend 80-90% of their time reading existing code, not writing new code."

Good structure reduces that reading time for both humans and LLMs.

### 10.8 Monorepo-Specific Guidance

For million-line monorepos, add to CLAUDE.md/AGENTS.md [22]:

```markdown
## Subsystem Map
| Path | Purpose | Owner |
|:---|:---|:---|
| api/ | REST endpoints | backend-team |
| web/ | React frontend | frontend-team |
| services/ | Background jobs | platform-team |
| shared/ | Common utilities | all |

## Dependency Edges
- web/ → api/ (via REST)
- services/ → shared/db
- api/ → shared/auth

## Hotspots (Often Break)
- shared/auth/session.py - Touch carefully
- api/v2/migration.py - Legacy compatibility
```

**Why this works:** LLM reads the map, navigates to relevant subsystem, avoids wandering through unrelated code.

**Hybrid retrieval pattern** [23]:
> "Use Claude Code for orchestration but have it call Gemini CLI with the 1M context for gathering information about large parts of the codebase."

Combine small-context precision with large-context exploration.

---

# Part IV: Reference

## 11. Project Templates

Consider starting from proven templates rather than blank slate:
- **Python:** `uv init` + pytest + ruff
- **TypeScript:** `npm create vite@latest` + vitest + eslint
- **Go:** `go mod init` + standard library testing

## 12. References

**Internal:**
- [1] [Designing AGENTS.md.md](Designing%20AGENTS.md.md) - Behavioral configuration
- [2] [Designing Skills.md](Designing%20Skills.md) - On-demand instructions
- [3] [Designing MCP Servers.md](Designing%20MCP%20Servers.md) - Tool integration
- [4] [Designing CLI Tools.md](Designing%20CLI%20Tools.md) - Script patterns
- [24] [Designing Hooks.md](Designing%20Hooks.md) - Lifecycle hooks for security, quality

**External:**
- [5] Martin Fowler: [Test Pyramid](https://martinfowler.com/articles/practical-test-pyramid.html)
- [6] Anthropic (2025): [Building Effective Agents](https://www.anthropic.com/research/building-effective-agents)
- [7] Marmelab (2025): [Spec-Driven Development: The Waterfall Strikes Back](https://marmelab.com/blog/2025/11/12/spec-driven-development-waterfall-strikes-back.html) - SDD criticism
- [8] Reddit r/cursor: [Does vibe coding hit a wall once your project gets big?](https://www.reddit.com/r/cursor/comments/1q1v99l/) (847 upvotes) - Decision documentation pattern
- [9] Reddit r/ClaudeAI: [SDD vs RPI using Claude](https://www.reddit.com/r/ClaudeAI/comments/1pkvque/) (188 upvotes) - The 60% rule, subagents for context
- [10] Reddit r/cursor: [Vibe coding wall comment](https://www.reddit.com/r/cursor/comments/1q1v99l/does_vibe_coding_hit_a_massive_wall_once_your/nx9cdhi/) - "You are a product manager"
- [11] Reddit r/ClaudeAI: [Boris's setup](https://www.reddit.com/r/ClaudeAI/comments/1q2c0ne/) (2876 upvotes) - Parallel git checkouts
- [12] Reddit r/ChatGPTCoding: [SDD criticism](https://www.reddit.com/r/ChatGPTCoding/comments/1o6j1yr/) (59 upvotes) - "Technical masturbation"
- [13] Reddit r/cursor: [Production SaaS guide](https://www.reddit.com/r/cursor/comments/1qaz5mw/) (121 upvotes) - Freeze working features
- [14] Martin Fowler: [Understanding SDD Tools](https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html) - Kiro verbosity
- [15] Addy Osmani (2025): [My LLM coding workflow going into 2026](https://addyosmani.com/blog/ai-coding-workflow/) - Context packing
- [16] Thoughtworks (2025): [Spec-driven development](https://www.thoughtworks.com/en-us/insights/blog/agile-engineering-practices/spec-driven-development-unpacking-2025-new-engineering-practices) - SDD sits above TDD/BDD
- [17] arXiv (2026): [On the Impact of AGENTS.md Files on AI Coding Agent Efficiency](https://arxiv.org/html/2601.20404) - 28.64% faster, 16.58% fewer tokens
- [18] Qodo (2025): [Evaluating RAG for large-scale codebases](https://www.qodo.ai/blog/evaluating-rag-for-large-scale-codebases/) - Context rot problem
- [19] IntuitionLabs (2025): [AI Code Assistants for Large Codebases](https://intuitionlabs.ai/articles/ai-code-assistants-large-codebases) - Enterprise tool comparison
- [20] Milvus (2025): [Why I'm Against Claude Code's Grep-Only Retrieval](https://milvus.io/blog/why-im-against-claude-codes-grep-only-retrieval-it-just-burns-too-many-tokens.md) - Semantic vs grep search
- [21] GitHub Blog (2025): [How to write a great agents.md](https://github.blog/ai-and-ml/github-copilot/how-to-write-a-great-agents-md-lessons-from-over-2500-repositories/) - Six core areas from 2500+ repos
- [22] Skywork (2025): [Claude Code Plugin Best Practices for Large Codebases](https://skywork.ai/blog/claude-code-plugin-best-practices-large-codebases-2025/) - Monorepo mapping
- [23] Reddit r/ChatGPTCoding: [Gemini CLI as Claude's context gatherer](https://www.reddit.com/r/ChatGPTCoding/comments/1lm3fxq/) (1179 upvotes) - Hybrid retrieval pattern
