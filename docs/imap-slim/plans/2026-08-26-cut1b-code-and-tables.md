# Cut 1b: fenced code blocks and tables

Frame: `2026-08-24-frame-imap-slim-cli-daemon.md`. Runs after
`2026-08-26-cut1a-body-contract-visible.md`, which is merged.

Baseline: `cd tests && uv run --frozen pytest imap-slim-mcp/ -q` → **540 passed**.

## Intent

HC asked for code blocks and tables. Neither is supported: `MARKDOWN_EXTENSIONS`
(`markdown_utils.py:14-21`) has no `fenced_code` and no `tables`, so a fence renders as an inline
code span and a pipe table renders as literal text. Turning them on exposes four defects that exist
today but are invisible precisely *because* the extensions are off.

## Goal

A fenced block reaches the recipient as the author wrote it, in both the HTML and the plain
alternative. A pipe table renders as a table. And the newline promise cut 1a made for paragraphs
also holds inside a blockquote.

## Situational Context — every defect measured 2026-09-05

```
1. preprocess_markdown has no fence state, so it injects blank lines INTO fenced content
   preprocess_markdown("```\n#include\n- literal\n> literal\n```")
     -> '```\n\n#include\n\n- literal\n\n> literal\n\n```'
   with fenced_code that renders as
     -> '<pre><code>\n#include\n\n- literal\n\n&gt; literal\n\n</code></pre>'

2. markdown_to_plain runs its five substitutions over fenced content
   '```\n**literal**\n~~literal~~\n==literal==\n[x](https://example.com)\n```'
     -> '```\n*literal*\nliteral\nliteral\nx <https://example.com>\n```'
   the text/plain alternative corrupts the author's code

3. autolink_urls is not HTML-aware
   '<pre><code>https://example.com</code></pre>'
     -> '<pre><code><a href="https://example.com">https://example.com</a></code></pre>'

4. a table needs a preceding blank line and nothing supplies one
   'intro\n| a | b |\n|---|---|\n| 1 | 2 |'
     -> '<p>intro<br />| a | b |<br />|---|---|</p>'          not a table

5. consecutive blockquote lines are split into separate paragraphs
   preprocess_markdown('> first\n> second') -> '> first\n\n> second'
     -> '<blockquote><p>first</p><p>second</p></blockquote>'
   cut 1a pinned this with a test so this cut changes it deliberately
```

### Fence grammar, measured against python-markdown 2026-09-05

The helper must agree with the extension, not approximate it. Every row measured:

| input | is a code block | note |
|---|---|---|
| `` ```\nx\n``` `` at column 0 | yes | the only supported position |
| 2-space indented fence | **no** | renders as an inline code span |
| 4-space indented fence | no | becomes an *indented* code block containing literal backticks |
| 3 backticks open, 4 close | **no** | count must match exactly |
| 4 open, 3 close | **no** | |
| 4 open, 4 close | yes | |
| `` ```c# `` , `` ```foo.bar `` | yes | `#` and `.` are valid in a language tag |
| `` ```{.python #ex} `` | yes | attribute-list syntax is valid |
| `` ~~~ `` inside a backtick fence | content | and a trailing lone `~~~` is **not** a fence |
| closer with trailing spaces | yes | valid closer |
| closer carrying a language tag | **no** | not a closer |
| fence inside a blockquote or list | no | the extension is root-only |

Consequences for the design, each of which the first draft got wrong:

- **Column 0 only.** `^[ \t]*` would shield indented delimiters the extension ignores.
- **Exact delimiter run**, not merely the same character.
- **The opener's trailing text is not a restricted charset.** `[\w+-]*` misses `c#`, `foo.bar`
  and `{.python #ex}`. The opener may carry arbitrary trailing text; only the *closer* must be bare.
- **Left-to-right state machine, not independent pairing per delimiter type.** Once a fence is
  open, every line that is not its exact closer is content — including delimiters of the other
  character. Independent pairing would produce overlapping regions.

### The interaction that shapes the design

`~~~` is both a `fenced_code` delimiter and, at 3+ characters, a marker-run line that cut 1a
protects. Naive fence tracking would toggle on a lone `~~~~~` rule and treat the whole rest of the
document as fenced. Measured, python-markdown does **not** do that:

```
'text\n\n~~~~~\n\nmore'           identical with and without fenced_code: '<p><sub>~</sub>~~</p>'
'text\n\n```\ncode never closed'  ->  '<p>text</p>\n<p>```<br />\ncode never closed</p>'
```

**An unterminated fence is not a fence.** So fence handling must pair delimiters first and treat
only *closed* regions as fenced, which reproduces markdown's own behaviour and leaves a lone
`~~~~~` as the rule line cut 1a protects. Verified against the prototype:

