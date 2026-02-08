# Research: Project Initialization Tools - Competitor Analysis

## Overview

Research into existing tools for creating skills, MCP servers, and CLI tools. Findings inform what to adopt, avoid, and improve upon in our `project-init` skill.

---

## 1. Skill Creators

### anthropics/skills (Official)
- **URL**: https://github.com/anthropics/skills
- **Stars**: Official reference
- **Structure**:
  - `/skills/` - Examples across Creative, Development, Enterprise
  - `/spec/` - Agent Skills specification
  - `/template/` - Reusable template
- **Key patterns**:
  - SKILL.md + YAML frontmatter (minimal: `name` + `description`)
  - Supports prompt-only and code-backed implementations
  - Apache 2.0 for examples, source-available for production (docx, pdf, pptx, xlsx)

### FrancyJGLisboa/agent-skill-creator (~250 stars)
- **URL**: https://github.com/FrancyJGLisboa/agent-skill-creator
- **What**: Meta-skill that teaches Claude to create skills
- **Workflow**: Discovery → Design → Architecture → Detection → Implementation → Testing (6 phases)
- **Claims**: 94-97% time reduction, 1000%+ ROI
- **Pattern**: `-cskill` suffix for generated skills
- **Concern**: Heavy process, potentially over-engineered

### alirezarezvani/claude-code-skill-factory (~100+ stars)
- **URL**: https://github.com/alirezarezvani/claude-code-skill-factory
- **What**: Production toolkit for skills, agents, commands, prompts
- **Structure**:
  - `.claude/` - 5 interactive guides + 8 slash commands
  - `generated-skills/` - 9 production examples
  - `generated-agents/` - Specialized agents
- **Generation**: Interactive Q&A (4-7 questions) → Validation → ZIP
- **Four templates**: Skills Factory, Agents Factory, Prompt Factory (69 presets), Hooks Factory

---

## 2. MCP Server Generators

### codingthefuturewithai/mcp-cookie-cutter (Most comprehensive)
- **URL**: https://github.com/codingthefuturewithai/mcp-cookie-cutter
- **What**: Cookiecutter template with multi-transport + management UI
- **Generated structure**:
  ```
  server/          # Multi-transport (stdio, SSE, streamable HTTP)
  tools/           # Tool implementations
  decorators/      # Auto-handlers (logging, exceptions, parallelization)
  log_system/      # SQLite logging with correlation IDs
  ui/              # Streamlit management interface
  client/          # Dev test client
  tests/           # Comprehensive suite
  ```
- **DevFlow**: JIRA workflow commands integrated
- **Concern**: Over-engineered for simple servers (Streamlit UI, SQLite logging)

### @mcpdotdirect/create-mcp-server (TypeScript)
- **Command**: `npx @mcpdotdirect/create-mcp-server`
- **Generated**:
  - `.devcontainer/` - Dev container
  - `src/index.ts` - Entry point
  - `src/examples/` - Example tools
- **Features**: Multi-transport, auto-reload, FastMCP integration
- **Runtime**: Bun default (modifiable to Node.js)

### shubhamgupta-dat/mcp-server-template
- **What**: Straightforward Cookiecutter
- **Structure**: Main module, tools/, resources/, prompts/
- **Implements**: All three MCP primitives (Tools, Resources, Prompts)
- **Tools**: uv, pytest, black, isort, mypy, Docker

### Canonical MCP Structure (consensus)
```
mcp-server/
├── src/
│   ├── server.py       # Server initialization
│   ├── tools/          # Tool implementations
│   ├── resources/      # Resource handlers
│   └── schemas/        # Data validation
├── tests/
├── pyproject.toml
├── .mcp.json           # Local dev config
├── Dockerfile
└── README.md
```

### Python Dependencies (consensus)
```toml
dependencies = [
    "mcp >= 1.0.0",
    "pydantic >= 2.0.0",
    "python-dotenv >= 1.0.0",  # Optional
]
```

---

## 3. CLI Generators

### PyTemplate/typer_cli (~400+ stars)
- **URL**: https://github.com/PyTemplate/typer_cli
- **What**: Production-ready Typer CLI template
- **Structure**:
  ```
  src/pytemplates_typer_cli/
  ├── core/         # Business logic (separate from CLI)
  ├── main.py       # CLI entry
  tests/
  ```
- **Testing**: pytest, pytest-cov, mypy
- **CI**: Automatic codecov on commits/PRs
- **Pre-commit**: Linting/formatting hooks

### cookiecutter-uv (Modern Python)
- **URL**: https://github.com/fpgmaas/cookiecutter-uv
- **What**: Modern template using `uv`
- **Features**:
  - src/ and flat layout support
  - GitHub Actions pre-configured
  - ruff, mypy, deptry
  - `uv.lock` for reproducibility
  - MkDocs, Docker, VSCode devcontainers

---

## 4. Templating Tools

### Cookiecutter (~13k stars)
- **What**: Foundation tool for project templates
- **Pattern**: Jinja2 + `cookiecutter.json` prompts
- **Hooks**: Pre-prompt, pre-generate, post-generate
- **Limitation**: No template updates after generation

### Copier (Alternative)
- **Advantages over Cookiecutter**:
  - **Template updates**: Built-in project updates when templates evolve
  - **YAML config**: Single `copier.yml` vs JSON
  - **Lifecycle management**: Handles migrations
  - **Smart preservation**: Won't overwrite unless instructed
- **Use case**: Better for evolving templates

---

## 5. Key Patterns Observed

### Generation Approaches

