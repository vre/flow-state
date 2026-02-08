# Plan: Project Initialization Skill

% Feedback: Deterministic/LLM split and ruff/pytest verification look solid.
% Feedback: Add explicit post-init hooks to run builder scripts and enforce failing tests first to lock "init -> generate -> TDD -> package".
% maybe rename as project-builder to align with skill-builder and mcp-builder plans?

## Goal

Create a skill that bootstraps new projects for skills, MCP servers, or CLI tools. The skill should front-load deterministic development infrastructure. Python projects only, Node.js out of scope.

## Context

Based on:
- `docs/Designing Initial Project Setup.md` - Setup sequence, scaffolding patterns
- `docs/Designing Skills.md` - Skill structure, <500 token budget
- `docs/Designing MCP Servers.md` - Single tool + action dispatcher
- `docs/Designing CLI Tools.md` - Unix conventions, scriptable patterns
- `docs/core/plans/2026-02-03-project-init-skill_research.md` - Competitor analysis
- Existing projects: `youtube-to-markdown/`, `imap-stream-mcp/`
- Brainstorming skill patterns: one question at a time, multiple choice preferred

## Core Principle

**Deterministic work → script. Probabilistic work → LLM.**

The script creates directory structure and template files. The LLM fills them with meaningful content using discovery answers. No string interpolation or Jinja in the script — just mkdir and touch.

## Acceptance Criteria

- [ ] Single script `init_project.py` with CLI subcommands and `--help`
- [ ] Creates valid pyproject.toml with hatchling build + uv
- [ ] Configures ruff linting matching repo standards (from root pyproject.toml)
- [ ] Sets up pytest with one passing test
- [ ] Generates full documentation set (CLAUDE.md, README.md, CHANGELOG.md, DEVELOPMENT.md, TESTING.md, LICENSE, .gitignore)
- [ ] Generates `.claude-plugin/marketplace.json`
- [ ] Generates type-specific template (SKILL.md / server.py / cli.py)
- [ ] Initializes git repo
- [ ] Works standalone or integrated into flow-state repo
- [ ] No interactive prompts in script (all via CLI args)
- [ ] Script prints help text when run without arguments
- [ ] Skill file `project-builder/SKILL.md` under 500 tokens

## Architecture: Script vs LLM Division

### Script does (deterministic)
- Create directory tree
- Create empty/stub template files
- Write pyproject.toml (fixed content, only name varies)
- Write ruff config (copied from repo standard)
- Write .gitignore (fixed content)
- Write .markdownlint.json (fixed content)
- Write .pre-commit-config.yaml (fixed content)
- Write .mcp.json for MCP projects (fixed structure)
- Write conftest.py and minimal passing test
- Write marketplace.json skeleton
- Run `git init`
- Run `uv sync`
- Run `uv run pytest` to verify
- Run `ruff check` to verify
- Output JSON summary of created files

### LLM does (probabilistic, using discovery answers)
- Fill README.md with purpose, features, usage examples
- Fill CLAUDE.md with project-specific role/rules (based on persona template + project context)
- Fill DEVELOPMENT.md with setup instructions
- Fill TESTING.md with test structure
- Fill CHANGELOG.md initial entry
- Fill SKILL.md description and trigger (skill projects)
- Fill server.py docstring and tool description (MCP projects)
- Fill cli.py description and help text (CLI projects)
- Fill marketplace.json description and keywords

## Discovery Step (in SKILL.md, before script)

Lightweight discovery borrowed from brainstorming skill patterns. Answers feed the LLM's file-filling step, not the script.

Use AskUserQuestion for multiple-choice questions only. Open-ended questions asked conversationally (one at a time).

### Questions

**Q1: Project type and license** (AskUserQuestion, two questions in one call)
- Type: Skill / MCP server / CLI tool
- License: MIT / Apache 2.0 / Other

**Q2: Project name** (conversational)
- Ask: "What should the project be called? Use kebab-case, e.g. `my-tool`."
- Used for directory name, pyproject.toml name
- Package name derived: `my-tool` → `my_tool` (kebab to snake_case)

**Q3: What problem does this solve?** (conversational)
- Ask: "In one sentence, what problem does this solve?"
- Feeds README, CLAUDE.md role, pyproject.toml description, SKILL.md trigger / server docstring / CLI help text

**Q4: Key capabilities** (conversational)
- Ask: "What are the 2-3 key things it should do?"
- Feeds README features section, SKILL.md steps / MCP actions / CLI subcommands

