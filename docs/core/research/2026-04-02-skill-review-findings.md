# Skill Review Findings — 2026-04-02

Codex (gpt-5.4-high) reviewed all `builder-*` and `session-*` skill directories for: SKILL.md correctness, references/ relevance, scripts/ consistency, internal consistency. Issues only.

## builder-cli-tool

### High

1. **Dead bootstrap path**: SKILL.md:18 uses `./project-builder/project_builder/build_project.py`, but no `project-builder/` directory exists in this skill. The command fails from skill root.

2. **Broken doc links**: SKILL.md:47 links to `../../docs/writing-cli-tools.md` and `../../docs/writing-mcp-servers.md`. From the skill directory these resolve outside the repo. The actual file is `./references/writing-cli-tools.md`. There is no bundled `writing-mcp-servers.md` — that belongs to builder-mcp.

3. **Wrong generated layout docs**: SKILL.md:27 and `subskills/generate_skeleton.md:17` describe top-level `${NAME}.py` + `cli.py`, but the generator (`scripts/generate_cli.py:237`) creates `${NAME}/${NAME}/...` package structure.

4. **Flat mode broken**: SKILL.md:20 documents `--flat` generation, SKILL.md:22 sends users to `validate_tool.py`, but the validator (`scripts/validate_tool.py:225`) only accepts directories, not single `.py` files. Confirmed: `validate_tool.py /tmp/.../demo_tool.py` exits with usage error.

### Medium

5. **Domain flag dropped**: `subskills/discover_intent.md:18` defines domain categories, generator supports `--domain` (`scripts/generate_cli.py:249`, `:322`), but SKILL.md:19 and `subskills/generate_skeleton.md:11` never pass `--domain`. Collected but unused.

6. **pyproject.toml patch claim false**: `subskills/generate_skeleton.md:21` says existing `pyproject.toml` is patched. Generator only warns, does not patch (`scripts/generate_cli.py:255`).

### Low

7. **Dead internal refs in Designing CLI Tools.md**: Lines 3, 130, 550 reference `CLAUDE.md` and `Designing MCP Servers.md` that don't exist in skill directory or repo root.

---

## builder-mcp

### High

1. **Auth support hollow**: SKILL.md offers `none | env_var | keyring | oauth`. `oauth` not handled by generator at all. `env_var`/`keyring` produce a helper that is never called. `keyring` not added as dependency. References: SKILL.md:41, `scripts/generate_mcp.py:24,99,207`, `scripts/generate_pyproject.py:27`, `subskills/with_api.md:15`.

2. **Subskill variables undefined**: Parent skill sets `DOMAIN`, `TRANSPORT`, `ACTIONS_JSON`, `AUTH_METHOD`, `INSTRUCTIONS`. Both subskills require `DESCRIPTION`. `with_api.md` also requires `API_BASE_URL` and `first_action`. Not self-contained. References: SKILL.md:37,44, `subskills/minimal_mcp.md:8,16`, `subskills/with_api.md:8,22,24`.

3. **Wrong doc path**: SKILL.md:19 says `docs/writing-mcp-servers.md` — file is at `references/writing-mcp-servers.md`.

### Medium

4. **HTTP workflow inconsistent**: SKILL.md:54 requires `HOST`, `PORT`, `STREAMABLE_HTTP_PATH` in `.env.example`. Generators hardcode `transport="streamable-http"` and `http://localhost:${PORT}/mcp`; `HOST` and `STREAMABLE_HTTP_PATH` ignored. References: `scripts/generate_mcp.py:159`, `scripts/generate_packaging.py:18,41`.

5. **Keyring setup.py missing**: Generated server tells user to run `python setup.py`, but no `setup.py` is generated anywhere (`scripts/generate_mcp.py:123`).

### Low

6. **Validator misses TODOs**: Generator emits TODO action handlers, help text, tool title (`scripts/generate_mcp.py:44,52,64,91`). `scripts/validate_mcp.py:22` does not check for TODOs, so unfinished scaffold passes validation.

7. **Stale pointer in reference**: `references/Designing MCP Servers.md:3` references a `CLAUDE.md` section that doesn't exist.

---

## builder-project

### High

1. **Dead bootstrap path**: SKILL.md:51 uses `python3 ./project-builder/project_builder/build_project.py ...` — actual path is `./project_builder/build_project.py` (underscore, one level). Same error in README.md:22,37.

### Medium

2. **Inconsistent skill naming**: SKILL.md:75 and `project_builder/build_project.py:188` say `skill-builder`. `references/writing-claude-agents-md.md:207` says `building-skills`. Ambiguous next-step guidance.

3. **Cross-references not self-contained**: `references/writing-claude-agents-md.md:207` points to `docs/Designing Skills.md` and `docs/writing-skills.md` — don't exist in this skill directory. References should be self-contained or use relative paths that resolve.

### Low

4. **Designing Hooks.md role unclear**: SKILL.md, README.md, and generator don't reference it directly. Scaffold only writes empty `.claude/settings.json` (`project_builder/build_project.py:419`). If kept, role should be explicit in SKILL.md.

