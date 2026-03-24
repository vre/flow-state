# Builder-project v2: Complete project scaffolding

## Intent

Generated projects should match the development process defined in CLAUDE.md from the start — no manual post-creation fixups. Plugin scaffolding should be opt-in, not default for non-skill types.

## Goal

`build_project.py` produces a complete project structure with all process-required directories and files. `.claude-plugin/` only appears for plugin projects. Skill linking is handled interactively by the SKILL.md workflow, not the script.

## Situational Context

- `create_base()` currently creates `docs/plans/` but not `docs/research/` or `docs/reflections/`
- `.claude-plugin/marketplace.json` is created unconditionally in `create_base()` AND in each type-specific creator (`create_skill`, `create_mcp`, `create_cli`)
- Embedded `CLAUDE_MD` template references `docs/plans/` but not `docs/research/`, `docs/reflections/`, `TODO.md`, or `ARCHITECTURE.md`
- `SKILL.md` step 3 and `README.md` state all types get `marketplace.json`
- Existing unit tests (57 passing in `tests/builder-project/test_build_project.py`) assert current marketplace.json behavior
- Integration tests (`tests/integration/test_builder_pipeline.py`) are non-hermetic (call `uv sync` → PyPI)
- Only `builder-cli-tool` calls `build_project.py` directly (SKILL.md line 18: `python3 ./project-builder/project_builder/build_project.py cli ${NAME} <dir>`). It does not pass `--plugin` — will get non-plugin scaffold by default after this change. `mcp-builder` and `skill-builder` do not call `build_project.py`.

## Constraints

- `build_project.py` is non-interactive — all interactive behavior belongs in SKILL.md
- `builder-cli-tool` calls `build_project.py` directly (SKILL.md line 18). `mcp-builder` and `skill-builder` do not call it directly — they operate on existing projects or generate independently
- Symlinks to sibling skills are not portable across checkouts — must be local-only (gitignored)
- Git `.gitignore` semantics: `.claude/*` (wildcard) ignores contents without ignoring the directory itself, allowing `!.claude/settings.json` to work. `.claude/` (trailing slash) would block all un-ignore rules for files within

## Design Decisions

**`.gitignore` pattern for `.claude/`:**

Git requires un-ignoring parent directories before files within them. The correct pattern:

```gitignore
# Claude Code — ignore ephemeral, keep shared config
.claude/*
!.claude/settings.json
```

Using `.claude/*` (not `.claude/`) ignores contents but not the directory itself. This allows `!.claude/settings.json` to work. `.claude/skills/`, `.claude/projects/`, `.claude/settings.local.json` etc. remain ignored by the wildcard.

Note: `.claude/skills/.gitkeep` will also be ignored. The directory is created by the script but is not tracked by git — each developer populates it locally.

**Plugin flag vs type:**
- `--plugin` flag on any type, rather than separate types
- Skills are always plugins (need marketplace.json) → `--plugin` implied for `skill` type
- `mcp` and `cli` default to non-plugin; `--plugin` adds `.claude-plugin/` scaffolding
- `--plugin` flag is threaded to `create_mcp()` and `create_cli()` only — `create_base()` is plugin-agnostic
- `create_skill()` ignores `--plugin` flag — it always creates plugin scaffolding

**Non-plugin MCP: `.mcp.json` handling:**
- Current `.mcp.json` template uses `${CLAUDE_PLUGIN_ROOT}` which is a plugin-specific variable
- Non-plugin MCP projects use `"--directory", "."` instead (relative to project root)
- Plugin MCP projects keep `${CLAUDE_PLUGIN_ROOT}` (resolved by Claude Code plugin system)
- `_mcp_json()` function receives `plugin: bool` parameter to select the right `--directory` arg. Overall `.mcp.json` shape (`{"mcpServers": {name: {...}}}`) is unchanged — only `args` array differs
- Manual acceptance step: after implementation, verify non-plugin MCP scaffold actually launches with `uv --directory . run <name>` from project root to confirm `"--directory", "."` resolves correctly

