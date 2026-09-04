# Cut 1a: make the draft body contract visible and honour it

Frame: `2026-08-24-frame-imap-slim-cli-daemon.md`. Supersedes `2026-08-24-cut1-markdown-contract.md`.

**Split from the single cut 1 on 2026-08-26.** Fenced code blocks and tables moved to cut 1b: they
are not "two more extensions", they require a fence-aware `preprocess_markdown`, a shield over
whole fenced regions, and an HTML-aware `autolink_urls`. Measurements in
`2026-08-26-cut1b-code-and-tables.md`. Bundling them would make the visibility fix wait on a
preprocessing rewrite.

Baseline: `cd tests && uv run --frozen pytest imap-slim-mcp/ -q` → **472 passed**.

## Intent

A session drafting mail cannot tell, from anything it has in context, that the body it writes is
markdown. `format` lives inside a **JSON string**, so the tool schema describes none of it — no
type, no enum, no description. Reading the help is the only way to learn the contract, which is
exactly what should not be required. Observed 2026-08-24: a session wrote `Otsikko\n=======` as
decoration, got `<h1>`, concluded "this draft is plain text", and stripped its own formatting.

## Goal

Two modes, both stated where the model already looks, and both actually applied. `plain` sends
exactly what was written and nothing else. `markdown` produces plain **and** HTML, with a newline
inside a paragraph meaning a line break. Choosing is mandatory; there is no silent default at any
layer.

## Constraints and decisions (HC, 2026-08-26)

- Mode names stay **`markdown`** and **`plain`**; nothing renamed, no aliases.
- **`plain` means only plain** — `text/plain`, no HTML part, no `<pre>` wrapper. HC accepts that
  the client picks the font.
- **`markdown` produces plain + HTML.**
- **No markdown source is cached anywhere.** HC: "the llm has the markdown."

## Situational Context

- `convert_body` (`markdown_utils.py:132-167`) is the single conversion point.
- Both draft branches read the format from the **payload**, not from the tool call:
  `draft_data.get("format", "markdown")` at `imap_stream_mcp.py:785` (modify) and `:824` (create).
- `MailAction` (`imap_stream_mcp.py:145-176`) already has the precedent: `preview` is
  `default=None` with a `model_validator` rejecting `list`/`search` without it.
- Draft responses (`:807-813`, `:849-855`) do not mention the format used.
- `edit_draft` (`imap_client.py:1388`) re-renders from the stored plain part.

### Measured defects

```
what a session loads:  docstring + field descriptions = 1919 chars; "markdown" appears in neither
                       everything inside `payload` is a JSON string: no schema, no enum, no types

marker-run lines through markdown_to_plain:
  '====='  -> '='   '~~~~~' -> '~'   '*****' -> '***'   '_____' -> '*_*'
  '  =====  ' -> '  =  '   '> =====' -> '> ='   'Terveisin\n=====\nVille' -> 'Terveisin\n=\nVille'

convert_body('Terveisin\nVille\nItio Oy', 'markdown'):
  HTML  '<p>Terveisin\nVille\nItio Oy</p>'   one running line
  plain breaks intact                        the two alternatives disagree

edit on a markdown draft, one replacement to an unrelated word:
  <strong>Ville</strong> -> <em>Ville</em>   <del>vanha</del> -> vanha   <mark>tarkea</mark> -> tarkea
```

## Design

### 1. `format` becomes a required top-level field — and is actually read

```python
format: Literal["markdown", "plain"] | None = Field(default=None, description=...)
```

plus a `model_validator` rejecting `action == "draft"` when it is `None`, mirroring
`validate_preview_required`.

**Both draft branches must use `params.format`.** They currently read
`draft_data.get("format", "markdown")` (`:785`, `:824`). Adding the field without changing those
two lines would ship a parameter nothing consults, and no schema or validator test would catch it.
This is the load-bearing edit of the cut.

Accurately stated: the field is **conditionally required at runtime with visible enum values**.
Pydantic renders `Literal[...] | None = None` as `anyOf(enum, null)` with `default: null`; it does
not appear in JSON Schema `required`, and the schema cannot express "required when action is
draft". What the model gains is the two values, their meaning, and a description saying when it is
required — which is the whole gap today.

**A top-level `format` key in the decoded draft payload is rejected**, naming the new field. The
check applies only when the decoded payload **is a JSON object**: `payload='"format"'` decodes to a
string, and a naive `"format" in draft_data` would report a forbidden key where there is no object
and no key. Arbitrary text containing the word is not a key.

**`convert_body` loses its default too.** `format_type: Literal["markdown", "plain"]` with no
default, and the error text stops calling markdown the default. A validator that protects the
production path is not the same as removing the silent default.