## Project Structures

### Common base (all types)
```
{name}/
├── CLAUDE.md                     # LLM behavioral config (symlinked as AGENTS.md)
├── AGENTS.md -> CLAUDE.md        # Symlink
├── README.md                     # Purpose, usage, features
├── CHANGELOG.md                  # Version history
├── DEVELOPMENT.md                # Dev environment setup
├── TESTING.md                    # How to run/write tests
├── LICENSE                       # User's chosen license
├── .gitignore                    # Python patterns
├── .markdownlint.json            # Markdown linting config
├── .pre-commit-config.yaml       # ruff + markdownlint hooks
├── .claude-plugin/
│   └── marketplace.json          # Plugin marketplace entry
├── pyproject.toml                # Build config + ruff + pyright
├── docs/
│   └── plans/                    # Design docs and plans
├── tests/
│   ├── conftest.py               # Shared fixtures
│   └── test_{name}.py            # Initial passing test
└── .worktrees/                   # Git worktree working dirs
```

### A. Skill Project (additions)
```
├── SKILL.md                      # Skill definition (<500 tokens)
├── scripts/                      # Numbered orchestration scripts
│   └── 10_example.py             # Stub script
├── subskills/                    # Conditional flow modules
└── {name_pkg}/                   # Python package for lib code
    └── __init__.py
```

### B. MCP Server Project (additions)
```
├── .mcp.json                     # Local dev config with ${CLAUDE_PLUGIN_ROOT}
└── {name_pkg}/                   # Python package
    ├── __init__.py               # Exports main()
    └── server.py                 # Single-tool dispatcher template
```

### C. CLI Tool Project (additions)
```
└── {name_pkg}/                   # Python package
    ├── __init__.py               # Exports main()
    └── cli.py                    # argparse scaffold template
```

## Script Design: `init_project.py`

Single script at `project-builder/project_builder/build_project.py`.

### Name Conversion

Kebab-case name → snake_case package name: `my-tool` → `my_tool`

```python
name_pkg = name.replace("-", "_")
```

Used everywhere a Python identifier is needed: package directory, import paths, entry points.

### Usage
```
python3 init_project.py <type> <name> <output_dir> [options]

Arguments:
  type          Project type: skill, mcp, cli
  name          Project name (kebab-case, e.g. my-tool)
  output_dir    Parent directory for the project

Options:
  --dry-run     Show what would be created, create nothing
  --help        Show this help text

Exit codes:
  0  Success
  1  Error (with suggestion)
  2  Usage error (shows help)
```

Running without arguments prints help text and exits with code 2.

### Script internals (functions, not classes)
```python
def main() → None                           # Parse args, dispatch
def create_base(name, output_dir) → Path    # Common dirs + files
def create_skill(name, project_dir) → None  # Skill-specific files
def create_mcp(name, project_dir) → None    # MCP-specific files
def create_cli(name, project_dir) → None    # CLI-specific files
def init_git(project_dir) → None            # git init
def init_uv(project_dir) → None             # uv sync
def verify(project_dir) → dict              # pytest + ruff check
def dry_run_report(name, type) → None       # Print what would be created
```

Output: JSON to stdout with created files, verification results.

### Content the script writes directly

**pyproject.toml** — complete, valid, type-specific:
```toml
[project]
name = "{name}"
version = "0.1.0"
description = ""
requires-python = ">=3.10"
dependencies = []  # or mcp/pydantic for MCP type

[dependency-groups]
dev = ["pytest>=9.0.0"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
target-version = "py310"
line-length = 140

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "D"]
ignore = ["D100", "D101", "D102", "D104", "D105", "D107", "D200", "D205", "D301", "D415", "B008", "E501"]

[tool.ruff.lint.pydocstyle]
convention = "google"

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = ["D"]
"**/scripts/*.py" = ["D103"]

[tool.pyright]
pythonVersion = "3.10"
typeCheckingMode = "basic"
```

MCP addition:
```toml
dependencies = ["mcp>=1.0.0", "pydantic>=2.0.0"]

[project.scripts]
{name} = "{name_pkg}:main"
```

CLI addition:
```toml
[project.scripts]
{name} = "{name_pkg}.cli:main"
```

**test_{name}.py** — minimal passing test:
```python
def test_placeholder():
    """Verify test infrastructure works."""
    assert True
```

**conftest.py** — empty with docstring:
```python
"""Shared test fixtures."""
```