| Approach | Example | Pros | Cons |
|----------|---------|------|------|
| Static template + JSON | Cookiecutter | Simple, one-time | No updates |
| Template + lifecycle | Copier | Updates over time | More complex |
| Interactive Q&A | Skill Factory | User-friendly | LLM token cost |
| Script-based | Our approach | Minimal, testable | Less interactive |

### Common Structure Patterns
- **Modular separation**: Business logic separate from orchestration
- **Pre-commit hooks**: Quality gates before commits
- **CI/CD built-in**: GitHub Actions, codecov
- **Testing infrastructure**: pytest, mypy, coverage
- **Dev environment**: uv or poetry for reproducibility

### MCP Best Practices (consensus)
1. One clear purpose per server
2. Layered architecture (tools/, resources/, middleware/)
3. Type safety throughout
4. Environment scoping (no shared secrets)
5. Fail-fast validation
6. Structured logging with correlation IDs
7. In-memory testing (avoid subprocess overhead)
8. Container-ready (Dockerfile included)

---

## 6. Analysis: What We Should Do

### ✅ Already in Our Plan (Validated)
- **Script-based generation** - Aligns with "minimize skill, maximize script"
- **pytest setup** - Universal consensus
- **ruff linting** - Modern choice over black+isort
- **pyproject.toml with hatchling** - Standard
- **Single-tool dispatcher for MCP** - Matches best practices
- **Unix conventions for CLI** - Standard

### Should Adopt

| Pattern | Source | Why |
|---------|--------|-----|
| `--format json` default when piped | typer_cli | Better for automation |
| Structured error with suggestion | MCP best practices | "Did you mean X?" |
| `.mcp.json` for local dev | MCP templates | Standard pattern |
| `tests/conftest.py` with fixtures | pytest best practices | DRY test setup |
| `--dry-run` flag | CLI conventions | Safe preview |

### Should Avoid

| Anti-pattern | Source | Why Bad |
|--------------|--------|---------|
| Interactive Q&A generation | Skill Factory | Token-expensive, not scriptable |
| Streamlit UI for MCP | mcp-cookie-cutter | Over-engineering |
| SQLite logging | mcp-cookie-cutter | Unnecessary complexity |
| 6-phase workflow | agent-skill-creator | Too heavy for simple projects |
| ZIP output | Skill Factory | We want in-place generation |
| Typer/Click for CLI | Popular templates | argparse is stdlib, sufficient |
| DevFlow/JIRA integration | mcp-cookie-cutter | Scope creep |
| Copier for templates | - | Overkill for our use case |

### 🆕 Additions to Plan
1. **Add `--dry-run`** - Show what would be created without creating
2. **Add `.mcp.json` template** - For MCP projects, with `${CLAUDE_PLUGIN_ROOT}`
3. **Add `conftest.py`** - pytest fixtures for each project type
4. **Add error suggestions** - Scripts should suggest fixes on failure
5. **Detect TTY for format** - JSON when piped, table when interactive

### Reconsider

| Item | Current Plan | Alternative | Decision |
|------|--------------|-------------|----------|
| Pre-commit hooks | Optional flag | Always include | **Include by default** - consensus pattern |
| GitHub Actions | Not included | Generate workflow | **Add as optional** `--with-ci` |
| Dockerfile | Not included | Generate for MCP | **Skip** - deployment is separate concern |

---

## 7. Competitive Positioning

### Our Differentiators
1. **Script-based, not template-based** - Testable, debuggable
2. **Minimal output** - No management UIs, no SQLite, no Streamlit
3. **Integrated with flow-state** - Works standalone or in repo
4. **TDD-first** - Test passes before any feature code
5. **CLAUDE.md aligned** - Follows our documented conventions exactly

### Where Others Win
- **Copier**: Better for template updates over time (we're one-shot)
- **Skill Factory**: More interactive (we're scriptable)
- **mcp-cookie-cutter**: More features (we're minimal)

### Our Niche
**Minimal, testable, convention-following project initialization for LLM-assisted development.**

Not trying to be everything. Just enough structure to start writing tests.

---

## 8. Updated Recommendations

### Scripts to Update

**10_create_structure.py** additions:
- Add `--dry-run` flag
- Generate `.mcp.json` for MCP projects
- Generate `.pre-commit-config.yaml` by default

**20_setup_testing.py** additions:
- Generate `tests/conftest.py` with basic fixtures
- Include example async test for MCP projects

**30_setup_linting.py** changes:
- Always create pre-commit config (remove optional flag)
- Match exact ruff config from root pyproject.toml

**40_create_template.py** additions:
- CLI: Add TTY detection for format default
- MCP: Add error suggestion pattern in template
- All: Add docstring with usage example

### New Optional Script

**50_setup_ci.py** (optional, `--with-ci`):
- Generate `.github/workflows/ci.yml`
- pytest + ruff in workflow
- Only for standalone projects (not repo-mode)

---

## Sources

- https://github.com/anthropics/skills
- https://github.com/FrancyJGLisboa/agent-skill-creator
- https://github.com/alirezarezvani/claude-code-skill-factory
- https://github.com/codingthefuturewithai/mcp-cookie-cutter
- https://github.com/shubhamgupta-dat/mcp-server-template
- https://github.com/PyTemplate/typer_cli
- https://github.com/fpgmaas/cookiecutter-uv
- https://github.com/cookiecutter/cookiecutter
- https://github.com/copier-org/copier
- https://modelcontextprotocol.io/docs/develop/build-server
- https://gofastmcp.com/patterns/testing