### 2. `nl2br` in markdown mode

A newline inside a paragraph becomes `<br>`, a blank line still starts a paragraph, and markdown
block syntax still wins where it applies — `Terveisin\n=====\nVille` is a setext heading, which is
markdown working as specified.

**Known limitation, stated because this cut makes a newline promise:** two consecutive `>` lines do
*not* become one quoted paragraph with a line break. `preprocess_markdown` inserts a blank line
between them, so `> first\n> second` renders as `<blockquote><p>first</p><p>second</p></blockquote>`.
Fixing it means making preprocessing block-aware, which is cut 1b's work.

### 3. Marker-run lines survive the plain alternative

Unchanged from the reviewed design in the superseded plan:

```python
_MARKER_RUN_LINE = re.compile(r"^[ \t]*(?:>[ \t]*)*([*_=~])\1{2,}[ \t]*$")
```

Split with `re.split(r"(\r\n|\n|\r)", text)` so CRLF, LF and bare CR survive. Each matching line
becomes `"\x00" + nonce + "\x00" + str(index) + "\x00"`, where `nonce` is the shortest non-empty
run of `0` making the base `"\x00" + nonce + "\x00"` absent from the body. The base must be a
**prefix** of every token, or a body containing `\x0001\x00` collides with token 1 and restoration
rewrites user text. The five substitutions then run over the whole body unchanged and in order;
tokens are restored by exact replacement.

The link substitution may legitimately span a token and must: `[a\n=====\nb](url)` converts today
because `[^\]]` matches newlines.

**The prefix rule is not sufficient on its own.** It guarantees no token is present in the *input*,
but a substitution can *synthesise* one. Measured:

```
input      '\x00==0==\x00==0==\x00\n====='
  base '\x000\x00' is absent, so token 0 is '\x000\x000\x00'
  the two highlight substitutions turn the first line into exactly that token
  restore then replaces both occurrences
  ->  '=====\n====='          wrong: user text rewritten
```

So after substituting, **verify each token occurs exactly once**; if any does not, lengthen the
nonce and redo from the original text. This terminates: a synthesised run of `0`s cannot exceed the
input length, so a nonce longer than the input cannot be manufactured. Verified: with the check the
same input returns `'\x000\x000\x00\n====='`, and all thirteen regression cases still pass.

### 4. The response says which mode was used

Derived from the format actually passed to `convert_body`, not hard-coded per branch:

```
**Format:** markdown → HTML + plain text        **Format:** plain text only
```

### 5. `edit` refuses to destroy an HTML body

Not mode detection — an HTML part does not mean "markdown draft"; a Thunderbird rich-text draft has
one too, and a markdown draft whose HTML part was deleted has no trace of its origin. The rule is
**preservation-based**: refuse any draft that currently carries an HTML body, because surgical
text replacement cannot preserve it. `edit_draft` re-renders from the plain part, which is the
lossy projection, so one edit turns bold into italic and drops strikethrough and highlight.

The refusal names the fix: send the full body with a draft-modify. The caller has it.

`edit` on a draft with no HTML body is lossless and keeps working unchanged.

## Acceptance Criteria

- [ ] **AC1 — the top-level format controls what is actually sent**

The end-to-end criterion. Without it the suite can pass while `params.format` is ignored.

```gherkin
Given a create draft call with format "plain"
Then create_draft receives html=None and the plain body unchanged

Given a create draft call with format "markdown"
Then create_draft receives a non-None html and a plain body

Given the same two cases through the modify branch
Then modify_draft receives the same arguments respectively

Given a draft payload whose decoded object contains a "format" key
Then both branches reject it with a message naming the top-level field

Given a draft payload whose body text merely contains the word "format"
Then it is processed normally

Given a payload that decodes to a JSON string or list rather than an object
Then the forbidden-key check does not fire on it
```

- [ ] **AC2 — choosing is mandatory, and the values are visible**

```gherkin
Given a draft action with no format
Then it is rejected with a message naming "markdown" and "plain"

Given a list or search action with preview supplied and no format
Then it is accepted, since format applies only to drafts

Given the input schema of the registered use_mail tool, read through FastMCP's tool listing
Then a top-level "format" property exists
And its non-null schema branch permits exactly "markdown" and "plain"
And the property remains nullable with a null default
And its description says when it is required

Given convert_body called with no format_type
Then it is a TypeError, not a silent markdown default
```

- [ ] **AC3 — plain means only plain**

```gherkin
Given a body with box-drawing characters, a "=====" line and a tab
When convert_body is called with "plain"
Then html is None and the plain part is byte-identical to the input

Given a draft created with format "plain"
When the generated MIME message is parsed
Then it has no text/html part
And the decoded text/plain payload equals the input body
```