**Backwards compatibility with downstream builders:**
- Only `builder-cli-tool` calls `build_project.py` directly (without `--plugin`)
- After this change, it gets non-plugin scaffold — no `.claude-plugin/` directory
- This is **acceptable breakage**: builder-cli-tool produces standalone tools by default. If someone needs a plugin, they explicitly pass `--plugin`
- `builder-cli-tool/SKILL.md` should be updated in a follow-up to document `--plugin` option, but this plan does not modify it (out of scope)

**Skill linking:**
- `build_project.py` creates `.claude/skills/` directory only — no linking logic
- SKILL.md step 3 handles linking interactively (AskUserQuestion: scan siblings for SKILL.md, offer selection, create symlinks)
- Symlinks are local-only (gitignored) — each developer links their own skill set
- Validation: manual testing via SKILL.md workflow, not unit-testable

**CLAUDE_MD template:**
- Update embedded template to reference `docs/research/`, `docs/reflections/`, `TODO.md` in Plan Phase
- Add `ARCHITECTURE.md` reference to Merge Phase
- Note: the embedded template is a simplified version of the root CLAUDE.md — it does not need to replicate the full `docs/<plugin/core>/...` structure which is specific to this monorepo

## Acceptance Criteria

- [x] AC1: `docs/plans/`, `docs/research/`, `docs/reflections/` all created with `.gitkeep`
- [x] AC2: `TODO.md` created (stub: `# TODO`)
- [x] AC3: `ARCHITECTURE.md` created with `# Architecture` heading and instruction comment
- [x] AC4: `.claude/settings.json` created with `{}`
- [x] AC5: `.claude/skills/` directory created (not git-tracked — ignored by `.claude/*` pattern)
- [x] AC6: `.claude-plugin/marketplace.json` only created when `--plugin` flag is passed or type is `skill`
  - `create_base()`: no longer creates `.claude-plugin/`
  - `create_skill()`: always creates `.claude-plugin/` (skill implies plugin)
  - `create_mcp()` / `create_cli()`: create `.claude-plugin/` only when `plugin=True` param
- [x] AC7: `.gitignore` uses `.claude/*` pattern with `!.claude/settings.json` un-ignore
- [x] AC8: Embedded `CLAUDE_MD` template updated to reference `docs/research/`, `docs/reflections/`, `TODO.md`, `ARCHITECTURE.md`
- [x] AC9: `SKILL.md` updated:
  - Step 1: adds "Plugin?" question only for mcp/cli types (skill is always plugin, question not shown)
  - Step 2: passes `--plugin` flag to script when mcp/cli user selected "Yes"
  - Step 1 also captures `${OUTPUT_DIR}` (where project will be created)
  - Step 3: conditional marketplace.json fill (only when plugin). Skill linking: scan `${OUTPUT_DIR}` for sibling directories containing SKILL.md (project is at `${OUTPUT_DIR}/${NAME}`, siblings are other dirs under `${OUTPUT_DIR}`). If ≤4 found, offer selection via AskUserQuestion with multi-select. If >4 found, list them and ask user to enter exact directory names (free text, comma-separated, whitespace trimmed; unknown name → error, re-prompt; empty input or `none` → skip linking). Selected sibling directories (not SKILL.md files) symlinked into `.claude/skills/` as relative symlinks. If symlink already exists, skip (no overwrite). If no siblings found, skip question silently.
- [x] AC10: `README.md` updated: generated structure description reflects conditional plugin, new directories
- [x] AC11: `dry_run_report()` reflects all new files and conditional plugin files
- [x] AC12: Non-plugin MCP `.mcp.json` has exact shape `{"mcpServers": {name: {"command": "uv", "args": ["--directory", ".", "run", name]}}}`. Plugin variant: same shape with `"${CLAUDE_PLUGIN_ROOT}"` replacing `"."`
- [x] AC13: Project root created at `${OUTPUT_DIR}/${NAME}` for all type variants
- [x] AC14: All existing tests updated and passing, new tests cover new behavior

## Testing Strategy

**Unit tests** (`tests/builder-project/test_build_project.py`):
- See task 15 for full test list (base files, plugin flag, gitignore, mcp.json, dry-run, main() paths)
- Modified: any existing test that asserts `.claude-plugin/marketplace.json` for non-skill types (task 14)

