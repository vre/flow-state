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

## Dev Skills from flow-jigs

Builder and session skills live in [flow-jigs](https://github.com/vre/flow-jigs). Install via marketplace:
```bash
/plugin marketplace add vre/flow-jigs
/plugin install builder-skill@flow-jigs
```

Or symlink locally for development:
```bash
ln -s /path/to/flow-jigs/session-claude .claude/skills/session-claude
ln -s /path/to/flow-jigs/builder-skill .claude/skills/builder-skill
# etc.
```

Dev skill symlinks are gitignored — they won't push to the repo.

## Local Plugin Installation Behavior

### Files Are Referenced In Place

When installing marketplace from local directory (`/plugin marketplace add /xxx/flow-state`):

1. **Files referenced in place** - Claude reads directly from source directory
2. **No copying to `.claude` directory** - unlike GitHub plugins which are cloned to cache
3. **Changes are immediate** - edit files and they're live, no reinstall needed
4. **Perfect for development** - iterative workflow

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
5. For prompt-only workflow changes:
   - run interactive extraction regression checks
   - verify context/token behavior with historian session inspection