- [ ] **AC4 — a newline inside a paragraph becomes a line break**

```gherkin
Given "Terveisin\nVille Reijonen\nItio Consulting Oy" as markdown
Then the html contains "Terveisin<br />" and "Ville Reijonen<br />"
And the plain part equals the input unchanged

Given "one\n\ntwo" as markdown
Then the html contains two separate <p> elements
And no <br /> bridges the blank line

Given a draft created with format "markdown"
When the generated MIME message is parsed
Then it has both a text/plain and a text/html part
And the decoded text/plain payload equals the input body
And the decoded text/html payload contains "<br />"
```

- [ ] **AC5 — supported blocks still work**

```gherkin
Given "- a\n- b\n\npara one\nline two"
Then the html contains "<ul>", "<li>a</li>", "<li>b</li>"
And no "<br />" appears between "<ul>" and "</ul>"
And the html contains "<p>para one<br />"

Given "# Otsikko\n\nteksti"       Then the html contains "<h1>Otsikko</h1>"
Given "teksti\n\n> lainaus"       Then the html contains "<blockquote>"
Given "> first\n> second"         Then the html contains two paragraphs inside one blockquote
```

The last scenario pins the known limitation from Design §2 so cut 1b changes it deliberately.

- [ ] **AC6 — marker-run lines survive; nothing else changes**

```gherkin
Given each of "=====", "~~~~~", "*****", "_____", "______", "~~~~~~", "******", "=======",
      "  =====  ", "\t*****\t", "> =====", ">> *****", "> > _____", "=====\n", "=====\r",
      "a\r=====\rb", "Terveisin\n=====\nVille", "Terveisin\r\n=====\r\nVille\r\n"
Then markdown_to_plain returns the input byte for byte

Given a body of 11 "=====" lines followed by "a ==x== b"
Then all 11 survive and the last line becomes "a x b"

Given sentinel-shaped bodies "\x000\x00 literal\n=====\n", "\x0000\x00 literal\n=====\n",
      "\x0001\x00 literal\n=====\n=====\n"
Then each returns byte for byte

Given "\x00==0==\x00==0==\x00\n=====", where the substitutions synthesise the shield's own token
Then the result is "\x000\x000\x00\n=====" and not "=====\n====="

Given these, markdown_to_plain returns exactly:
  "***bold italic***" -> "**bold italic**"    "~~a~~~~b~~" -> "ab"
  "==a====b==" -> "ab"                        "**a****b**" -> "*a**b*"
  "**bold**" -> "*bold*"                      "a ~~b~~ c" -> "a b c"
  "a ==x== b" -> "a x b"                      "[t](http://x)" -> "t <http://x>"
  "[long label\ncontinued](https://example.com)" -> "long label\ncontinued <https://example.com>"
  "[alpha\n=====\nomega](https://example.com)\n~~~~~"
        -> "alpha\n=====\nomega <https://example.com>\n~~~~~"
  "**bold\ncontinued**" -> "**bold\ncontinued**"
  "# Heading\n\n- list item\n\n> quote" -> unchanged        "" -> ""
```

- [ ] **AC7 — the response states the mode actually used**

```gherkin
Given a draft call in {create, modify} with format "markdown"
Then the response contains "**Format:** markdown → HTML + plain text"
And the response matches the arguments actually passed to create_draft/modify_draft

Given a draft call in {create, modify} with format "plain"
Then the response contains "**Format:** plain text only"
```

- [ ] **AC8 — edit refuses to destroy an HTML body**

Exact MIME structures, because a happy-path fixture would miss most of these.

```gherkin
Given a text/plain-only draft
Then edit applies the replacement as it does today

Given a multipart/alternative draft with text/plain and text/html
Then edit is refused, and the message says formatting would be lost and to send the full body

Given a multipart/related draft with an HTML root and an inline image
Then edit is refused

Given an HTML-only draft
Then edit is refused

Given a multipart/mixed draft with a text/plain body and a named .html file attachment
Then edit is NOT refused, because the attachment is not the body

Given a draft whose text/html part is present but empty
Then edit is refused, and the criterion states that an empty HTML part still counts
```

- [ ] **AC9 — the contract is stated where the model reads it, within a description-text budget**

Measures description prose only: `len(use_mail.__doc__) + sum(field description lengths)`. The
property name, type, enum and default also occupy served-schema space and are deliberately not in
this number. Baseline measured 2026-08-26: docstring 1357, field descriptions 562, combined
**1919**.

