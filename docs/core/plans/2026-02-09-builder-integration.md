# Builder Skills Integration

Date: 2026-02-09
Branch: `feature/cli-tool-builder` (worktree `.worktrees/cli-tool-builder`)

## Intent

The three builder skills (project-builder, skill-builder, cli-tool-builder) were built independently. When composed in sequence, they collide: duplicate test directories, nested package-in-package structures, wasted SKILL.md content, no cleanup guidance. Fix the integration points so the pipeline project-builder → skill-builder → cli-tool-builder produces clean output.

## Goal

Running the three skills in sequence produces a project with:
- No duplicate files (one pyproject.toml, one tests/ dir, one SKILL.md)
- Flat scripts in `scripts/` (not nested packages)
- Each skill knows what it owns and what it delegates

## Constraints

- Working directory: `/Users/vre/work/flow-state/.worktrees/cli-tool-builder`
- Run tests with: `uv run pytest tests/{skill}/ -v` (requires `dangerouslyDisableSandbox: true`)
- TDD: tests first
- Each builder skill must still work standalone (not just in the pipeline)
- Commit after each task: `git commit -a -m "{description}"`

## Problem Analysis

Five integration gaps found during end-to-end testing (project-builder → skill-builder → cli-tool-builder → worktree-manager skill):

### Gap 1: cli-tool-builder only generates standalone packages

`generate_cli.py --output scripts/` creates `scripts/manage_worktree/manage_worktree/cli.py` — a full package with its own `pyproject.toml`, `tests/`, `__init__.py`. Inside a skill's `scripts/` dir this creates 3-level nesting and duplicate infrastructure.

### Gap 2: Duplicate test directories

skill-builder writes working tests in `tests/test_*.py`. cli-tool-builder generates stub tests in `scripts/{tool}/tests/`. Two test dirs, neither references the other. The stubs are orphaned `NotImplementedError` files.

### Gap 3: project-builder fills SKILL.md that gets overwritten

project-builder's Step 2 fills SKILL.md with guessed content (script names like `10_create.py`). skill-builder completely rewrites it. The filled content is wasted effort.

### Gap 4: No cleanup instructions after cli-tool-builder

builder_skill.md Step 4 says "invoke cli-tool-builder" but doesn't say what to do with the generated package structure, or that its tests/ should be deleted.

### Gap 5: Skills assume top-level invocation

Each skill generates everything for a complete project. When composed, they over-produce. cli-tool-builder doesn't know it's inside a skill-builder workflow.

## Ownership Boundaries

```
project-builder owns:         skill-builder owns:           cli-tool-builder owns:
─────────────────────         ───────────────────           ──────────────────────
pyproject.toml                SKILL.md (content)            Generated file CONTENT
.gitignore                    tests/conftest.py             Action functions
.pre-commit-config.yaml       tests/test_*.py              dispatch() + Result type
CLAUDE.md (base)              scripts/ (location + naming)  CLI arg parsing
README.md (stub)              subskills/                    format_output()
CHANGELOG.md (stub)           Validation
docs/plans/
.worktrees/
git init + uv sync
```

Key rules:
- **Each skill creates only what it owns.** Stubs for downstream skills are minimal placeholders.
- **cli-tool-builder owns content, skill-builder owns location.** skill-builder passes `--output` and `--name` to cli-tool-builder. cli-tool-builder writes file content, not directory structure.

## Tasks

### Task 1: Add `--flat` mode to `generate_cli.py`

**Why:** cli-tool-builder must produce a single .py file when invoked as part of skill-builder workflow.

**Critical constraint:** `--flat` CANNOT compose existing templates. `cli.py.tmpl` uses relative import `from .${module_name} import ACTIONS, dispatch, format_output` — this doesn't work in a single file. A new template is needed.

**Changes to `cli-tool-builder/templates/flat.py.tmpl`** (NEW FILE):

Create a new template that merges all content into one self-contained file:
```
"""${tool_name} - CLI tool with action dispatcher."""

from __future__ import annotations
import argparse, json, sys
from dataclasses import dataclass, field
from typing import Any

# --- Exit codes ---
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2

@dataclass
class Result:
    data: Any = None
    error: str | None = None
    exit_code: int = EXIT_OK
    metadata: dict = field(default_factory=dict)
    @property
    def ok(self) -> bool:
        return self.error is None

# --- Actions ---
${action_functions}

def show_help(**kwargs) -> Result:
    ...  (same as core.py.tmpl)

ACTIONS: dict[str, callable] = {
${action_registry}
    "help": show_help,
}

def dispatch(action: str, **kwargs) -> Result:
    ...  (same as core.py.tmpl)

def format_output(result: Result, fmt: str = "auto") -> str:
    ...  (same as core.py.tmpl, include _format_table)

# --- CLI ---
def build_parser() -> argparse.ArgumentParser:
    ...  (adapted from cli.py.tmpl, no relative imports)

def main(argv: list[str] | None = None) -> int:
    ...  (adapted from cli.py.tmpl, no relative imports, no load_env)

if __name__ == "__main__":
    sys.exit(main())
```