```
'```\na\n```'                 flags [T, T, T]
'~~~~~'                       flags [F]
'```\nunterminated'           flags [F, F]
'a\n```\nx\n```\nb\n~~~~~\nc' flags [F, T, T, T, F, F, F]
```

## Design

### 1. Pair fences before doing anything with them

```python
_FENCE_OPEN = re.compile(r"^(`{3,}|~{3,})(.*)$")     # column 0; trailing text unrestricted
_FENCE_CLOSE = re.compile(r"^(`{3,}|~{3,})[ \t]*$")  # bare, trailing whitespace allowed
```

A left-to-right scan marks the lines of every **closed** fence region:

1. Outside a fence, a line matching `_FENCE_OPEN` at column 0 opens one, remembering its exact
   delimiter string.
2. Inside, a line closes it only if it matches `_FENCE_CLOSE` **and** its delimiter run is exactly
   the opener's character repeated at least as many times, with nothing but whitespace after.
   Anything else — including a delimiter of the other character — is content.
3. An opener with no closer before end of input is not a fence, matching the extension.

**The helper works on the original string, not on lines the caller split.** It returns a list of
`(content, separator)` records plus a fenced flag per record, so `preprocess_markdown` and
`markdown_to_plain` cannot disagree about line endings: today the first splits on `"\n"` and the
second on `(\r\n|\n|\r)`, and a CRLF body would leave a `\r` attached that no fence regex matches.

### 2. `preprocess_markdown` becomes block-aware

- Lines inside a closed fence are copied **verbatim** — no blank-line insertion, no analysis.
- A blank line is inserted before an opening fence, as for any other block.
- **Consecutive `>` lines no longer get a blank line between them**, mirroring the existing
  list-item rule, so a quoted line break survives (defect 5). The marker is recognised on the raw
  line with 0-3 leading spaces, matching the extension; 4 spaces is indented code, not a quote.
  Lazy continuation (`> first` / bare text / `> second`) is **out of scope** — the bare line resets
  the state and a blank is inserted, which is today's behaviour, unchanged.
- A blank line is inserted before a **table start**. Measured, the extension accepts both
  `| a | b |` and `a | b` header forms, and rejects a separator with no pipe in it:

  ```
  '| a | b |\n|---|---|\n| 1 | 2 |'   table
  'a | b\n--- | ---\n1 | 2'           table      -- the first draft's regex missed this
  '| literal |\n:---:'                NOT a table -- the first draft's regex accepted it
  ```

  So the rule is: a header row containing a `|`, immediately followed by a separator row that
  contains a `|` and consists only of `|`, `-`, `:` and whitespace. Root level only — a table
  indented inside a list is out of scope, because inserting an unindented blank line there would
  change list ownership.

Measured with the prototype, all eight behaving:

```
'```\n#include\n- literal\n> literal\n```'  -> '<pre><code>#include\n- literal\n&gt; literal\n</code></pre>'
'intro\n```\ncode\n```'                     -> '<p>intro</p>\n<pre><code>code\n</code></pre>'
'intro\n| a | b |\n|---|---|\n| 1 | 2 |'    -> '<p>intro</p>\n<table>...<td>1</td>...'
'> first\n> second'                         -> '<blockquote>\n<p>first<br />\nsecond</p>\n</blockquote>'
'text\n- a\n- b'   'text\n# Head'   'one\ntwo'   'text\n\n=====\n\nmore'   all unchanged
```

### 3. The plain-text shield extends from lines to regions

`markdown_to_plain` already shields marker-run lines behind a collision-safe nonce token and
verifies each token survives substitution. Fenced regions join the same mechanism — same tokens,
same verification loop, no second scheme. Fence delimiter lines are protected with their content.

Measured:

```
'**bold** here\n\n```\n**literal**\n~~literal~~\n==literal==\n[x](https://example.com)\n=====\n```\n\nand ~~gone~~\n'
  -> '*bold* here\n\n```\n**literal**\n~~literal~~\n==literal==\n[x](https://example.com)\n=====\n```\n\nand gone\n'
     fenced content byte-identical; inline outside still converts