---

## builder-skill

### High

1. **edit_skill.md unexecutable**: `subskills/edit_skill.md:9` uses `${SKILL_DIR}`, `:39` uses `${SKILL_NAME}` — neither defined in edit flow. Route is dead.

2. **${SKILL_DIR} never collected**: `subskills/skill_only.md:14` and `subskills/builder_skill.md:17` require `${SKILL_DIR}`, but only name is collected. Scenario log confirms agents skip it (`scenarios/create-pr-review-skill.yaml:110`).

### Medium

3. **Description guidance contradicts**: `references/writing-skills.md:19` says trigger + output. `references/Designing Skills.md:87,108` says trigger-only. `scenarios/create-pr-review-skill.yaml:31` enforces trigger-only.

4. **Dead local links in references**: `references/writing-skills.md:156` → `docs/writing-model-specific-prompts.md` (missing). `references/Designing Skills.md:588,589,593` → missing sibling docs.

### Low

5. **Wrong directory name in scenarios**: `scenarios/README.md:7` and `scenarios/create-pr-review-skill.yaml:5` say `skill-builder/` — actual directory is `builder-skill`.

6. **Validator empty path**: `scripts/validate_structure.py:282` uses `skill_dir.name` which is empty when run from current directory, producing output `No test directory found for scripts in /`.

7. **Stale scenario record**: `scenarios/create-pr-review-skill.yaml:92` claims `skill_only.md` uses Sonnet — no model-selection instruction in `subskills/skill_only.md`.

---

## session-claude

### Medium

1. **Bash missing from --allowedTools**: SKILL.md:30,40,45,62 and README.md:15,17,33 describe Bash as available in worktree mode, but the actual `claude` command omits `Bash` from `--allowedTools`. Internally inconsistent.

2. **Error handling wrong**: SKILL.md:66,71 says detect errors via stderr. Actual Claude Code 2.1.81+ returns `is_error: true` in JSON on stdout with `result` and `session_id`. Callers following skill literally will miss failures.

---

## session-codex

### High

1. **--full-auto contradiction**: SKILL.md:10,17 direct-mode examples use `--full-auto`. README.md:7,81 says `--full-auto` sets `approval_policy="on-request"` which hangs in non-interactive use. The canonical commands reintroduce the documented failure mode.

### Medium

2. **JSON error handling incomplete**: SKILL.md:115 says "show stderr, STOP". `codex exec --json` also emits structured error events on stdout (`{"type":"error",...}`). Callers following literally miss failures.

### Low

3. **README hang explanation inconsistent**: README.md:46 says hangs are "known issue" only for out-of-sandbox commands. Earlier text (README.md:7) says root cause is `approval_policy="on-request"` in non-interactive mode. Statements don't align.

---

## session-gemini

### High

1. **Sandbox profile names broken**: SKILL.md:35,50 and README.md:21 use `permissive-closed` / `restrictive-closed`. Installed Gemini CLI 0.35.3 exposes `permissive-open`, `permissive-proxied`, `restrictive-open`, `restrictive-proxied`, `strict-open`, `strict-proxied` (verified in `sandboxUtils.js:14`). Worktree commands will fail.

### Medium

2. **Profile count mismatch**: SKILL.md:31 documents 5 profiles. README.md:15 documents 6. Named profiles don't match between them.

3. **Headless auth too narrow**: SKILL.md:27 and README.md:53 imply `GOOGLE_API_KEY` is required. Gemini CLI headless auth also accepts cached auth, `GEMINI_API_KEY`, or Vertex AI env vars. Source: [Gemini CLI auth docs](https://google-gemini.github.io/gemini-cli/docs/get-started/authentication.html).

---

## session-sandvault

### Medium

1. **Broken doc references**: README.md:63,71,127,128,129 reference `docs/core/research/...` files that don't exist in this skill directory.

2. **Missing script**: README.md:119 references `setup-profile-patch.sh` as required follow-up after `sv build`. Script doesn't exist in skill directory.

### Low

3. **Non-operative metadata**: SKILL.md:4 `allowed-tools: Bash` is not enforced by skill loader — implies enforcement that doesn't happen.

4. **README drift risk**: Operational guidance lives in README.md which skill loader doesn't read. Creates drift between SKILL.md (loaded) and README.md (not loaded).

---

## Cross-cutting patterns

1. **Doc path confusion**: Multiple skills reference `docs/...` paths that don't resolve from skill directory. After moving files to `references/`, internal references weren't updated (builder-mcp:3, builder-cli-tool:2).

2. **Variable contracts broken**: builder-skill and builder-mcp both define subskill variables in parent that don't match what subskills expect.

3. **Error handling stale**: session-claude and session-codex both have wrong error detection guidance for current CLI versions.

4. **Validation gaps**: builder-cli-tool flat mode and builder-mcp TODO stubs pass validators that shouldn't accept them.