The template must be a real file at `cli-tool-builder/templates/flat.py.tmpl` using `string.Template` substitution (same `${}` pattern as existing templates).

**Changes to `cli-tool-builder/scripts/generate_cli.py`:**

1. Add `--flat` flag to `build_parser()` (line 275-303)
2. Add `generate_flat()` function:
   ```python
   def generate_flat(name: str, operations: list[str], output_dir: Path, description: str) -> None:
       module_name = name.replace("-", "_")
       user_actions = [a for a in operations if a not in RESERVED_ACTIONS]
       action_functions = "\n\n".join(generate_action_function(a) for a in user_actions)
       action_registry = generate_action_registry(operations)
       action_help_lines = generate_action_help_lines(operations)
       template = load_template("flat.py.tmpl")
       content = template.safe_substitute(
           tool_name=name, module_name=module_name,
           tool_description=description,
           action_functions=action_functions,
           action_registry=action_registry,
           action_help_lines=action_help_lines,
       )
       write_file(output_dir / f"{module_name}.py", content)
   ```
3. In `main()`, branch on `args.flat`:
   ```python
   if args.flat:
       generate_flat(name, operations, output_dir, description)
   else:
       generate(name, operations, output_dir, description, domain=domain)
   ```

**Tests to add in `tests/cli-tool-builder/test_generate_cli.py`:**

New `TestFlatMode` class (7 tests):
- `test_flat_creates_single_file(tmp_path)` — only one .py file, no subdirs in output
- `test_flat_no_package_structure(tmp_path)` — no `__init__.py`, no `pyproject.toml`, no `tests/`
- `test_flat_file_has_dispatch(tmp_path)` — contains `def dispatch` and `ACTIONS`
- `test_flat_file_has_argparse(tmp_path)` — contains `ArgumentParser`
- `test_flat_file_has_result(tmp_path)` — contains `class Result`
- `test_flat_file_passes_ast_parse(tmp_path)` — `ast.parse()` succeeds
- `test_flat_file_has_all_actions(tmp_path)` — each requested action name appears as function
- `test_non_flat_unchanged(tmp_path)` — existing `generate()` still creates full package (regression guard)

Each test calls `main(["--name", "test_tool", "--operations", '["list", "get"]', "--output", str(tmp_path), "--flat"])` and inspects the output.

### Task 2: Reduce project-builder's SKILL.md template to stub

**Why:** project-builder fills SKILL.md with guessed script names that skill-builder always overwrites.

**Changes to `project-builder/project_builder/build_project.py`:**

Replace `SKILL_MD_TEMPLATE` (lines 172-196) with:
```python
SKILL_MD_TEMPLATE = """\
---
name: {name}
description: Use when TODO
keywords: TODO
allowed-tools:
  - Bash
  - Read
---

# {title}

TODO: Use skill-builder to fill this in.
"""
```

`create_skill()` at line 442 uses `SKILL_MD_TEMPLATE.format(name=name, title=title)` — this still works since the stub uses `{name}` and `{title}` placeholders.

**Changes to `project-builder/SKILL.md`:**

In Step 2, change the SKILL.md bullet from current text to:
"SKILL.md: leave as stub — skill-builder fills this."