'====='                        -> '====='                    unchanged from cut 1a
'**bold** and [t](http://x)'   -> '*bold* and t <http://x>'
```

### 4. `autolink_urls` skips `<pre>`, `<code>` and existing `<a>`

The guard goes **inside** `autolink_urls`, not in its caller, so a future caller cannot forget it.

**Narrow, stated contract.** The only input is HTML that python-markdown just produced from a draft
body: balanced, lowercase, no attributes containing a literal `</code>`. Within that, splitting on
`(<pre\b.*?</pre>|<code\b.*?</code>|<a\b.*?</a>)` with `DOTALL` is sufficient. It is *not* a
general HTML parser and must not be described as one: hand-written nested `<code>`, an unclosed
tag, or `<CODE>` would defeat it. Those cannot occur here because the caller is
`convert_body`, one line after `markdown.markdown()`.

`<a>` joins the exclusions in the same pass: today an already-anchored URL has its visible text
matched again and nested inside a second anchor.

```
'<pre><code>https://example.com</code></pre>'      -> unchanged
'<p>see https://example.com</p>'                   -> anchored as before
mixed p / pre-code / p                             -> only the two paragraphs anchored
```

### 5. Enable the extensions

`fenced_code` and `tables` join `MARKDOWN_EXTENSIONS`, and `HELP_TOPICS["draft"]` drops the line
saying they are unsupported.

## Constraints

- Cut 1a's guarantees must not regress: marker-run lines protected, `nl2br` for paragraphs, the
  nonce verification, plain mode byte-identical.
- One fence-pairing helper shared by preprocessing and the shield.
- The 540 tests pass, except the two that pin superseded behaviour, below.

### Superseded tests

- `test_markdown.py::test_adds_blank_line_before_code_block` asserts the closing fence gets a blank
  line before it — its own comment calls the behaviour out as odd. It becomes an assertion that
  fenced content is copied verbatim.
- `test_markdown_utils.py::test_consecutive_quote_lines_split_known_limitation`, pinned by cut 1a
  precisely so this cut changes it, becomes an assertion of one paragraph with a `<br />`.

## Acceptance Criteria

- [ ] **AC1 — fenced content survives into the HTML**

"Verbatim" means line structure and decoded text are preserved; HTML escaping still applies, which
is why the expected output below contains `&gt;`.

```gherkin
Given "```\n#include\n- literal\n> literal\n```"
Then the html is "<pre><code>#include\n- literal\n&gt; literal\n</code></pre>"
And no blank line was inserted anywhere inside the fence

Given "intro\n```\ncode\n```"
Then intro is its own paragraph and the fence renders as a code block

Given a fence with a language tag, "```python\nx = 1\n```"
Then the html marks it as python and the content is unchanged
```

- [ ] **AC2 — fenced content is verbatim in the plain alternative**

```gherkin
Given a body whose fence contains "**literal**", "~~literal~~", "==literal==",
      "[x](https://example.com)" and "====="
Then markdown_to_plain leaves every one of those lines byte-identical
And "**bold**" outside the fence still becomes "*bold*"
And "~~gone~~" outside the fence still becomes "gone"
```

- [ ] **AC3 — fence recognition matches python-markdown exactly**

Every row of the measured table above is a case, tested on the helper and end to end:

```gherkin
Given a fence at column 0, it is recognised
Given a 2-space or 4-space indented delimiter, it is not
Given 3 backticks opened and 4 closed, or 4 and 3, it is not a fence
Given 4 and 4, it is
Given "```c#", "```foo.bar" and "```{.python #ex}", each opens a fence
Given "~~~" inside a backtick fence, it is content, and a trailing lone "~~~" is not a fence
Given a closer with trailing spaces, it closes; given a closer carrying a language tag, it does not
Given LF, CRLF and bare CR bodies, the helper returns the same fenced flags
Given two adjacent closed fences, and an empty fence, both are recognised
```

- [ ] **AC3b — an unterminated or unpaired delimiter is not a fence**

```gherkin
Given "~~~~~" alone
Then it is still protected as a marker-run line, not treated as a fence
And the rest of the document is unaffected

Given "```\nunterminated"
Then no fence region is recognised, matching python-markdown, which renders it as a paragraph

Given "intro\n```\nnever closed"
Then no blank line is inserted before the delimiter either, because it is not a block start

Given "a\n```\nx\n```\nb\n~~~~~\nc"
Then only the three lines of the closed fence are treated as fenced
```

- [ ] **AC4 — tables render**

```gherkin
Given "intro\n| a | b |\n|---|---|\n| 1 | 2 |"
Then the html contains <table> with a and b as <th> and 1 and 2 as <td>

Given a table already preceded by a blank line
Then it renders identically, with no doubled blank line

Given "| not | a table" with no separator row
Then no blank line is inserted and no table is produced

Given "intro\na | b\n--- | ---\n1 | 2" without outer pipes
Then a blank line is inserted and a table is produced, matching the extension