**.gitignore** — standard Python patterns (matching repo's .gitignore, minus project-specific entries like the model binary). Must include `.worktrees/`, `.claude/`, `uv.lock`.

**.markdownlint.json** — matching repo config.

**.pre-commit-config.yaml** — ruff + markdownlint hooks matching repo config.

**.mcp.json** (MCP only):
```json
{
  "mcpServers": {
    "{name}": {
      "command": "uv",
      "args": ["--directory", "${CLAUDE_PLUGIN_ROOT}", "run", "{name}"]
    }
  }
}
```

**marketplace.json** (skill type — includes `"skills"` field):
```json
{
  "name": "{name}",
  "owner": { "name": "", "email": "" },
  "metadata": {
    "description": "",
    "version": "0.1.0",
    "pluginRoot": "./"
  },
  "plugins": [
    {
      "name": "{name}",
      "source": "./",
      "description": "",
      "version": "0.1.0",
      "category": "",
      "keywords": [],
      "skills": ["./"]
    }
  ]
}
```

**marketplace.json** (MCP/CLI type — no `"skills"` field):
```json
{
  "name": "{name}",
  "owner": { "name": "", "email": "" },
  "metadata": {
    "description": "",
    "version": "0.1.0",
    "pluginRoot": "./"
  },
  "plugins": [
    {
      "name": "{name}",
      "source": "./",
      "description": "",
      "version": "0.1.0",
      "category": "",
      "keywords": []
    }
  ]
}
```

**Template stubs** — empty files with just a header comment/frontmatter that the LLM fills:
- README.md: `# {name}\n`
- CHANGELOG.md: `# Changelog\n`
- DEVELOPMENT.md: `# Development\n`
- TESTING.md: `# Testing\n`
- CLAUDE.md: full persona + dev process + context management (see below)
- SKILL.md (skill type): frontmatter skeleton
- server.py (MCP type): import skeleton with single-tool pattern
- cli.py (CLI type): argparse scaffold

### CLAUDE.md Template Content

Includes persona + dev process + context management from current CLAUDE.md. Excludes "Implementing X" sections (those live in type-specific builder skills).

```markdown
# Ways of Working for LLM

NEVER START IMPLEMENTATION BEFORE APPROVAL. Autopilot is FAILURE.

Speak like a Finn or a Dutch - blunt, direct, concise and factual. No flattery or empty
compliments. Nothing is done before proven done, nothing is great before proven great. Never
say: "Good thinking", "Great idea", "You're right", "Good point", "You're absolutely right",
"Good choice", "Good feedback", "Excellent find", "This is excellent".

Base answers on scientific facts, logic, and documented information. State clearly when
uncertain or when evidence is insufficient. Show your reasoning when making claims. Cite
sources when they add clarity or evidence: `[1]` in body, `[1]: <url> "description"` in references.

Present findings, suggestions, and proposed changes first. Prioritize precision over
simplification. No unnecessary jargon. Use analogies and explain domain-specific concepts when
needed. Reply in user's language. Write text in English unless file is in other language.

You are a deep expert in your subject area. Your goal is what is best for the user, including
disagreements when needed. Be critical, analytical, forward-looking. Present your own
perspective with justification. Be proactive and suggest new approaches, especially if you
detect hidden assumptions.

## THE DEVELOPMENT PROCESS

1. Plan Phase Rules
   - Work in cooperation with the human companion, don't push to proceed before they say so.
   - ALWAYS WRITE THE PLAN: 'docs/plans/' for project-specific
   - Define measurable acceptance criteria and validation approach
   - Mission Command: include intent, goal, proper guidance with constraints and necessary situational context
   - Use exact requirements, no temporal references ("current best practices", "latest version")
   - Create git worktree under '.worktrees/[short_description]' for isolated development
2. Implementation Phase Rules
   - Implement ONLY what is explicitly requested - no unrequested additions
   - Don't touch working code. New ideas → new branch, not mutation of existing features.
   - NO CODE before tests + YAGNI + KISS + DRY + Avoid Wordiness
   - Testability: Pure functions + thin `main()` glue. No DI frameworks.
   - Use `uv` for python development environment management
   - Type hints throughout
   - Google style docstrings
   - For every todo do `git add` for new files, `git commit -a -m "{minimal description}"`
3. Reflect Phase Rules
   - Mark status: `[x]` done `[-]` not done `[>]` deferred `[_]` skipped `[+]` discovered `[?]` unclear
   - Add "## Reflection": what went well, what changed from plan, lessons learned
4. Merge Phase Rules
   - Validate what was created with skeptic's eye
   - Update Documentation: CHANGELOG.md, TESTING.md, DEVELOPMENT.md, README.md
   - Ask final acceptance from the human companion

## Context Management

- If context exceeds 50%: restate current task before continuing
- At 60%: consider nuking the chat and starting fresh
- After compaction: confirm task state with user before resuming work
- Single-purpose conversations - mixing unrelated topics degrades performance ~40%
```

## SKILL.md Flow

```
Step 0: Discovery
  AskUserQuestion: project type (skill/mcp/cli) + license (MIT/Apache 2.0/Other)
  Ask conversationally (one at a time): project name, problem statement, key capabilities

Step 1: Create project structure
  python3 ./scripts/init_project.py <type> <name> <output_dir>
  Creates: full directory tree with template files
  Validates: pytest passes, ruff check passes
  If script exits non-zero: show error output, STOP.

Step 2: Fill template files
  Using discovery answers, write content into all template files:
  - README.md: purpose, features (from capabilities), basic usage
  - DEVELOPMENT.md: setup with uv, running tests, linting
  - TESTING.md: test structure, running tests, design principles
  - CHANGELOG.md: initial 0.1.0 entry
  - LICENSE: chosen license text
  - marketplace.json: description, keywords, category from capabilities
  - CLAUDE.md: add "## Tech Stack" and "## Project Structure" sections
  Type-specific:
  - Skill: SKILL.md description (trigger from problem statement), example script stub
  - MCP: server.py tool docstring and action descriptions (from capabilities)
  - CLI: cli.py description and help text (from capabilities)

DONE: Show created files tree.
  Suggest next step: invoke skill-builder / mcp-builder / cli-tool-builder
  to write the first FAILING test for actual functionality.
  The placeholder test (assert True) proves infra works.
  The builder skill replaces it with real domain tests (TDD red → green).
```

## Tasks

1. [ ] Write `project-builder/project_builder/build_project.py` — single script, all subcommands
2. [ ] Write tests for build_project.py (create each type, verify structure, verify test passes, verify lint passes)
3. [ ] Write `project-builder/SKILL.md` — orchestration under 500 tokens
4. [ ] Write `project-builder/README.md` — usage documentation
5. [ ] Test: create skill project end-to-end via skill invocation
6. [ ] Test: create MCP project end-to-end via skill invocation
7. [ ] Test: create CLI project end-to-end via skill invocation

## Validation Approach

```bash
# Test script directly
python3 project-builder/project_builder/build_project.py skill test-skill /tmp/claude/test
python3 project-builder/project_builder/build_project.py mcp test-mcp /tmp/claude/test
python3 project-builder/project_builder/build_project.py cli test-cli /tmp/claude/test

# Verify each created project
cd /tmp/claude/test/test-skill && uv run pytest && ruff check .
cd /tmp/claude/test/test-mcp && uv run pytest && ruff check .
cd /tmp/claude/test/test-cli && uv run pytest && ruff check .

# Verify git
cd /tmp/claude/test/test-skill && git log --oneline

# Dry run
python3 project-builder/project_builder/build_project.py --dry-run skill test-skill /tmp/claude/test

# No args = help
python3 project-builder/project_builder/build_project.py
```

Test via skill invocation with `claude -p`.

## Design Decisions (Resolved)

1. **One script, not four.** `init_project.py` with functions for each concern. One invocation, one failure mode. Subcommands control project type.

2. **Script creates structure, LLM fills content.** Clean separation: deterministic (dirs, config files, fixed templates) vs probabilistic (meaningful README text, CLAUDE.md role description, SKILL.md triggers).

3. **marketplace.json generated.** Skeleton with empty description/keywords — LLM fills these in Step 2.

4. **Git initialized.** Script runs `git init` + initial commit with all generated files.

5. **Pre-commit hooks included by default.** Research showed consensus: always include. Ruff + markdownlint hooks.

6. **GitHub Actions CI: ask user.** Implemented as subskill `./subskills/setup_ci.md` to keep main skill focused.

7. **CLAUDE.md = persona + dev process + context management.** "Implementing X" sections excluded — those live in type-specific builder skills (skill-creator, mcp-builder, cli-builder).

8. **Discovery: AskUserQuestion for multiple choice, conversational for open-ended.** Reduces widget calls from 5 to 1. Open-ended questions (name, problem, capabilities) asked conversationally one at a time.

9. **uv.lock excluded from git.** Generated .gitignore excludes uv.lock. Matching existing repo convention. Dependencies pinned in pyproject.toml, lock file is environment-specific.

10. **Renamed to project-builder.** Aligned with sibling naming: skill-builder, mcp-builder, cli-tool-builder. Builder skills use `{noun}-builder` pattern.

11. **Explicit handoff to builder skills.** DONE step suggests invoking the appropriate builder skill next. Chain: init (green infra test) → builder (red domain test → green). The placeholder `assert True` proves the test framework works; the builder skill writes the first real failing test.

## Constraints

- Python only (no TypeScript/Node.js)
- Local development focus (no deployment automation)
- Minimal dependencies in generated projects
- Follow existing repo conventions exactly
- No Jinja/string interpolation in script for content — just fixed files

## Post-Integration: Compatibility with skill-builder

After integration review with skill-builder, the following changes are needed:

### 1. SKILL_MD_TEMPLATE needs `keywords` field

skill-builder's `validate_structure.py` requires `keywords` in frontmatter.
Current template lacks it. Add `keywords:` placeholder.

```yaml
---
name: {name}
description: Use when <trigger>. <What it produces>.
keywords:
allowed-tools:
  - Bash
  - Read
  - Write
---
```

### 2. SKILL_MD_TEMPLATE naming convention note

skill-builder enforces gerund naming (`creating-widgets` not `widget-creator`).
project-builder passes `{name}` verbatim. Two options:
- A) project-builder passes name as-is, LLM fixes during Step 2 (fill templates)
- B) project-builder's discovery asks for gerund name for skill projects

