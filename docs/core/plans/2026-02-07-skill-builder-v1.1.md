# Plan: skill-builder v1.1 — Builder Skill Support

## Goal

Extend skill-builder to handle **builder skills** (skills with scripts, templates, tests) — not just simple workflow skills. Based on gaps found during cli-tool-builder development.

## Problem

skill-builder is tuned for workflow skills (SKILL.md only). Builder skills need scripts/, templates/, tests/, cross-skill awareness. When building cli-tool-builder, skill-builder provided zero guidance for 80% of the work.

## Intent

- Route builder skills to dedicated guidance (new subskill)
- Validate scripts are syntactically correct
- Validate subskills are well-formed
- Warn when scripts exist without tests
- Tiered token budget: 300 (workflow) / 500 (builder)

## Constraints

- NO CODE before tests (TDD)
- Pure functions, type hints, Google-style docstrings
- Each check: write tests → implement → verify → commit
- `uv` for env, `pytest` for tests
- Keep SKILL.md under 200 tokens, subskills under 500

## Tasks

### Task 1: Add `check_script_syntax()` with tests

**Files:**
- `tests/skill-builder/test_validate_structure.py` — add `TestScriptSyntax` (6 tests)
- `skill-builder/scripts/validate_structure.py` — add `check_script_syntax()`

**Behavior:** Use `ast.parse()` on `./scripts/*.py` files referenced in SKILL.md via `PATH_REF_RE`. Skip missing files (path check handles that). Report syntax errors with filename and line.

**Tests:**
1. Valid script passes
2. Invalid script reports syntax error with filename
3. No script references → check not triggered
4. Multiple scripts, one bad → exactly 1 issue
5. Missing script file → no crash (path check handles)
6. Error message includes filename

### Task 2: Add `check_subskill_validity()` with tests

**Files:**
- `tests/skill-builder/test_validate_structure.py` — add `TestSubskillValidity` (5 tests)
- `skill-builder/scripts/validate_structure.py` — add `check_subskill_validity()`

**Behavior:** Light validation on referenced `./subskills/*.md` files. NOT recursive SKILL.md validation (subskills lack frontmatter). Check: file not empty, has at least one markdown heading (`^#`), under 2000 chars (~500 tokens). Report issues prefixed with `[filename]`.

**Tests:**
1. Valid subskill passes
2. Empty subskill reports issue
3. Missing subskill → no crash (path check handles)
4. No headings → reports issue
5. Issues prefixed with `[subskill_name]`

### Task 3: Add `check_test_coverage()` with tests

**Files:**
- `tests/skill-builder/test_validate_structure.py` — add `TestTestCoverage` (5 tests)
- `skill-builder/scripts/validate_structure.py` — add `check_test_coverage()`

**Behavior:** Warn (severity=warning) if `scripts/` dir exists next to SKILL.md but no test directory found. Check locations:
1. `{skill_dir}/tests/`
2. `{skill_dir}/../tests/`
3. `{skill_dir}/../../tests/{skill_dir_name}/` (repo-root pattern: `tests/skill-builder/`)

**Tests:**
1. scripts/ with tests/ at same level → no warning
2. scripts/ without any tests → warning
3. No scripts/ dir → check not triggered
4. tests/ at grandparent level with skill name dir → accepted
5. Warning has `severity=warning`, does not fail validation

### Task 4: Add tiered token budget with tests

**Files:**
- `tests/skill-builder/test_validate_structure.py` — add `TestTieredTokenBudget` (5 tests)
- `skill-builder/scripts/validate_structure.py` — modify `validate()`, add `_detect_token_budget()`

**Behavior:** Replace `TOKEN_BUDGET = 300` with:
- `TOKEN_BUDGET_WORKFLOW = 300`
- `TOKEN_BUDGET_BUILDER = 500`

Detect builder: name matches `BUILDER_RE` (already exists) OR body contains `./scripts/` path references.

**Tests:**
1. Workflow skill at 350 tokens → FAIL (over 300)
2. Builder-named skill at 350 tokens → PASS (under 500)
3. Script-referencing skill at 350 tokens → PASS (500 budget)
4. Builder skill at 550 tokens → FAIL (over 500)
5. Error message shows correct limit value

### Task 5: Create `subskills/builder_skill.md`

**Files:**
- `skill-builder/subskills/builder_skill.md` (new)

**Content:** Guides creation of skills with scripts/templates/tests. Must:
- Gate: "If no scripts needed → use skill_only.md instead. STOP."
- Gather: name (noun-builder form), outputs, script names, template files
- Directory structure guidance
- TDD: tests before scripts
- Validate with `validate_structure.py`
- Under 500 tokens

### Task 6: Update SKILL.md routing + validate

**Files:**
- `skill-builder/SKILL.md` — add builder route to Step 1
- Verify under 200 tokens
- Verify passes `validate_structure.py`

**Change:** Add one line:
```
- Builder skill (needs scripts/templates/tests) → Read and follow `./subskills/builder_skill.md`
```

### Task 7: Full test suite verification

- All existing 49 tests (34 + 15) pass
- All new ~21 tests pass
- `validate_structure.py` passes on `skill-builder/SKILL.md`
- `validate_structure.py` passes on `cli-tool-builder/SKILL.md` (builder budget)
- Commit all changes

## Execution Order

```
Task 1 → Task 2 → Task 3 → Task 4 (sequential TDD: tests + implementation per check)
    ↓
Task 5 (builder_skill.md, after validate can check it)
    ↓
Task 6 (SKILL.md routing, after subskill exists)
    ↓
Task 7 (full verification)
```

## Acceptance Criteria

- [x] 4 new check functions in `validate_structure.py` (check_script_syntax, check_subskill_validity, check_test_coverage, _detect_token_budget)
- [x] ~21 new tests, all passing (76 total in skill-builder)
- [x] All 49 existing tests still passing
- [x] `builder_skill.md` under 500 tokens (1950 chars ≈ 488 tokens)
- [x] `SKILL.md` under 200 tokens with builder route (785 chars ≈ 196 tokens)
- [x] cli-tool-builder SKILL.md passes validation with builder budget
- [x] No regressions in cli-tool-builder tests (81 tests)