Given "intro\n| literal |\n:---:\nafter"
Then no blank line is inserted, because a separator with no pipe is not a table separator
And the paragraph is not split
```

- [ ] **AC5 — a quoted line break survives**

```gherkin
Given "> first\n> second"
Then the html is one blockquote containing one paragraph with a <br /> between the lines

Given "text\n> quote"
Then a blank line is still inserted before the quote so it becomes a blockquote

Given "- item\n> quote"
Then a blank line is still inserted, since a list item is not a quote line

Given quote markers indented by 0, 1 and 3 spaces
Then each continues the quote; given 4 spaces, it does not
```

- [ ] **AC6 — autolinking never enters code**

```gherkin
Given "<pre><code>https://example.com</code></pre>"
Then autolink_urls returns it unchanged

Given "<p>see https://example.com</p>"
Then the url is anchored as before

Given a mix of paragraph, pre/code and paragraph
Then only the paragraphs are anchored

Given "<p><code>https://inside</code> https://outside</p>"
Then only the outside url is anchored

Given html that already contains an anchor around a url
Then no nested anchor is produced

Given a body with a url inside a fence and another outside it, converted through convert_body
Then the first survives as code text and the second becomes an anchor
```

- [ ] **AC7 — cut 1a's guarantees still hold**

```gherkin
Given every marker-run and inline case from cut 1a's AC6
Then markdown_to_plain returns exactly what cut 1a asserted

Given "one\ntwo" and "one\n\ntwo"
Then nl2br and paragraph separation behave exactly as cut 1a asserted

Given a plain-format body
Then it is still byte-identical with no HTML part
```

- [ ] **AC8 — the help no longer lies**

```gherkin
Given HELP_TOPICS["draft"]
Then it does not say fenced code blocks and tables are unsupported
And it names them as supported
```

- [ ] **AC9 — the full suite passes**

```gherkin
When `cd tests && uv run --frozen pytest imap-slim-mcp/ -q` is run
Then every test passes
```

## Testing Strategy

- **Unit, deterministic**: AC1–AC7 in `test_markdown_utils.py`, against `convert_body` and
  `markdown_to_plain` directly.
- **Fence pairing**: AC3 tested on the helper directly as well as end to end, since the flag array
  is the thing the two callers share.
- **Regression**: AC7 re-runs cut 1a's parametrised case lists rather than restating them.
- **Static**: AC8 in `test_tool_description.py`.
- Outside-in per AC: failing test first.

## Out of Scope

- **Indented (four-space) code blocks** — core markdown already handles them and no defect was
  measured.
- **Inline spans crossing a newline**, whitespace-in-delimiters, escapes, inline code spans — the
  pre-existing `markdown_to_plain` behaviours cut 1a listed.
- **Nested fences** — a fence inside a fence is not markdown; the scan takes the first exact
  closer, stated rather than special-cased.
- **Fences and tables inside lists or blockquotes** — the extension is root-only for fences, and a
  blank line inserted before an indented table would change list ownership.
- **Lazy blockquote continuation** — a bare line between two `>` lines still resets the state.
- **A general HTML parser for autolinking** — the contract is markdown-generated HTML only, stated
  in Design §4.
- Cuts 3, 4, 5.

## Tasks

- [ ] 1. Failing AC3 tests for the fence-pairing helper.
- [ ] 2. Failing AC1, AC4, AC5 tests for preprocessing.
- [ ] 3. Failing AC2 tests for the region shield.
- [ ] 4. Failing AC6 tests for autolinking.
- [ ] 5. `_FENCE` + the pairing helper.
- [ ] 6. `preprocess_markdown`: verbatim fences, quote continuation, table starts.
- [ ] 7. `markdown_to_plain`: shield fenced regions with the existing token scheme.
- [ ] 8. `autolink_urls`: skip `<pre>`/`<code>` internally.
- [ ] 9. `fenced_code` and `tables` into `MARKDOWN_EXTENSIONS`.
- [ ] 10. Update the two superseded tests with docstrings saying what changed and why.
- [ ] 11. `HELP_TOPICS["draft"]`; `CHANGELOG.md`.
- [ ] 12. Verify: full suite green.

## Files Changed

| file | change |
|---|---|
| `imap-slim-mcp/markdown_utils.py` | `MARKDOWN_EXTENSIONS:14-21`, `preprocess_markdown`, `markdown_to_plain`, `autolink_urls`, new fence helper |
| `imap-slim-mcp/imap_stream_mcp.py` | `HELP_TOPICS["draft"]` Format section |
| `tests/imap-slim-mcp/` | `test_markdown_utils.py`, `test_markdown.py`, `test_tool_description.py` |
| `imap-slim-mcp/CHANGELOG.md` | Unreleased entry |

## Reflection

<!-- Written post-implementation -->
