# HTML Email Support via Markdown

## Goal
Enable HTML-formatted email drafts. Claude writes markdown, server converts to HTML + plain text.

## Research

### Example files location
`docs/research/`
- `Formatting test Gmail.eml` - Gmail's HTML + plain text output
- `Formatting test Thunderbird.eml` - Thunderbird's HTML + plain text output
- Screenshots: rendering in Gmail, Mac Mail, Outlook, Thunderbird (dark/light)

### Pre-markdown plain text syntax comparison

Example emails were created using Gmail and Thunderbird toolbar formatting tools. Not all Thunderbird fonts were tested - it uses the system fontset which likely won't render correctly in clients without the same fonts (fonts are not embedded in emails).

| Format | Gmail plain | Thunderbird plain | Markdown |
|--------|-------------|-------------------|----------|
| Bold | `*Bold*` | `*Bold*` | `**Bold**` |
| Italic | `*Italic*` | `/Italic/` | `*Italic*` |
| Underline | `*Underlined*` | `_Underlined_` | (not supported) |
| Bold+Italic | `*Bold and Italic*` | `/*Bold and Italic*/` | `***text***` |
| Strikethrough | (plain) | (plain) | `~~text~~` |
| Link | `Link <http://url>` | `Link` | `[Link](url)` |
| Ordered list | `1. item` | `1. item` | `1. item` |
| Unordered list | `- item` | `* item` | `- item` |
| Quote | (plain) | (plain) | `> quote` |
| Heading | (plain) | indented | `# Heading` |
| HR | (none) | `----...` | `---` |

### What survives / is lost
**Preserved in HTML:** bold, italic, underline, colors, fonts, sizes, alignment, lists, links, tables, hr
**Lost in plain text:** fonts, sizes, colors, alignment (only structure remains)

### Library search
No library found for markdown → pre-markdown. Options:
1. Markdown as-is for plain text
2. Custom conversion (~20 lines)
3. strip-markdown (loses everything)

## Decisions

### Supported markdown subset

| Markdown | HTML |
|----------|------|
| `**bold**` | `<strong>` |
| `*italic*` | `<em>` |
| `~~strike~~` | `<del>` |
| `# - ######` | `<h1>-<h6>` |
| `- item` | `<ul><li>` |
| `1. item` | `<ol><li>` |
| `> quote` | `<blockquote>` |
| `[text](url)` | `<a href>` |
| `---` | `<hr>` |

**Not supported:** underline, colors, fonts, sizes, alignment, tables, images

### Plain text format
Convert markdown to pre-markdown conventions (Gmail style):
- `**bold**` → `*bold*`
- `*italic*` → `*italic*` (unchanged)
- `[text](url)` → `text <url>`
- `~~strike~~` → plain text (markers removed)
- Lists, quotes, headings: keep as-is

### Format option
- **format: "markdown"** (default) → markdown → HTML + pre-markdown plain text
- **format: "plain"** → no conversion, text/plain only (no HTML)

## Implementation

### 1. Dependency
```bash
uv add markdown
```

### 2. imap_client.py
`create_draft()` ja `modify_draft()`:
```python
def create_draft(..., html: Optional[str] = None):
    if html:
        msg.set_content(body)  # plain text
        msg.add_alternative(html, subtype='html')
    else:
        msg.set_content(body)  # plain only
```

### 3. streammail_mcp.py
Draft handler:
```python
import markdown

# payload: {"to": "...", "body": "...", "format": "markdown"|"plain"}
format_type = draft_data.get('format', 'markdown')

if format_type == 'markdown':
    html = markdown.markdown(body)
    result = create_draft(..., html=html)
else:
    result = create_draft(..., html=None)  # plain only
```

### 4. Help text
```
## Body Format
- format: "markdown" (default) - converts to HTML, plain text = markdown source
- format: "plain" - no HTML, plain text only
```

## Files
- `pyproject.toml`
- `imap_client.py`
- `streammail_mcp.py`

## Verification
1. Markdown draft: `{"body": "**bold** and *italic*", "format": "markdown"}`
   - Thunderbird: HTML renders correctly
   - View source: multipart/alternative with text/plain + text/html
2. Plain draft: `{"body": "plain text", "format": "plain"}`
   - Single part text/plain only
3. Default (no format): behaves as markdown

## Test Results & Learnings

### Dependencies added
- `markdown` - core CommonMark conversion
- `pymdown-extensions` - additional features (strikethrough, checkboxes, etc.)

### Python markdown library limitations
- Only supports core Markdown (Gruber's original spec)
- No strikethrough, checkboxes, or GFM features built-in
- Requires `pymdown-extensions` for extended syntax

### Extensions tested and selected

| Extension | Purpose | Status |
|-----------|---------|--------|
| `pymdownx.tilde` | ~~strikethrough~~ | ✓ works |
| `pymdownx.tasklist` | `- [ ]` checkboxes | ✓ works |
| `pymdownx.mark` | ==highlight== | ✓ works (Outlook: ✗) |
| `pymdownx.betterem` | smarter bold/italic | ✓ works |
| `pymdownx.emoji` | :smile: → 😄 | ✓ works (needs `emoji.to_alt` for Unicode) |
| `pymdownx.smartsymbols` | (c)→© arrows | ✗ skipped - syntax not intuitive |

### Emoji configuration
Default emoji output uses CDN images (`<img src="cloudflare...">`) which triggers "remote content blocked" in Thunderbird. Fix: configure `emoji_generator: emoji.to_alt` for Unicode output.

### Markdown preprocessing needed
Markdown requires blank line before block elements (lists, blockquotes, headings, code blocks). Added `preprocess_markdown()` to auto-insert blank lines.

### Plain text conversion (markdown_to_plain)

| Markdown | Plain text | Notes |
|----------|------------|-------|
| `**bold**` | `*bold*` | Gmail style, universal pre-markdown convention |
| `*italic*` | `*italic*` | unchanged, universal convention |
| `~~strike~~` | `strike` | markers stripped |
| `==highlight==` | `highlight` | markers stripped |
| `:emoji:` | 😄 | Unicode (converted before plain) |
| `- [ ]` | `- [ ]` | unchanged |
| `[text](url)` | `text <url>` | Gmail style |

### Screen reader accessibility research
**Why strip `~~` and `==` markers:**
- JAWS (40% primary, 60% commonly used per [WebAIM 2024](https://webaim.org/projects/screenreadersurvey10/)) reads symbols with higher verbosity
- Would read "tilde tilde strike tilde tilde" - poor UX
- NVDA default is silent, but users with higher verbosity would hear markers
- Stripping markers gives clean "strike" / "highlight" for all users

**Why keep `*` for bold/italic:**
- Universal pre-markdown convention from 1980s Usenet
- Short if verbalized: "star bold star"
- Thunderbird uses `/italic/` but problematic (URLs trigger false italics)
- Gmail uses `*` for both bold and italic

### MCP help text
Kept minimal - one line listing supported features:
```
Supports: **bold**, *italic*, ~~strike~~, ==highlight==, :emoji:, `- [ ]` checkboxes, lists, headings, links, blockquotes
```