Option A is simpler — project-builder is infrastructure, naming is domain concern.
Add a comment in the template: `# Note: use gerund naming (creating-X) for skill names`

### 3. `full_package.md` delegation

skill-builder's deferred `full_package.md` subskill duplicates project-builder's scaffolding.
When implemented, `full_package.md` should delegate to project-builder for:
- test stubs, marketplace.json, CHANGELOG.md, pyproject.toml
And only add skill-builder-specific concerns:
- pressure test configuration, rationalization table

### 4. Test placement convention

project-builder uses `tests/{skill-name}/`. skill-builder uses `{skill-name}/tests/`.
Convention: follow project-builder's pattern (repo-level `tests/` directory) for consistency.
skill-builder tests should move to `tests/skill-builder/` to match.

## Post-Integration: Cross-Skill Alignment with cli-tool-builder (2026-02-07)

### Concern Borders

- **project-builder** owns: directory structure, pyproject.toml (initial/base), dev infrastructure (ruff, pytest, git, pre-commit), CLAUDE.md, marketplace.json skeleton, README/docs stubs
- **Builder skills** own: domain-specific code that REPLACES project-builder's stubs
- **Integration chain**: project-builder (green infra test) → builder skill (red domain test → green)

### 1. Decision #10 outdated: rename completed