**Manual validation** (tasks 16-18):
- SKILL.md full workflow: 3 type variants (skill, mcp no-plugin, cli with-plugin) + OUTPUT_DIR verification
- SKILL.md skill-linking: 4 edge cases (happy path ≤4, no-overwrite, no-siblings, >4 exact-name)
- Non-plugin MCP launch: `uv --directory . run <name>` from generated project root

## Out of Scope

- LSP plugin installation/configuration (separate initiative)
- QMD integration (global tool, not per-project)
- CodeGraphContext integration
- Updating downstream builder skills — only `builder-cli-tool` directly calls `build_project.py`. It will produce non-plugin CLI scaffold by default, which is correct. Follow-up to document `--plugin` option in its SKILL.md.
- Full parity with root CLAUDE.md process (the embedded template is deliberately simplified for standalone projects)

## Tasks

- [x] 1. Add `docs/research/`, `docs/reflections/` with `.gitkeep` to `create_base()`
- [x] 2. Add `TODO.md` stub to `create_base()`
- [x] 3. Add `ARCHITECTURE.md` stub to `create_base()`
- [x] 4. Add `.claude/settings.json` (`{}`) and `.claude/skills/` to `create_base()`
- [x] 5. Update `.gitignore` template: `.claude/*` with `!.claude/settings.json`
- [x] 6. Add `--plugin` flag to argparse, pass `plugin: bool` to `create_mcp()` and `create_cli()` (not `create_base()`). For skill type, force `plugin=True` regardless of flag.
- [x] 7. Remove `.claude-plugin/` creation from `create_base()`, move to:
  - `create_skill()`: always (skill implies plugin)
  - `create_mcp()`: only when `plugin=True`
  - `create_cli()`: only when `plugin=True`
- [x] 8. Update `_mcp_json()` to accept `plugin: bool` — use `${CLAUDE_PLUGIN_ROOT}` when plugin, `"."` when not
- [x] 9. Update `dry_run_report()` to accept `plugin: bool`, reflect conditional plugin files and new directories
- [x] 10. Update embedded `CLAUDE_MD` template: add `docs/research/`, `docs/reflections/`, `TODO.md`, `ARCHITECTURE.md` references
- [x] 11. Update `build_project.py` module docstring header to include `[--plugin]` in usage line
- [x] 12. Update `SKILL.md`:
  - Step 1: add "Plugin?" discovery question for mcp/cli only (not shown for skill type). Add "Where should the project be created?" question → set `${OUTPUT_DIR}` (default: current directory)
  - Step 2: pass `--plugin` to script when mcp/cli user selected "Yes". Pass `${OUTPUT_DIR}` as output_dir argument.
  - Step 3: conditional marketplace.json fill (only when plugin). Skill linking: scan `${OUTPUT_DIR}` for sibling dirs with SKILL.md. ≤4 siblings → AskUserQuestion multi-select. >4 siblings → list and ask free text (comma-separated names). Symlink into `.claude/skills/` (relative). No overwrite. Skip if no siblings.
