# Plan: CLI Tool Builder Skill

**Created:** 2026-02-03
**Updated:** 2026-02-07 (incorporated competitor research + review feedback + cross-skill alignment)
**Status:** Draft - v1 scope defined
**Depends on:** `project-builder` (base scaffolding), aligns with `mcp-builder` (MCP contracts)
**Skill name:** `cli-tool-builder`
**Location:** Standalone skill (own directory), marketplace-ready

## Intent

Create a skill that guides the creation of CLI tools that serve multiple consumers:
1. **Humans** via terminal (`mytool list users`)
2. **LLM agents** directly (`Bash` tool calls)
3. **Skills** as scripts (`python3 ./scripts/mytool.py`)
4. **MCP servers** via separate entry point (`mytool-mcp`, stdio transport only for v1)

The skill produces one codebase, multiple interfaces.
User decides which interfaces to enable (CLI-only for humans/LLM/both, or CLI + MCP).

## Goal

The skill handles two modes:

**Mode A: New project** ("create a CLI tool for X")
1. Discover intent via brainstorming-style conversation (not rigid categories)
2. Delegate base scaffolding to `project-builder` (pyproject.toml, docs, tests, marketplace)
3. Generate CLI-specific files on top (cli.py, core.py, action tests)
4. Iterate: user adds logic, skill validates compliance

**Mode B: Existing project** ("add CLI patterns to this")
1. Audit what exists (entry points, arg parsing, output format, tests)
2. Identify gaps against CLI design doc
3. Add missing patterns without overwriting working code

**Philosophy:** One working iteration > complete plan that never ships. Init, implement, test, package are separate concerns — each revisitable.

## Constraints

### Python-Only, Minimal Dependencies
- **Python 3.10+** only (no Node.js/TypeScript option)
- **Prefer stdlib**: argparse, json, pathlib, dataclasses, typing, string.Template
- **Base install: zero external deps** - CLI-only mode uses stdlib only
- **Optional MCP extra** (`.[mcp]`):
  - `mcp` - Anthropic's official MCP SDK (includes FastMCP patterns)
  - `pydantic` - validation (comes with mcp)
- **Optional credential extra** (`.[keyring]`):
  - `keyring` - system credential storage
- **No transitive bloat**: Every dependency must be justified
- **Rationale**: Auditable code > npm dependency trees. Supply chain security.

**Configuration sources (priority order):**
1. CLI flags (`--token X`) — explicit, per-invocation
2. Environment variables (`MYTOOL_TOKEN`) — 12-factor, CI-friendly
3. `.env` file in project root — local dev convenience (simple KEY=VALUE parser, ~15 lines stdlib, skips comments/blank lines/`export` prefix)
4. Config file (`~/.config/mytool/config.json`) — persistent user prefs (JSON: stdlib, no tomllib needed)

**Note:** The `mcp` package (v1.0+) incorporates FastMCP's decorator-style API. References to "FastMCP" mean the patterns in the official SDK, not a separate package.

### From Designing CLI Tools.md
- POSIX conventions: `-v` verbose, `-q` quiet, `--format json|table`
- TTY detection: human format if terminal, JSON if piped
- Exit codes: 0=success, 1=error, 2=usage, 3=not found, 4=permission, 5=network
- Errors must suggest fix: `Error: missing <user-id>. Try: mytool list users`
- Stateless by default (all context per invocation)
- No interactive prompts without `--yes` escape hatch

