# Development - Local Plugin Installation Behavior

## Files Are Referenced In Place

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
/plugin marketplace add $(PWD)
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
