# Builder Skills: Bug Fixes from End-to-End Testing

Date: 2026-02-07
Branch: `feature/cli-tool-builder` (worktree `.worktrees/cli-tool-builder`)

## Intent

Fix 5 bugs found during end-to-end testing of the skill-builder workflow. Two are high-severity (let broken pipelines pass validation), three are low-severity (friction and UX).

## Goal

All bugs fixed. All existing tests pass. New tests cover the changes.

## Constraints

- Working directory: `/Users/vre/work/flow-state/.worktrees/cli-tool-builder`
- Run tests with: `uv run pytest tests/skill-builder/ -v`
- TDD: write/update tests first, then implement
- `builder_skill.md` is currently ~418 tokens — must stay under 500
- `validate_structure.py` is at `skill-builder/scripts/validate_structure.py`
- Tests are at `tests/skill-builder/test_validate_structure.py`
- Fixtures are at `tests/skill-builder/conftest.py`
- Commit after each task: `git commit -a -m "{description}"`

## Context

### Bug 1: No cross-script output contract guidance

`builder_skill.md` Step 3 (Write Tests) doesn't mention that scripts piping to each other need a shared output schema. During log-analyzer build: JSON parser normalized `msg`→`message`, KV parser didn't, report script expected `message`. Unit tests passed, pipeline produced wrong output silently.

### Bug 2: No smoke test step

`builder_skill.md` ends at "Validate" (runs `validate_structure.py`). That checks SKILL.md formatting only. No step to run the actual pipeline on sample data. The smoke test is what caught Bug 1.

### Bug 3: Gerund naming convention too rigid

`GERUND_RE = re.compile(r"^[a-z]+-?[a-z]*ing(-[a-z]+)+$")` hard-fails names like `log-analyzer`. All 3 builder skills in this project needed a `BUILDER_RE` exception. Superpowers skills also don't follow it (`brainstorming`, `systematic-debugging`, etc). Decision: remove both `GERUND_RE` and `BUILDER_RE`. Replace with kebab-case + ≥2 segments.

### Bug 4: sys.path.insert boilerplate

Every test file repeats `sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))`. `builder_skill.md` should instruct creating a `conftest.py` with this setup.

### Bug 5: Validator traceback on directory input

`validate_file("/tmp/claude/log-analyzer")` gives raw `IsADirectoryError`. Should auto-detect `SKILL.md` inside directory, or suggest fix.

## Tasks

### Task 1: Fix naming validation (Bug 3)

Changes to `skill-builder/scripts/validate_structure.py`:
1. Remove `GERUND_RE` constant (line 25)
2. Remove `BUILDER_RE` constant (line 26)
3. Replace the naming block (lines 227-239) with kebab-case check: `^[a-z]+(-[a-z]+)+$` (lowercase, hyphen-separated, ≥2 segments). Error message: `"Name '{name}' must be kebab-case with ≥2 segments (e.g. 'log-analyzer', 'skill-builder')"`
4. `_detect_token_budget` (line 183) still uses `BUILDER_RE` — replace with inline check: `name.endswith("-builder")` or keep the `./scripts/` detection (which already works)

Changes to `tests/skill-builder/test_validate_structure.py`:
- Replace `TestGerundNaming` class (lines 248-317) with `TestNaming` class
- Test cases: kebab-case passes, single segment fails, uppercase fails, `widget-creator` passes (was failing before), `skill-builder` passes (no more warning), `log-analyzer` passes
- Update `conftest.py`: `skill_bad_name` fixture — change to a single-segment name like `widget` (since `widget-creator` is now valid)

Changes to `tests/skill-builder/conftest.py`:
- `valid_skill` fixture: name can stay `creating-widgets` (still valid kebab)
- `skill_bad_name` fixture: change name from `widget-creator` to just `widget` (single segment = invalid)

### Task 2: Fix directory input handling (Bug 5)

Changes to `skill-builder/scripts/validate_structure.py` in `validate_file()`:
- After `path = Path(file_path)`, check `path.is_dir()`
- If directory and `(path / "SKILL.md").exists()`: use that path
- If directory and no SKILL.md: print `"Error: {path} is a directory with no SKILL.md. Try: validate_structure.py {path}/SKILL.md"` and exit 1

Tests: add to `TestCLI` class:
- `test_directory_with_skill_md_works(tmp_path)` — create dir with SKILL.md, validate_file should work
- `test_directory_without_skill_md_exits(tmp_path)` — empty dir, should SystemExit

### Task 3: Update builder_skill.md (Bugs 1, 2, 4)

Current content is 49 lines, ~418 tokens. Budget: 500 tokens.

Changes to `skill-builder/subskills/builder_skill.md`:

Step 3 (Write Tests First) — add after existing content:
- Mention `conftest.py` with sys.path.insert for `scripts/` imports (Bug 4)
- If scripts pipe to each other: define output schema, write integration test (Bug 1)

Add Step 7: Smoke Test (Bug 2) — after Step 6 (Validate):
- Create sample input. Run pipeline from SKILL.md Step 1→N. Verify output.

Token budget warning: measure after changes. If >500 tokens, compress existing steps.

## Acceptance Criteria

- [x] Bug 1: builder_skill.md Step 3 mentions output contracts for piped scripts
- [x] Bug 1: builder_skill.md Step 3 mentions integration test for piped scripts
- [x] Bug 2: builder_skill.md has Step 7 smoke test with sample data
- [x] Bug 3: `GERUND_RE` and `BUILDER_RE` removed from validate_structure.py
- [x] Bug 3: replaced with kebab-case + ≥2 segments check
- [x] Bug 3: tests updated — names like `log-analyzer`, `widget-creator`, `skill-builder` all pass
- [x] Bug 4: builder_skill.md Step 3 mentions conftest.py with sys.path setup
- [x] Bug 5: validate_structure.py handles directory input (auto-finds SKILL.md or suggests fix)
- [x] Bug 5: tests for directory input added
- [x] All existing tests still pass (76 skill-builder + 81 cli-tool-builder = 157)
- [x] builder_skill.md stays under 500 tokens (1950 chars ≈ 488 tokens)