Decision #10 says "Naming stays project-init". This is stale — the skill was renamed to `project-builder` (commit 064fe78). Update decision text.

**Files:** plan decision #10

### 2. CLI stub is a placeholder, not the final code

project-builder's `CLI_PY_TEMPLATE` creates a minimal 30-line cli.py. When cli-tool-builder runs next, it REPLACES this with the full implementation (~90 lines: load_env, POSIX flags, TTY detection, Result type). This is by design:
- project-builder proves infra works (tests pass, lint passes)
- cli-tool-builder adds domain patterns

Document this in the plan and in `build_project.py` as a comment on `CLI_PY_TEMPLATE`.

**Files:** plan, build_project.py CLI_PY_TEMPLATE comment

### 3. pyproject.toml: base vs extended

project-builder creates minimal pyproject.toml (no optional-deps). cli-tool-builder adds:
```toml
[project.optional-dependencies]
mcp = ["mcp>=1.0", "pydantic"]
keyring = ["keyring"]
dev = ["pytest>=7.0", "ruff"]
```
This is LLM-patched (not programmatic). project-builder should NOT include these — they're domain concerns.

**Files:** no code change, strategy documented here

### 4. Naming convention alignment

Builder skills use `{noun}-builder` pattern: project-builder, skill-builder, mcp-builder, cli-tool-builder. This is different from skill-builder's gerund convention (`creating-X`) which applies to generated workflow skills, not infrastructure builders.

Update SKILL.md "Done" step to use correct names:
```
Suggest: invoke skill-builder / mcp-builder / cli-tool-builder
```

**Files:** project-builder/SKILL.md (verify handoff names are correct)
