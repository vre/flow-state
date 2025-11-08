# Claude Code Marketplace Structure Reference

Research on Claude Code marketplace and plugin architecture.

## Official Documentation Sources

- **Plugin Development**: https://code.claude.com/docs/en/plugins.md
- **Plugin Reference**: https://code.claude.com/docs/en/plugins-reference.md
- **Plugin Marketplaces**: https://code.claude.com/docs/en/plugin-marketplaces.md

## Marketplace Structure Basics

### Hierarchy
```
Marketplace
└── Plugins (multiple)
    └── Skills/Commands/Agents/Hooks/MCPs (multiple per plugin)
```

**Key Point**: Users install at PLUGIN level, not individual skills. One plugin can bundle multiple related skills.

### Required Files

**Marketplace minimum:**
```
marketplace-repo/
└── .claude-plugin/
    └── marketplace.json
```

**Plugin minimum:**
```
plugin-folder/
└── .claude-plugin/
    └── plugin.json
```

## marketplace.json Schema

### Required Fields
```json
{
  "name": "marketplace-identifier",    // kebab-case, no spaces
  "owner": {
    "name": "Maintainer Name",
    "email": "email@example.com"
  },
  "plugins": [...]                     // Array of plugin entries
}
```

### Optional Metadata
```json
{
  "metadata": {
    "description": "Brief description",
    "version": "1.0.0",
    "pluginRoot": "./plugins"          // Base path for relative sources
  }
}
```

### Plugin Entry Structure

**Required:**
- `name`: Plugin identifier (kebab-case)
- `source`: Where to fetch plugin from

**Optional:**
- `description`, `version`, `author`, `homepage`, `repository`, `license`
- `keywords`, `category`, `tags`
- `strict`: true/false
- Component paths: `commands`, `agents`, `hooks`, `mcpServers`, `skills`

### Plugin Source Types

**Relative path** (same repository):
```json
{
  "name": "my-plugin",
  "source": "./plugins/my-plugin"
}
```

**GitHub repository**:
```json
{
  "name": "plugin",
  "source": {
    "source": "github",
    "repo": "owner/repo"
  }
}
```

**Git URL**:
```json
{
  "name": "plugin",
  "source": {
    "source": "url",
    "url": "https://gitlab.com/team/plugin.git"
  }
}
```

## plugin.json Schema

### Required
- `name`: Unique kebab-case identifier

### Metadata
- `version`: Semantic version
- `description`: Brief purpose
- `author`: Object with name, email, url
- `homepage`, `repository`, `license`
- `keywords`: Array of discovery tags

### Component Paths
All paths relative to plugin root, must start with `./`

- `commands`: String or array pointing to command files/directories
- `agents`: String or array for agent definitions
- `skills`: String or array for skill directories
- `hooks`: Path or inline JSON
- `mcpServers`: Path or inline MCP config

**Note**: Custom paths supplement, not replace, default directories. If `commands/` exists, it loads alongside custom paths.

## Directory Structure Patterns

### Example: Anthropic Skills Marketplace
```
anthropic-agent-skills/
├── .claude-plugin/
│   └── marketplace.json
├── document-skills/
│   ├── xlsx/
│   │   ├── SKILL.md
│   │   └── recalc.py
│   ├── docx/
│   ├── pptx/
│   └── pdf/
├── skill-creator/
├── mcp-builder/
└── ... more skills
```

marketplace.json defines 2 plugins:
- `document-skills` with skills: xlsx, docx, pptx, pdf
- `example-skills` with skills: skill-creator, mcp-builder, etc.

### Example: Superpowers Plugin
```
superpowers/
├── .claude-plugin/
│   └── plugin.json
├── skills/
│   ├── testing/
│   ├── debugging/
│   ├── collaboration/
│   └── meta/
├── commands/
├── agents/
└── hooks/
```

Single plugin with multiple skill categories.

## Distribution Methods

### 1. GitHub Direct
```bash
/plugin install github:username/plugin-name
```

### 2. Via Marketplace
```bash
/plugin marketplace add username/marketplace-repo
/plugin install plugin-name@marketplace-name
```

### 3. Local Development
```bash
/plugin marketplace add ./path/to/marketplace
```

## Real-World Examples

### superpowers-marketplace
```json
{
  "name": "superpowers-marketplace",
  "owner": {...},
  "plugins": [
    {
      "name": "superpowers",
      "source": {
        "source": "url",
        "url": "https://github.com/obra/superpowers.git"
      },
      "version": "3.4.1",
      "strict": true
    }
  ]
}
```

### anthropic-agent-skills
```json
{
  "name": "anthropic-agent-skills",
  "plugins": [
    {
      "name": "document-skills",
      "source": "./",
      "strict": false,
      "skills": [
        "./document-skills/xlsx",
        "./document-skills/docx",
        "./document-skills/pptx",
        "./document-skills/pdf"
      ]
    }
  ]
}
```

## Organization Strategies

### Option A: One plugin per skill
```
marketplace/
├── .claude-plugin/marketplace.json
└── skill-name/
    ├── .claude-plugin/plugin.json
    └── SKILL.md
```

### Option B: Grouped plugins by category
```
marketplace/
├── .claude-plugin/marketplace.json
├── category-one/
│   ├── .claude-plugin/plugin.json
│   ├── skill-a/
│   └── skill-b/
└── category-two/
    ├── .claude-plugin/plugin.json
    └── skill-c/
```

### Option C: Flat skill structure
```
marketplace/
├── .claude-plugin/marketplace.json
├── skill-a/SKILL.md
├── skill-b/SKILL.md
└── skill-c/SKILL.md
```

marketplace.json references skills directly.

## Component Types

- **Skills** - SKILL.md files with YAML frontmatter
- **Commands** - .md files in commands/
- **Agents** - Agent definitions
- **Hooks** - Event handlers
- **MCP Servers** - External tool integrations

## File Requirements

**Marketplace-level:**
- `.claude-plugin/marketplace.json` - Required
- `README.md` - Recommended
- `LICENSE` - Recommended

**Plugin-level:**
- `.claude-plugin/plugin.json` - Required if using plugin structure
- `README.md` - Recommended per plugin

**Skill-level:**
- `SKILL.md` - Required (with YAML frontmatter)
- Supporting scripts/files as needed

## Validation

Before publishing:
```bash
claude plugin validate .
```

## References

- Anthropic official skills: https://github.com/anthropics/skills
- Community examples: ccplugins/marketplace, Dev-GOM/claude-code-marketplace, obra/superpowers
