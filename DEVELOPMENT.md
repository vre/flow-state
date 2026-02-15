# Development

## Project-Level Development Setup

When developing this project, skills and MCP servers point directly to local directories:

**Skills** (`.claude/skills/`):
```
youtube-to-markdown -> ../../youtube-to-markdown  (symlink)
```

**MCP Servers** ('.mcp.json'):
```json
{
  "mcpServers": {
    "imap-stream": {
      "command": "uv",
      "args": ["--directory", "./imap-stream-mcp", "run", "imap-stream"]
    }
  }
}
```

This setup ensures:
- Always using latest development version
- No reinstall needed after changes
- Same pattern for both skills and MCP servers

Note: Each sub-project (e.g., 'imap-stream-mcp') also has its own '.mcp.json' with `${CLAUDE_PLUGIN_ROOT}` for standalone installation.

## Local Plugin Installation Behavior

### Files Are Referenced In Place

When installing marketplace from local directory (`/plugin marketplace add /xxx/flow-state`):

1. **Files referenced in place** - Claude reads directly from source directory
2. **No copying to `.claude` directory** - unlike GitHub plugins which are cloned to cache
3. **Changes are immediate** - edit files and they're live, no reinstall needed
4. **Perfect for development** - iterative workflow

## GitHub Marketplace vs Local Directory

**GitHub marketplaces:**
- Files copied via git clone to `~/.claude/plugins/cache/`
- Must update/reinstall to get changes

**Local directories:**
- Direct path reference, no copy
- Changes immediately available

## Development Workflow

### Local testing

```bash
/plugin marketplace add "$PWD"
/plugin install youtube-to-markdown@flow-state
```

### Validation

```bash
claude plugin validate .
```

### Iterative Development

1. Add local marketplace: `/plugin marketplace add /xxx/flow-state`
2. Install plugin: `/plugin install youtube-to-markdown@flow-state`
3. Edit scripts/SKILL.md in `/xxx/flow-state/youtube-to-markdown/`
4. Changes are live (may need Claude reload)
5. Test, iterate, repeat

## Release Checklist

When releasing a plugin update from a worktree branch:

1. Update docs in root + affected plugin directory:
   - `README.md`
   - `DEVELOPMENT.md`
   - `TESTING.md`
   - `TODO.md`
   - `CHANGELOG.md` (where present)
2. Bump versions consistently:
   - `.claude-plugin/marketplace.json` (`metadata.version` and plugin `version`)
   - `<plugin>/pyproject.toml`
   - `<plugin>/CHANGELOG.md`
3. Rebase branch before merge:
   - `git pull --rebase origin main`
4. Validate after rebase:
   - run tests for affected plugin(s)
   - run lints/checks for changed files

## LLM Agent Development Guidelines

For comprehensive guidance on building Skills, MCPs, CLI tools, and instruction files:

- [docs/Designing Initial Project Setup.md](docs/Designing%20Initial%20Project%20Setup.md) - Setting up projects for LLM-assisted development
- [docs/Designing AGENTS.md.md](docs/Designing%20AGENTS.md.md) - Instruction engineering (Context Engineering, Psychology)
- [docs/Designing Skills.md](docs/Designing%20Skills.md) - Writing robust workflows (Skill vs Script)
- [docs/Designing MCP Servers.md](docs/Designing%20MCP%20Servers.md) - Tool interfaces (Token Economics)
- [docs/Designing CLI Tools.md](docs/Designing%20CLI%20Tools.md) - CLI tools for humans and LLMs
- [docs/Designing Hooks.md](docs/Designing%20Hooks.md) - Lifecycle hooks (Security, Observability)