```gherkin
Given the use_mail docstring and the MailAction field descriptions
Then together they state that a draft body is markdown or plain and that choosing is required
And they state that a newline in a paragraph is a line break and a blank line a paragraph
And they state that plain is sent verbatim with no HTML
And the combined length is at most 2249 (baseline 1919 + 330)
```

- [ ] **AC10 — every example is a valid call**

```gherkin
Given every draft example in the use_mail docstring and in HELP_TOPICS
Then each includes a top-level format
And none places format inside the payload
And none describes markdown as a default

Given HELP_TOPICS["draft"]
Then its Format section states both modes, the newline rule, and that block syntax takes precedence
```

- [ ] **AC11 — the full suite passes**

```gherkin
When `cd tests && uv run --frozen pytest imap-slim-mcp/ -q` is run
Then every test passes
```

## Testing Strategy

- **Unit, deterministic**: AC3–AC6 in `test_markdown_utils.py`.
- **Tool-level, mocked**: AC1, AC2, AC7 in `test_imap_stream_mcp.py`, asserting on the arguments
  passed to the mocked `create_draft`/`modify_draft` rather than only on returned text.
- **MIME, deterministic and mandatory**: AC3 and AC4's message-structure halves build the message
  and parse it back, asserting content types and *decoded* payload equality. Raw wire bytes are not
  asserted — transfer encoding and CRLF normalisation make "byte-identical" meaningless there.
- **Schema**: AC2 reads the registered tool's `inputSchema` through FastMCP's tool listing, not
  only `MailAction.model_json_schema()`, since the served schema is what the model sees.
- **Edit refusal**: AC8 in `test_imap_client.py` with the six MIME structures constructed explicitly.
- **Static**: AC9, AC10 in a new `test_tool_description.py`.
- **Manual, optional and gated**: one draft to HC's own Drafts, verified by reading the raw source.
  Useful output verification, but **not a completion gate** — the deterministic MIME tests are.
  A draft only, never a send, and only if HC asks for it.
- Outside-in per AC: failing test first.

## Out of Scope

- **Fenced code blocks and tables** — cut 1b, with the preprocessing, shield and autolink work they
  require.
- **Consecutive blockquote lines** — pinned as a limitation by AC5, changed in cut 1b.
- **Any markdown source cache** — HC's decision.
- **`<pre>` alternative for plain** — HC's decision.
- **Inline spans crossing a newline** — `**bold\ncontinued**` stays literal in the plain part while
  the HTML renders it. Not recorded in `TODO.md`: there is no decision to fix it, and a TODO
  without one is debt, not a plan.
- **Whitespace-inside-delimiters, escapes, inline code spans** — pre-existing behaviour of the five
  substitutions, neither improved nor worsened.
- Cuts 3, 4, 5.

## Tasks

- [ ] 1. Failing AC1 tests: top-level format controls the arguments, in both branches.
- [ ] 2. Failing AC2 tests: validator, served schema enum, `convert_body` without a default.
- [ ] 3. Failing AC3–AC6 tests.
- [ ] 4. Failing AC7, AC8 tests with the six MIME structures.
- [ ] 5. Failing AC9, AC10 tests.
- [ ] 6. `format` field + `model_validator`; reject the payload key.
- [ ] 7. Wire `params.format` into both draft branches, replacing `draft_data.get(...)`.
- [ ] 8. `convert_body` loses its default; update callers and its error text.
- [ ] 9. `nl2br` in `MARKDOWN_EXTENSIONS`.
- [ ] 10. `_MARKER_RUN_LINE` + shield/restore in `markdown_to_plain`, with the
      verify-each-token-occurs-once retry.
- [ ] 11. `**Format:**` line in both draft responses.
- [ ] 12. `edit_draft` refuses when the draft carries an HTML body.
- [ ] 13. Docstring, `payload` description, `HELP_TOPICS` examples and Format section.
- [ ] 14. `CHANGELOG.md`.
- [ ] 15. Verify: full suite green.

## Files Changed

| file | change |
|---|---|
| `imap-slim-mcp/markdown_utils.py` | `MARKDOWN_EXTENSIONS:14-20`, `markdown_to_plain:104-131`, `convert_body:132-167` |
| `imap-slim-mcp/imap_stream_mcp.py` | `MailAction:145-176`; draft branches `:785`, `:824`; responses `:807-813`, `:849-855`; docstring `:424-441`; `HELP_TOPICS:200-330` |
| `imap-slim-mcp/imap_client.py` | `edit_draft:1388` refusal |
| `tests/imap-slim-mcp/` | `test_markdown_utils.py`, `test_imap_stream_mcp.py`, `test_imap_client.py`, `test_tool_description.py` (new) |
| `imap-slim-mcp/CHANGELOG.md` | Unreleased entry |

## Reflection

<!-- Written post-implementation -->
