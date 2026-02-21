# DONE: Project-Level Linting Setup

**Date:** 2026-01-31
**Status:** Implemented (partial)

## Intent

Establish consistent code quality enforcement across the flow-state monorepo. Catch style issues, potential bugs, and type errors before they reach the codebase.

## Goal

All Python and Markdown files pass automated linting checks. Pre-commit hooks prevent non-compliant code from being committed.

## Current State

- No linting configuration exists
- Python files: ~40 across `youtube-to-markdown/`, `imap-stream-mcp/`, `tests/`
- Markdown files: ~25 across root, plugins, subskills, docs
- Build system: `uv` + `hatchling`, Python ≥3.10
- Code style: Google docstrings, type hints throughout (per CLAUDE.md)

## Tools

| Layer | Tool | Rationale |
|-------|------|-----------|
| Python lint/format | ruff | Fast, single tool replaces flake8+isort+black |
| Markdown lint | markdownlint-cli2 | Standard, configurable, npm-based |
| Type checking | pyright | Strict, fast, good IDE integration |
| Git hooks | pre-commit | Language-agnostic hook orchestration |

## Implementation

### 1. Root pyproject.toml

Create `/Users/vre/work/flow-state/pyproject.toml`:

```toml
[tool.ruff]
target-version = "py310"
line-length = 88
exclude = [".worktrees", ".venv", "__pycache__"]

[tool.ruff.lint]
select = [
    "E",    # pycodestyle errors
    "F",    # pyflakes
    "I",    # isort
    "UP",   # pyupgrade
    "B",    # flake8-bugbear
    "SIM",  # flake8-simplify
    "D",    # pydocstyle
]
ignore = [
    "D100", # missing docstring in public module
    "D104", # missing docstring in public package
    "D105", # missing docstring in magic method
]

[tool.ruff.lint.pydocstyle]
convention = "google"

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = ["D"]  # no docstrings required in tests

[tool.pyright]
pythonVersion = "3.10"
typeCheckingMode = "basic"
exclude = [".worktrees", ".venv"]
```

### 2. Markdownlint Config

Create `/Users/vre/work/flow-state/.markdownlint.json`:

```json
{
  "default": true,
  "MD013": false,
  "MD033": false,
  "MD041": false
}
```

Rules disabled:

- MD013: Line length (conflicts with prose writing)
- MD033: Inline HTML (needed for some formatting)
- MD041: First line heading (not all files need h1 first)

### 3. Pre-commit Config

Create `/Users/vre/work/flow-state/.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.9.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/DavidAnson/markdownlint-cli2
    rev: v0.17.0
    hooks:
      - id: markdownlint-cli2

  - repo: https://github.com/RobertCraigie/pyright-python
    rev: v1.1.391
    hooks:
      - id: pyright
```

### 4. Installation

```bash
# Install pre-commit
uv tool install pre-commit

# Install hooks
pre-commit install

# Run on all files (initial fix)
pre-commit run --all-files
```

## Tasks

1. [x] Create root `pyproject.toml` with ruff + pyright config
2. [x] Create `.markdownlint.json`
3. [x] Create `.pre-commit-config.yaml`
4. [x] Run `ruff check --fix .` to auto-fix issues
5. [x] Run `ruff format .` to format all Python - 38 files reformatted
6. [x] Fix remaining ruff errors manually - 13 B904 fixes (exception chaining)
7. [>] Run `markdownlint-cli2 --fix "**/*.md"` - 4301 errors, deferred to separate branch
8. [>] Fix remaining markdown errors manually - deferred
9. [>] Run `pyright` and fix type errors - requires per-project venv with deps
10. [x] Install pre-commit hooks
11. [x] Verify all tests still pass - 356 tests passing
12. [+] Calibrate ruff rules - relaxed line length, disabled strict docstring rules

## Acceptance Criteria

- [x] `ruff check .` exits 0
- [x] `ruff format --check .` exits 0
- [>] `markdownlint-cli2 "**/*.md"` exits 0 - deferred
- [>] `pyright` exits 0 - deferred
- [x] `pre-commit run --all-files` exits 0
- [x] `uv run pytest` passes - 356 tests

**Note:** Markdown linting errors are reviewed together with human companion to calibrate rules to the right level.

## Validation Approach

```bash
# Full validation sequence
ruff check . && \
ruff format --check . && \
markdownlint-cli2 "**/*.md" && \
pyright && \
cd tests && uv run pytest
```

## Constraints

- Must not break existing tests
- Must work with existing `uv` workflow
- Ruff rules must align with Google docstring style (per CLAUDE.md)
- Exclude `.worktrees/` from all linting (contains WIP code)

## Scope Exclusions

- CI/CD pipeline setup (separate task)
- Coverage thresholds (separate task)
- Editor/IDE configuration files (developer choice)

## Risks

- **Existing code may have many violations** - Mitigation: Use auto-fix first, then manual fixes
- **Pyright may flag false positives** - Mitigation: Start with `basic` mode, can relax if needed
- **Pre-commit adds commit latency** - Mitigation: ruff is fast (~10ms), acceptable tradeoff

---

## Reflection

### What Went Well

Ruff is fast and auto-fixes most issues. Pre-commit hooks work seamlessly. Iterative calibration with human companion prevented wasted effort on strict rules that don't fit the project.

### What Changed from Plan

Line length 88→140, removed SIM rules, disabled many D-rules, ignored B008 (DI pattern), disabled E501 (line length). Original rules were too strict - 304 errors initially, pragmatic calibration reduced to manageable fixes.

### Actual Config Diff

```toml
line-length = 140  # was 88
exclude = [..., "docs"]  # added docs folder
select = ["E", "F", "I", "UP", "B", "D"]  # removed SIM
ignore = [..., "D101", "D102", "D107", "D200", "D205", "D301", "B008", "E501"]
```

### Lessons Learned

Start relaxed, tighten later. Markdown linting needs per-project calibration - 4301 errors mostly stylistic conflicts. Pyright in monorepo is non-trivial - needs venv with all deps installed per package.
