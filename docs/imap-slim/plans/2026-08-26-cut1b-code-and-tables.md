# Cut 1b: fenced code blocks and tables

Frame: `2026-08-24-frame-imap-slim-cli-daemon.md`. Split out of cut 1 on 2026-08-26.
Runs after `2026-08-26-cut1a-body-contract-visible.md`. **Not yet planned in detail** — this file
records why it is separate and what the measurements say, per the one-cut-at-a-time rule.

## Why this is not "add two extensions"

HC asked for code blocks and tables. Neither is supported today: `MARKDOWN_EXTENSIONS`
(`markdown_utils.py:14-20`) has no `fenced_code` and no `tables`, so a fence renders as an inline
code span and a pipe table renders as literal text.

Turning them on exposes four defects that are currently invisible precisely *because* the
extensions are off. All measured 2026-08-26:

```
1. preprocess_markdown has no fence state - it injects blank lines INTO fenced content

   preprocess_markdown("```\n#include\n- literal\n> literal\n```")
     -> '```\n\n#include\n\n- literal\n\n> literal\n\n```'
   rendered with fenced_code:
     -> '<pre><code>\n#include\n\n- literal\n\n&gt; literal\n\n</code></pre>'

2. markdown_to_plain runs its five substitutions over fenced content too

   body: '```\n**literal**\n~~literal~~\n==literal==\n[x](https://example.com)\n```'
   plain part: '```\n*literal*\nliteral\nliteral\nx <https://example.com>\n```'
   the text/plain alternative corrupts the user's code

3. autolink_urls is not HTML-aware

   '<pre><code>https://example.com</code></pre>'
     -> '<pre><code><a href="https://example.com">https://example.com</a></code></pre>'

4. tables need a preceding blank line, which nothing supplies

   'intro\n| a | b |\n|---|---|\n| 1 | 2 |'
     -> '<p>intro<br />| a | b |<br />|---|---|</p>'      not a table at all
```

There is a fifth, adjacent, which cut 1a pins as a known limitation and this cut should resolve:

```
5. consecutive blockquote lines are split into separate paragraphs

   preprocess_markdown('> first\n> second') -> '> first\n\n> second'
     -> '<blockquote><p>first</p><p>second</p></blockquote>'
   so nl2br cannot make a quoted line break, which cut 1a promises for paragraphs
```

## Shape of the work

- **`preprocess_markdown` becomes block-aware.** It must copy an opening fence through its matching
  closing fence unchanged, and stop treating each `>` line as a new block. Language-qualified
  fences, tilde fences if enabled, and an unterminated fence all need deciding.
- **The shield generalises from lines to regions.** Cut 1a shields marker-run *lines* in
  `markdown_to_plain`; this cut must shield whole fenced *regions* with the same collision-safe
  token scheme, including fences containing marker-run lines and sentinel-shaped text.
- **`autolink_urls` must skip `<pre>` and `<code>`**, or run before HTML generation.
- **Tables** need either a documented "blank line required" rule with a test, or preprocessing that
  recognises a header/separator pair.

## Do not start this

before cut 1a is merged: it rewrites `preprocess_markdown`, which cut 1a's marker-run shield sits
next to, and the two would conflict for no benefit.