### From Designing MCP Servers.md
- Single tool + action dispatcher (70% token savings)
- Help action for progressive documentation
- Liberal inputs, strict outputs (Postel's Law)
- Service-prefix naming (`mytool_do` not just `do`)
- Tool annotations: readOnlyHint, destructiveHint, idempotentHint

### From Designing Skills.md
- Minimize skill, maximize script
- Scripts self-documenting (validate args, print usage)
- Explicit outputs per step
- No logic duplication between skill and script

### From CLAUDE.md
- Tests before code
- Type hints throughout
- Google style docstrings
- Pure functions + thin main() glue

### Security (from competitor research)
- **stdout/stderr separation**: MCP stdio uses stdout for JSON-RPC only. All logs to stderr.
- **Command whitelisting**: For CLI-wrapping tools, support ALLOWED_COMMANDS pattern
- **Path validation**: Prevent traversal, resolve symlinks, validate base directory
- **No hardcoded paths**: Use env vars or config for all paths
- **Credential handling**: Never log credentials, prefer keyring over env vars for secrets
- **Destructive operations**: Require `--yes`/`--force` flag, document in help

## Architecture

```
mytool/
├── mytool.py           # Core logic (pure functions)
├── cli.py              # CLI entry point (argparse)
├── mcp_server.py       # MCP server (optional, via .[mcp])
├── mcp.json            # MCP server config (if MCP mode)
├── pyproject.toml      # Created by project-builder, patched by this skill (entry points, extras)
└── tests/
    ├── test_core.py    # Test per action (auto-generated)
    ├── test_cli.py     # CLI integration tests
    └── test_mcp.py     # MCP transport tests (if MCP mode)
```

**Note:** Base files (pyproject.toml, tests/, docs structure, marketplace.json) are generated by `project-builder`. This skill adds CLI-specific files on top.

**Key insight from research:** mcp-starter-template auto-generates `test_*.py` per tool. We do the same - one test file per action, with failing stubs (TDD).

### Separate Entry Points (not flag-based)

```python
# cli.py - CLI entry point
def main():
    """CLI entry point. No MCP dependencies."""
    run_cli()

# mcp_server.py - MCP entry point (optional install)
def main():
    """MCP entry point. Requires .[mcp] extra."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        print("MCP mode requires: pip install mytool[mcp]", file=sys.stderr)
        sys.exit(1)
    run_mcp()
```

**Why separate entrypoints instead of `--mcp` flag:**
- Flag parsing via `"--mcp" in sys.argv` bypasses argparse validation
- Confuses `--help` output
- Mixes concerns (CLI vs server mode)
- Separate entrypoint is explicit and MCP-config-friendly

### Result Type

```python
@dataclass
class Result:
    data: Any = None           # Payload (list, dict, str)
    error: str | None = None   # Error message if failed
    exit_code: int = 0         # CLI exit code (0-5)
    metadata: dict | None = None  # Optional (count, truncated, etc.)

    @property
    def ok(self) -> bool:
        return self.error is None
```

### Action Dispatcher (shared by CLI and MCP)

```python
# mytool.py - Core logic
ACTIONS = {
    "list": list_items,
    "get": get_item,
    "create": create_item,
    "delete": delete_item,
    "help": show_help,
}

def dispatch(action: str, **kwargs) -> Result:
    """Single dispatcher for both CLI and MCP."""
    if action not in ACTIONS:
        return Result(error=f"Unknown action '{action}'. Valid: {list(ACTIONS)}")
    return ACTIONS[action](**kwargs)
```

### Output Format Handling (stdlib only)

```python
def format_output(result: Result, fmt: str = "auto") -> str:
    """Format result for output. No external dependencies.

    Args:
        result: Action result
        fmt: "json", "table", or "auto" (detect TTY)
    """
    if fmt == "auto":
        fmt = "table" if sys.stdout.isatty() else "json"

    if fmt == "json":
        return json.dumps(result.data, indent=2)
    elif fmt == "table":
        return _simple_table(result.data)  # stdlib implementation
    # etc.

def _simple_table(data: list[dict]) -> str:
    """Simple table formatter using only stdlib."""
    if not data:
        return ""
    headers = list(data[0].keys())
    widths = {h: max(len(h), max(len(str(row.get(h, ""))) for row in data)) for h in headers}
    header_line = " | ".join(h.ljust(widths[h]) for h in headers)
    separator = "-+-".join("-" * widths[h] for h in headers)
    rows = [" | ".join(str(row.get(h, "")).ljust(widths[h]) for h in headers) for row in data]
    return "\n".join([header_line, separator] + rows)
```

## Skill Workflow

### Step 0: Check if CLI is needed

Not everything needs a scaffolded CLI project. Skip this skill if:
- One-liner transform → use a shell alias or simple script
- Single function → just write the function, no project scaffold
- Already have a working script → don't over-engineer

**Gate:** If task can be done with <50 lines of code, suggest writing it directly instead.

### Step 1: Discover Intent (brainstorming-style)

Open-ended discovery, not rigid categories. Key questions:
- What problem does this solve? Who uses it?
- What are the 3-5 core operations?
- What data does it work with? (files, APIs, local state, other CLIs)
- Does it need MCP mode? (defer if unclear)
- New project or existing code?

Use brainstorming patterns to surface hidden assumptions. Domain categories (API client, data processor, CLI wrapper, system utility) emerge from answers — don't force upfront.

### Step 2: Scaffold (new) or Audit (existing)

**New project:**
```bash
# 1. Base scaffolding via project-builder
python3 ./project-builder/project_builder/build_project.py cli ${TOOL_NAME} ${OUTPUT_DIR}

# 2. CLI-specific files on top
python3 ./scripts/generate_cli.py \
  --name "${TOOL_NAME}" \
  --operations "${OPERATIONS_JSON}" \
  --output "${OUTPUT_DIR}"
```

**Existing project:**
```bash
python3 ./scripts/audit_cli.py "${PROJECT_DIR}"
# Reports: missing patterns, non-compliant exit codes, etc.
```

Output:
- Tests for each operation (failing, TDD style)
- Security helpers if tool wraps external CLIs or handles file paths

### Step 3: Implement Operations

User implements core logic. Skill validates:
- [ ] All tests pass
- [ ] Exit codes follow spec
- [ ] Error messages suggest fixes
- [ ] Help action returns valid docs

### Step 4: MCP Integration (optional)

If user wants MCP mode:
```bash
python3 ./scripts/add_mcp_mode.py "${OUTPUT_DIR}/${TOOL_NAME}"
```

Adds:
- `mcp_server.py` aligned with mcp-builder contracts (single-tool, help action, error format)
- `mcp.json` server config
- Entry point `mytool-mcp` in pyproject.toml
- Optional `.[mcp]` extra in pyproject.toml

## Acceptance Criteria

### CLI Compliance
- [ ] Generated CLI follows POSIX conventions
- [ ] `--format json|table` works correctly
- [ ] TTY detection auto-selects format
- [ ] Exit codes match spec (0-5)
- [ ] Errors include actionable suggestions
- [ ] Help action provides documentation
- [ ] Tool works with `uv run`

### MCP Compliance (when `.[mcp]` installed)
- [ ] Separate `mytool-mcp` entry point works
- [ ] Single tool with action dispatcher
- [ ] **No stdout pollution** - static check: no `print()` without `file=stderr`
- [ ] Lazy import fails helpfully if mcp not installed

### Test Generation
- [ ] Test file generated with per-action test classes (`test_core.py`)
- [ ] Tests are failing stubs (TDD style)
- [ ] CLI integration test generated (`test_cli.py`)
- [ ] MCP transport test generated (if MCP mode)

### Security
- [ ] Destructive actions require `--yes` flag
- [ ] No hardcoded paths in generated code
- [ ] Path validation helper included (for "Data processor" domain)
- [ ] Command whitelisting helpers included (for "CLI wrapper" domain only)
- [ ] Credentials: env var pattern, never logged

### Existing Project Audit (v2)
- [ ] `audit_cli.py` reports: missing POSIX flags, wrong exit codes, no TTY detection, stdout pollution
- [ ] Output: checklist of gaps with file:line references
- [ ] No modifications — report only, user decides what to fix

### Dependencies
- [ ] **Zero non-essential dependencies** (only mcp, pydantic for MCP mode)
- [ ] CLI-only mode works with **stdlib only**
- [ ] `validate_tool.py` checks dependency count

## Validation

### Automated Validation Script

```bash
python3 ./scripts/validate_tool.py "${OUTPUT_DIR}/${TOOL_NAME}"
```

**Checks performed:**
- [ ] Exit codes: 0 on success, 2 on bad args, non-zero on error
- [ ] Error messages contain actionable suggestions
- [ ] Help output exists and is valid
- [ ] No stdout output when --quiet flag used
- [ ] MCP mode: stderr only for logs (no stdout pollution)
- [ ] No hardcoded paths in source files
- [ ] Dependency count within limits

### Manual Testing

```bash
# CLI mode
uv run mytool list
uv run mytool list --format json
uv run mytool list --quiet && echo "exit: $?"
echo '{}' | uv run mytool list  # piped = JSON output

# Error handling
uv run mytool invalid-action  # should exit 2, suggest valid actions

# MCP mode (if .[mcp] installed)
uv run mytool-mcp  # starts stdio server

# MCP without deps (should fail helpfully)
pip install mytool  # base only
uv run mytool-mcp   # should say "requires pip install mytool[mcp]"
```

### Test with Claude

```bash
claude -p "use mytool to list items"
```

## Examples to Study

### Internal (this repo)
- **imap-stream-mcp**: Single-tool MCP pattern, action dispatcher, help system
- **youtube-to-markdown**: Script-based skill, numbered scripts, CLI patterns

### External (from research)
- **[cli-mcp-server](https://github.com/MladenSU/cli-mcp-server)**: Security whitelisting pattern (ALLOWED_COMMANDS, path validation)
- **[mcp-starter-template](https://github.com/StevenStavrakis/mcp-starter-template)**: Auto-generates test files per tool
- **[claude-code-skill-factory](https://github.com/alirezarezvani/claude-code-skill-factory)**: Interactive Q&A workflow, validation commands
- **[gh-mcp](https://github.com/munch-group/gh-mcp)**: CLI wrapper pattern (wraps `gh` as MCP)

## Decisions Made

1. **Skill name**: `cli-tool-builder` (noun form, matches `mcp-builder` style)

2. **Location**: Standalone skill directory, not under document-skills/
   - Can share marketplace with other standalone tools
   - Independent versioning

3. **MCP mode entry**: Separate `mytool-mcp` entry point only (no `--mcp` flag)
   - Flag-based switching bypasses argparse, confuses help output
   - Separate entry is explicit and MCP-config-friendly
   - Lazy import fails helpfully if `.[mcp]` extra not installed

4. **Authentication**: Env vars required, keyring optional helper
   - Follows 12-factor app principles
   - Optional keyring setup script (like imap-stream-mcp)

5. **State**: Stateless default, defer session support
   - Start simple, add if patterns emerge

6. **Stdlib over packages**: Use Python stdlib where sufficient
   - `argparse` not click/typer
   - `json` not orjson
   - `dataclasses` not attrs
   - `pathlib` not pathtools
   - `logging` not loguru
   - `unittest`/`pytest` (pytest is acceptable dev dep)
   - Custom `_simple_table()` not tabulate/rich

7. **Discovery via brainstorming, not rigid Q&A**:
   - Open-ended conversation to surface intent and hidden assumptions
   - Domain categories emerge from answers, not forced upfront
   - Generate after enough is known to produce a working skeleton

8. **Test-first generation**: Imitate mcp-starter-template
   - Generate test file per action with failing stubs
   - User implements to make tests pass (TDD)
   - Validation script checks test coverage

9. **Scope boundary with mcp-builder skill**:
   - `cli-tool-builder`: CLI-first tools that *optionally* add MCP mode
   - `mcp-builder`: MCP-first servers (no CLI mode)
   - This skill owns the thin MCP wrapper for CLI tools, not full MCP server design
   - MCP wrapper must align with mcp-builder contracts (single-tool, help action, error format)

10. **Soft dependency on project-builder**:
    - If `project-builder` available: use it for base scaffolding, then layer CLI files
    - If not available: `generate_cli.py` creates everything (standalone mode)
    - No duplication: detect existing pyproject.toml and patch it, or create if missing

11. **New vs existing project support**:
    - New: delegate to project-builder, then layer CLI patterns
    - Existing: audit + gap analysis, add missing patterns only

## Directory Structure

```
cli-tool-builder/
├── SKILL.md                    # Main skill entry
├── marketplace.json            # Marketplace metadata
├── pyproject.toml              # For script dependencies
├── scripts/
│   ├── generate_cli.py         # Generates CLI skeleton (on top of project-builder)
│   ├── audit_cli.py            # Audits existing project for CLI compliance
│   ├── add_mcp_mode.py         # Adds MCP wrapper to existing CLI
│   └── validate_tool.py        # Validates generated tool
├── templates/                      # stdlib string.Template (no Jinja2)
│   ├── cli.py.tmpl                 # CLI entry point template
│   ├── core.py.tmpl                # Core logic template
│   ├── pyproject.toml.tmpl         # CLI-specific pyproject
│   ├── test_core.py.tmpl           # Per-action test classes (TDD stubs)
│   ├── test_cli.py.tmpl            # CLI integration tests
│   └── security_helpers.py.tmpl    # Path validation (conditional, domain-based)
├── subskills/
│   ├── discover_intent.md      # Step 1: Brainstorming-style discovery
│   ├── generate_skeleton.md    # Step 2: Scaffold new or audit existing
│   ├── implement_guide.md      # Step 3: Implementation guidance
│   └── add_mcp.md              # Step 4: Optional MCP mode (v2)
└── tests/
    └── test_generation.py      # Tests for the generators
```

## Implementation Order

### v1 (this iteration)
1. Create skill structure (SKILL.md, scripts/)
2. Write templates using `string.Template` (stdlib, no Jinja2)
3. Write `generate_cli.py` — standalone skeleton generator (creates or patches pyproject.toml)
4. Write `validate_tool.py` — static checks (exit codes, no stdout pollution, deps)
5. Test with sample domain (e.g., bookmark manager)
6. Add marketplace.json

### v2 (separate iteration)
1. Write `audit_cli.py` — checks existing project for CLI compliance gaps
2. Write `add_mcp_mode.py` — adds MCP wrapper (optional, behind `.[mcp]`)

**v1 scope:** `generate_cli.py` + `validate_tool.py`. Works standalone.
**v2 scope:** `audit_cli.py` (existing projects) + `add_mcp_mode.py` (MCP add-on).
**Soft dep:** Prefers `project-builder` for scaffolding if available, works without it.

## Security Patterns

See [Designing CLI Tools.md §10](../../../docs/Designing%20CLI%20Tools.md) for credential handling, path validation, command whitelisting, and destructive operation patterns. Templates should implement these, not duplicate the documentation.

## References

### Internal
- [Designing CLI Tools.md](../../../docs/Designing%20CLI%20Tools.md)
- [Designing MCP Servers.md](../../../docs/Designing%20MCP%20Servers.md)
- [Designing Skills.md](../../../docs/Designing%20Skills.md)
- [imap-stream-mcp](../../../imap-stream-mcp/) - MCP pattern example
- [youtube-to-markdown](../../../youtube-to-markdown/) - Skill pattern example
- [CLI Builder Research](./2026-02-03-cli-builder-research.md) - Competitor analysis

### External (security)
- [MCP Security Survival Guide](https://towardsdatascience.com/the-mcp-security-survival-guide-best-practices-pitfalls-and-real-world-lessons/)
- [Simon Willison on MCP Prompt Injection](https://simonwillison.net/2025/Apr/9/mcp-prompt-injection/)
- [MCP Patterns & Anti-Patterns](https://medium.com/@thirugnanamk/mcp-patterns-anti-patterns-for-implementing-enterprise-ai-d9c91c8afbb3)

## Post-Integration: Cross-Skill Alignment (2026-02-07)

After rebasing onto `builders` branch containing project-builder and skill-builder, these changes are needed:

### Concern Borders

- **project-builder** owns: directory structure, pyproject.toml (initial), dev infrastructure (ruff, pytest, git), CLAUDE.md
- **cli-tool-builder** owns: core.py, cli.py, action-specific tests, security helpers, exit codes, TTY detection, Result type
- **Integration**: cli-tool-builder REPLACES project-builder's cli.py stub with full template. LLM patches pyproject.toml to add optional-dependencies (`[mcp]`, `[keyring]`). project-builder's `assert True` test is REPLACED by cli-tool-builder's TDD stubs.

### 1. Rename `project-init` → `project-builder`

All references in plan body use `project-init` — the skill was renamed to `project-builder`.
Search-replace throughout: plan text, SKILL.md, subskills.

**Files:** plan (6 locations), SKILL.md, subskills/generate_skeleton.md

### 2. Fix project-builder invocation path

Plan shows `project-init --name "${TOOL_NAME}" --type cli` but actual invocation is:
```bash
python3 ./project-builder/project_builder/build_project.py cli ${NAME} <output_dir>
```

**Files:** plan line 231

### 3. Add `keywords:` to SKILL.md frontmatter

skill-builder's `validate_structure.py` requires `keywords` in frontmatter.

**Files:** cli-tool-builder/SKILL.md

### 4. SKILL.md: document both workflow paths

Current SKILL.md doesn't mention project-builder. Add:
- Path A (with project-builder): invoke project-builder first → cli-tool-builder layers on top
- Path B (standalone): generate_cli.py creates everything

**Files:** cli-tool-builder/SKILL.md

### 5. Template overlap: cli.py replacement

project-builder creates a minimal 30-line cli.py stub. cli-tool-builder's template is the real implementation (~90 lines with load_env, TTY detection, POSIX flags). Document that cli-tool-builder's output REPLACES the stub — this is by design (infra test → domain test progression).

**Files:** documentation only, no code change

### 6. Naming convention: `cli-tool-builder` is correct

skill-builder enforces gerund naming for generated skills. Builder skills themselves use `{noun}-builder` pattern: project-builder, skill-builder, mcp-builder, cli-tool-builder. This is intentional — builders are infrastructure, not workflow skills.

**Files:** skill-builder/scripts/validate_structure.py (gerund check should WARN for builder names, not FAIL)

### 7. pyproject.toml strategy

When project-builder already created pyproject.toml:
- generate_cli.py warns and skips (current behavior, correct)
- LLM adds optional-dependencies (`[mcp]`, `[keyring]`, `[dev]`) during implementation phase
- No programmatic TOML merge needed

When standalone (no project-builder):
- generate_cli.py creates full pyproject.toml from template (current behavior, correct)

**Files:** no code change, strategy documented here