**Tests to update in `tests/project-builder/test_build_project.py`:**
- `test_skill_md_has_frontmatter` — passes: stub has `---`, `name: my-skill`, `keywords:`
- Add `test_skill_md_is_stub` — asserts `"TODO"` in content (confirms it's a placeholder, not filled-in guesses)

### Task 3: Update builder_skill.md for clean cli-tool-builder integration

**Why:** builder_skill.md says "invoke cli-tool-builder" without specifying how.

**Token budget:** Currently 1914 chars (~478 tokens). Budget is 500 tokens (2000 chars). Available headroom: 86 chars.

The `--flat` instruction adds ~200 chars. Must cut ~120 chars elsewhere.

**Cuts to make room:**
- Step 1: Remove question examples `(kebab-case: \`log-analyzer\`)` and `(e.g. \`generate_foo.py, validate_foo.py\`)` — saves ~70 chars
- Step 2: Remove `# if routing needed` and `# if templates needed` comments — saves ~40 chars
- Step 7: Compress to one line — saves ~20 chars

**New Step 4 content** (replaces current):
```
## Step 4: Implement Scripts

Pure functions, type hints, Google docstrings. Thin `main()` glue.
Each script: `#!/usr/bin/env python3`, stdin/stdout, JSON output, exit codes.

If script is a CLI tool with actions, use cli-tool-builder `--flat`:
```bash
python3 ./cli-tool-builder/scripts/generate_cli.py --name ${SCRIPT} --operations '["action1", "action2"]' --output ${SKILL_DIR}/scripts/ --flat
```
Then fill in action stubs with real logic.
```

**IMPORTANT:** The `--operations` flag takes a JSON array of strings, NOT dicts. Example: `'["create", "list", "clean"]'`, NOT `'[{"name": "create", ...}]'`.

**Measure after changes:** `wc -c` must be ≤2000 chars.

### Task 4: Update cli-tool-builder SKILL.md for embedded usage

**Why:** cli-tool-builder's SKILL.md only documents standalone workflow.

**Changes to `cli-tool-builder/SKILL.md`:**

In the Workflow section, after item 3 (Scaffold), add a sub-bullet:
```
- Embedded (inside skill): add `--flat` flag. Creates single .py file, no package, no tests.
```

In the "What Gets Generated" section, add after the existing tree:
```
With `--flat`:
    ${DIR}/${NAME}.py    # All-in-one: Result, actions, dispatch, argparse
```

### Task 5: Integration test

**Why:** Verify the full pipeline produces clean output.

**Test location:** `tests/integration/test_builder_pipeline.py`

**Prerequisites:** This test requires `git` and `uv` in PATH (real subprocesses). Mark with:
```python
pytestmark = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("uv") is None,
    reason="Requires git and uv"
)
```

**Test class `TestBuilderPipeline`:**

1. `test_project_builder_creates_stub_skill_md(tmp_path)`:
   - Run `build_project.py skill test-proj {tmp_path}` via subprocess
   - Assert SKILL.md contains "TODO"
   - Assert SKILL.md does NOT contain `10_example.py`

2. `test_flat_cli_creates_single_file(tmp_path)`:
   - Create `{tmp_path}/scripts/` dir
   - Run `generate_cli.py --name test_tool --operations '["list","get"]' --output {tmp_path}/scripts/ --flat`
   - Assert `scripts/test_tool.py` exists
   - Assert NO `scripts/test_tool/` directory exists
   - Assert NO `pyproject.toml` in scripts/
   - Assert NO `tests/` in scripts/

3. `test_validate_structure_passes_with_flat_script(tmp_path)`:
   - Create a SKILL.md referencing `./scripts/test_tool.py`
   - Create `scripts/test_tool.py` with valid Python
   - Run `validate_structure.py {tmp_path}/SKILL.md`
   - Assert passes (exit 0, `"pass": true`)

4. `test_full_pipeline_no_nesting(tmp_path)`:
   - Run project-builder → creates scaffold
   - Run cli-tool-builder --flat → creates single script
   - Walk `scripts/` directory
   - Assert max depth is 1 (no nested dirs under scripts/)
   - Assert exactly 1 .py file in scripts/
   - Assert 0 pyproject.toml files under scripts/

## Acceptance Criteria

- [x] `flat.py.tmpl` template created (self-contained, no relative imports)
- [x] `generate_cli.py --flat` produces a single .py file
- [x] `generate_cli.py` without `--flat` still produces full package (regression)
- [x] Flat file passes `ast.parse()` and contains Result + dispatch + argparse
- [x] 8 new tests for flat mode (TestFlatMode: 7 + 1 regression), all passing
- [x] project-builder's SKILL.md template is a stub with TODO marker
- [x] project-builder's SKILL.md Step 2 says to leave SKILL.md for skill-builder
- [x] builder_skill.md Step 4 specifies `--flat` with correct `--operations` format (string array)
- [x] builder_skill.md ≤2000 chars after changes (1950 chars)
- [x] cli-tool-builder SKILL.md documents `--flat` usage
- [x] Integration tests pass (4/4 pipeline tests, no nesting)
- [x] All existing tests pass (218 across all builders)