- [x] 13. Update `README.md`: generated structure reflects conditional plugin, new directories, `--plugin` flag in usage examples
- [x] 14. Update existing tests that assert unconditional marketplace.json
- [x] 15. Write new tests:
  - `test_base_creates_docs_subdirs`: `docs/research/`, `docs/reflections/` exist
  - `test_base_creates_todo_md`: `TODO.md` exists
  - `test_base_creates_architecture_md`: `ARCHITECTURE.md` exists
  - `test_base_creates_claude_dir`: `.claude/settings.json`, `.claude/skills/` exist
  - `test_base_no_marketplace`: `create_base()` does not create `.claude-plugin/`
  - `test_no_marketplace_without_plugin_flag`: mcp/cli without `--plugin` → no `.claude-plugin/`
  - `test_marketplace_with_plugin_flag`: `--plugin` → `.claude-plugin/marketplace.json` exists
  - `test_skill_implies_plugin`: skill type → `.claude-plugin/` exists without `--plugin`
  - `test_gitignore_claude_selective`: `.claude/*` present, `!.claude/settings.json` present. Behavioral: after `git init` + `git add`, verify `git check-ignore .claude/settings.json` exits non-zero (not ignored) and `git check-ignore .claude/skills/foo` exits zero (ignored)
  - `test_plugin_flag_argparse`: `--plugin` accepted by CLI parser
  - `test_mcp_json_non_plugin`: parse `.mcp.json`, assert exact shape `{"mcpServers": {name: ...}}` with `args` containing `"--directory", "."`
  - `test_mcp_json_plugin`: parse `.mcp.json`, assert same shape with `args` containing `"--directory", "${CLAUDE_PLUGIN_ROOT}"`
  - `test_dry_run_includes_new_base_files`: `--dry-run` output includes `TODO.md`, `ARCHITECTURE.md`, `.claude/settings.json`, `.claude/skills/`, `docs/research/`, `docs/reflections/`
  - `test_dry_run_mcp_no_plugin`: `--dry-run mcp` without `--plugin` → no `.claude-plugin/` in output
  - `test_dry_run_mcp_with_plugin`: `--dry-run mcp --plugin` → `.claude-plugin/` in output
  - `test_dry_run_cli_no_plugin`: `--dry-run cli` without `--plugin` → no `.claude-plugin/` in output
  - `test_dry_run_cli_with_plugin`: `--dry-run cli --plugin` → `.claude-plugin/` in output
  - `test_main_mcp_no_plugin`: `main()` with `init_git`, `init_uv`, `verify` mocked. mcp without `--plugin` → no `.claude-plugin/`
  - `test_main_mcp_with_plugin`: same mocking. mcp with `--plugin` → `.claude-plugin/` exists
  - `test_main_cli_no_plugin`: same mocking. cli without `--plugin` → no `.claude-plugin/`
  - `test_main_cli_with_plugin`: same mocking. cli with `--plugin` → `.claude-plugin/` exists
  - `test_dry_run_skill_implies_plugin`: `--dry-run skill` (no `--plugin` flag) → `.claude-plugin/` in output
  - `test_main_skill_implies_plugin`: `main()` with mocking. skill without `--plugin` → `.claude-plugin/` exists, JSON `"files"` output includes `.claude-plugin/marketplace.json`
  - `test_main_mcp_no_plugin_files_output`: `main()` with mocking. mcp without `--plugin` → JSON `"files"` output does NOT include `.claude-plugin/marketplace.json`
- [ ] 16. Manual validation: SKILL.md full workflow (3 type variants):
  - `skill` type: no "Plugin?" question shown, plugin scaffold created, project created in `${OUTPUT_DIR}`
  - `mcp` without plugin: "Plugin?" shown, answer No, no `.claude-plugin/`, project in `${OUTPUT_DIR}`
  - `cli` with plugin: "Plugin?" shown, answer Yes, `.claude-plugin/` created, project in `${OUTPUT_DIR}`
  - All variants: verify project appears at `${OUTPUT_DIR}/${NAME}` (not CWD or elsewhere)
- [ ] 17. Manual validation: SKILL.md skill-linking:
  - Happy path (≤4 siblings): create project with siblings containing SKILL.md → symlinks point to sibling directories (not SKILL.md files), links are relative
  - No overwrite: pre-create a symlink in `.claude/skills/` before running Step 3 → existing link unchanged, no error
  - No siblings: create project in empty dir → no linking question shown, no error
  - `>4` siblings: list shown, user enters exact directory names (comma-separated, whitespace trimmed). Unknown name → error message, re-prompt. Empty input or `none` → skip. Only valid names create symlinks.
- [ ] 18. Manual validation: non-plugin MCP launch — `uv --directory . run <name>` from generated project root
- [x] 19. Verify: all unit tests pass (`tests/builder-project/`). Integration tests (`tests/integration/test_builder_pipeline.py`) are non-hermetic (PyPI dependency) — run if network available, skip otherwise. `--dry-run` output correct for all type/plugin combinations.

## Files Changed

- `builder-project/project_builder/build_project.py` — core changes + docstring (tasks 1-11)
- `builder-project/SKILL.md` — steps 1, 2, 3 updated (task 12)
- `builder-project/README.md` — generated structure docs (task 13)
- `tests/builder-project/test_build_project.py` — test updates + new tests (tasks 14-15)

## Reflection

<!-- Written post-implementation by IMP -->
<!-- ### What went well -->
<!-- ### What changed from plan -->
<!-- ### Lessons learned -->
