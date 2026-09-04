# Cut 1: markdown contract — state it, honour line breaks, stop corrupting marker-run lines

Frame: `2026-08-24-frame-imap-slim-cli-daemon.md`. Cut 1 of 5. No architecture change; mergeable alone.

Revision history, both driven by cross-model review findings that were reproduced before acting:

- **r1** lookaround guards on each marker. Rejected — regressed `***bold italic***` and adjacent
  spans, missed underscore runs. See §Rejected designs.
- **r2** per-line processing. Rejected — regressed multi-line links, which work today. See §Rejected designs.
- **r3** (this) placeholder shield: protect marker-run lines, then run the existing whole-body
  substitutions completely untouched. Hardened after a third review pass — nonce sentinel,
  bare-CR splitting, exact-token restore.

## Intent

A drafting session must be able to tell, from what it already has in context, that the body it
writes is markdown and how newlines behave. Today it cannot, so it either decorates with ASCII
that silently becomes headings and lists, or it strips its own formatting after seeing the
result. Both were observed on 2026-08-24.

## Goal

`format` semantics are visible in the tool description and echoed in the draft response; a newline
inside a paragraph survives into the rendered mail; a line that is nothing but a run of `=`, `~`,
`*` or `_` — optionally indented or quote-prefixed — reaches the plain-text part unchanged.

## Situational Context

- `markdown_utils.convert_body(body, format_type="markdown")` (`markdown_utils.py:132-167`) is
  the single conversion point, called from both draft branches
  (`imap_stream_mcp.py:785-786` modify, `imap_stream_mcp.py:824-825` create).
- `MARKDOWN_EXTENSIONS` (`markdown_utils.py:14-20`): `pymdownx.tilde`, `pymdownx.tasklist`,
  `pymdownx.mark`, `pymdownx.betterem`, `pymdownx.emoji`. No `nl2br`.
- `markdown_to_plain` (`markdown_utils.py:104-131`) produces the `text/plain` alternative by
  applying five unanchored `re.sub` calls **to the whole body**. Two of them depend on that:
  `\[([^\]]+)\]\(([^)]+)\)` spans newlines because both negated classes match `\n`.
- What a session loads: `use_mail` docstring (`imap_stream_mcp.py:424-441`) and `MailAction`
  field descriptions (`imap_stream_mcp.py:145-163`). Neither says "markdown".
  `HELP_TOPICS["draft"]` (`imap_stream_mcp.py:272-307`) says it but is opt-in.
- Draft responses (`imap_stream_mcp.py:807-813` modify, `849-855` create) do not mention format.
- Baseline: `cd tests && uv run pytest imap-slim-mcp/ -q` → **430 passed in 0.67s**.

### Measured defects (all reproduced 2026-08-24)

```
markdown_to_plain, marker-run lines:
  '====='  → '='        '~~~~~'  → '~'        '*****'  → '***'
  '_____'  → '*_*'      '______' → '*_*_'     '=======' → '==='
  '~~~~~~' → '~~'       '******' → '****'
  '  =====  ' → '  =  '            '\t*****\t' → '\t***\t'
  '> ====='   → '> ='              '>> *****'  → '>> ***'
  'Terveisin\n=====\nVille'        → 'Terveisin\n=\nVille'
  'Terveisin\r\n=====\r\nVille\r\n'→ 'Terveisin\r\n=\r\nVille\r\n'

convert_body('Terveisin\nVille\nItio Oy'):
  HTML  '<p>Terveisin\nVille\nItio Oy</p>'   → one running line in the client
  plain 'Terveisin\nVille\nItio Oy'          → breaks intact
  the two alternatives of the multipart therefore disagree
```

Underscore runs were missed in r1, which asserted `__` was not defective. It is.

### Pre-existing limitations confirmed, NOT fixed here

Verified against the actual extension list, because r1 leaned on constructs that turn out not to
be supported at all:

```
markdown.markdown('```\n**literal**\n```')  → '<p><code>**literal**</code></p>'   no fenced_code
markdown.markdown('| a | b |\n|---|---|')   → '<p>| a | b |\n|---|---|</p>'       no tables
markdown.markdown('Terveisin\n=====\nVille', +nl2br) → '<h1>Terveisin</h1>\n<p>Ville</p>'
```

The third is not a defect: `=====` under text is a **setext heading underline**, and markdown
block syntax takes precedence over `nl2br`. It is the reason the tool wording must say "newline
*in a paragraph*" rather than "newline", and the reason the manual check states its expected HTML
explicitly instead of calling `=====` a rule.

## Constraints

- Tool-description additions cost context on every session. Budget: **≤ 161 characters** across
  the two edited fragments, whose pre-change lengths are recorded in AC5. The wording chosen in
  Design §3 measures **147** (+24 payload, +123 docstring), verified by extracting the exact
  fragments the AC5 test reads, indentation included.
- The entire pre-existing test suite must pass unchanged. r1 failed this.
- The five substitutions in `markdown_to_plain` must keep running over the **whole body**, in
  their current order, on unprotected text. r2 failed this.
- No change to the wire format, the accepted `format` values, or `preprocess_markdown`.

## Design

### 1. `nl2br` unconditionally in markdown mode

Append `"nl2br"` to `MARKDOWN_EXTENSIONS`. A newline inside a paragraph becomes `<br>`, a blank
line still starts a paragraph, and markdown block syntax still wins where it applies. This is the
contract every mail composer already has, and it makes the HTML alternative agree with the plain
alternative, which today it does not.

Accepted consequence: prose hard-wrapped by the writer renders with those breaks. That is already
true of the plain part, so this removes a divergence rather than creating one. The escape hatch
already exists and is unchanged: `format: "plain"` skips conversion entirely. **No new
`linebreaks` option** — a second knob for a case the existing one covers.

### 2. Placeholder shield in `markdown_to_plain`

The observed defect is a *line* that is nothing but a marker run. Protect exactly those, then run
the existing substitutions over the whole body with no other change:

```python
_MARKER_RUN_LINE = re.compile(r"^[ \t]*(?:>[ \t]*)*([*_=~])\1{2,}[ \t]*$")
```

1. `re.split(r"(\r\n|\n|\r)", text)` — keeps every separator as its own element, so CRLF, LF and
   bare CR all survive. `splitlines()` is not used: it recognises additional Unicode line breaks
   and would rewrite them.
2. Each content element matching `_MARKER_RUN_LINE` is swapped for a sentinel
   `"\x00" + nonce + "\x00" + str(index) + "\x00"`, where `nonce` is the shortest **non-empty**
   run of `0` such that the base `"\x00" + nonce + "\x00"` does not occur in the body.
   The base must be a *prefix* of every token: that is what makes the absence check sound. A
   token of the form `"\x00" + nonce + str(index) + "\x00"` would **not** be safe — the base
   `"\x000\x00"` can be absent from a body that still contains `"\x0001\x00"`, and exact
   restoration would then rewrite user text. Verified: with the unsafe form,
   `"\x0000\x00 literal\n=====\n"` comes back as `"===== literal\n=====\n"`; with the prefixed
   form it round-trips unchanged.
   The `\x00` delimiters also make tokens mutually non-overlapping, so index 1 cannot corrupt
   index 10, and the token contains no `*`, `_`, `=`, `~`, `[`, `]`, `(` or `)`, so none of the
   five substitutions can match inside it.
3. The five existing substitutions run over the rejoined body, unchanged and in the current order.
4. Each sentinel is restored by exact string replacement to its original line, byte for byte.

A substitution *may* legitimately span a sentinel — the link expression does, since `[^\]]` and
`[^)]` match both `\x00` and newlines. That is correct and required: it is how the multi-line link
keeps working. The sentinel is re-emitted untouched inside the replacement, then restored.

The quote prefix `(?:>[ \t]*)*` is included because a rule line quoted from an earlier reply is
the plausible real case; `-` is deliberately absent from the character class since no substitution
touches it.

Verified — every marker-run form is protected and **every** inline case is byte-identical to
current behaviour:

```
'=====' '~~~~~' '*****' '_____' '______' '=======' '~~~~~~' '******'   now unchanged
'  =====  '  '\t*****\t'  '> ====='  '>> *****'                       now unchanged
'Terveisin\n=====\nVille'   'Terveisin\r\n=====\r\nVille\r\n'  '=====\n'   now unchanged

'***bold italic***'  → '**bold italic**'              identical to today
'~~a~~~~b~~' → 'ab'   '==a====b==' → 'ab'             identical to today
'**a****b**' → '*a**b*'   '**bold**' → '*bold*'       identical to today
'a ~~b~~ c' → 'a b c'   'a ==x== b' → 'a x b'         identical to today
'[t](http://x)' → 't <http://x>'                      identical to today
'[long label\ncontinued](https://example.com)' → 'long label\ncontinued <https://example.com>'
                                                      identical to today  ← r2 broke this
'**bold\ncontinued**'  unchanged   ''  unchanged   'no markers here'  unchanged

'[alpha\n=====\nomega](https://example.com)\n~~~~~'   → 'alpha\n=====\nomega <https://example.com>\n~~~~~'
      link spanning two protected lines: both restored, link still converted
11 protected lines + 'a ==x== b'  → all 11 restored, 'a x b'   (index 1 vs 10, no overlap)
'\x000\x00 literal\n=====\n'   '\x0000\x00 literal\n=====\n'   '\x0001\x00 literal\n=====\n=====\n'
      → all unchanged; nonce lengthens until the base is absent from the body
'=====\r'  '=====\r\n'  '=====\n'  'a\r=====\rb'   → all unchanged
```

### Rejected designs

**r1 — negative lookarounds** `(?<!X)XX(?!X)(.+?)(?<!X)XX(?!X)` per marker. Cross-model review
found, and direct measurement confirmed, two regressions: `***bold italic***` became
`***bold italic***` instead of today's `**bold italic**`, breaking `test_bold_italic_combined`
(`tests/imap-slim-mcp/test_markdown.py:161-169`); and adjacent spans `~~a~~~~b~~` became
`a~~~~b` instead of today's correct `ab`, same for `==a====b==` and `**a****b**`. It also missed
underscore runs. The lookaround models delimiter adjacency; the defect is about whole lines.

**r2 — apply the five substitutions per line.** Cross-model review found, and measurement
confirmed, that this silently drops the multi-line link case: `[long label\ncontinued](url)` is
converted today because `[^\]]` and `[^)]` match newlines, and per-line processing leaves it
untouched. Protection must not change the scope over which the substitutions run.

### 3. Say it where the model reads it

`MailAction.payload` description — replace the draft segment with (+24 chars; `body` →
`body:markdown` is +9, `format?` → `format?:markdown|plain` is +15):

```
draft=JSON{to,subject,body:markdown,in_reply_to?,cc?,format?:markdown|plain,attachments?:[paths]}
```

`use_mail` docstring — replace the draft example line with (+123 chars, indentation included):

```
{action:"draft", payload:'{"to":"x","subject":"y","body":"**md** body"}'} - body is markdown→HTML; newline=<br>, blank line=paragraph, block syntax wins; format:"plain"=no conversion
```

`format:"plain"=no conversion` rather than "for raw" — "raw" is ambiguous between raw markdown,
raw HTML and unconverted text, and AC5 needs a testable statement that conversion is disabled.

### 4. Echo the format in the response

Both draft responses gain one line above `**Saved to:**`, derived from the actual `format_type`
used rather than hard-coded per branch:

```
**Format:** markdown → HTML + plain text      (or)      **Format:** plain text only
```

Closes the feedback loop: a session that meant plain text sees immediately that it did not get it.

### 5. `HELP_TOPICS["draft"]`

Update the `## Format` block to state the newline rule, that block syntax takes precedence, and
that fenced code blocks and tables are not supported. Opt-in detail, so it may be longer.

## Acceptance Criteria

- [ ] **AC1 — a newline inside a paragraph becomes a line break**

```gherkin
Given a draft body "Terveisin\nVille Reijonen\nItio Consulting Oy"
When convert_body is called with format_type "markdown"
Then the html part contains "Terveisin<br />" and "Ville Reijonen<br />"
And the plain part equals the input unchanged
```

- [ ] **AC2 — supported block constructs still work**

Scope is lists, headings, single blockquotes and paragraph separation. Fenced code and tables are
excluded by Out of Scope and are not asserted.

```gherkin
Given a draft body "- a\n- b\n\npara one\nline two"
When convert_body is called with format_type "markdown"
Then the html part contains "<ul>", "<li>a</li>", "<li>b</li>"
And no "<br />" appears between "<ul>" and "</ul>"
And the html part contains "<p>para one<br />"

Given a draft body "# Otsikko\n\nteksti"
Then the html part contains "<h1>Otsikko</h1>"

Given a draft body "teksti\n\n> lainaus"
Then the html part contains "<blockquote>" and "lainaus"
```

- [ ] **AC3 — marker-run lines survive; nothing else changes**

Literal expected values, not "same as before" — the implementer must not have to run the old code
to know the target.

```gherkin
Given each of "=====", "~~~~~", "*****", "_____", "______", "~~~~~~", "******", "=======",
      "  =====  ", "\t*****\t", "> =====", ">> *****", "> > _____", "=====\n", "=====\r",
      "a\r=====\rb", "Terveisin\n=====\nVille", "Terveisin\r\n=====\r\nVille\r\n"
When markdown_to_plain is called
Then the output equals the input byte for byte

Given a body of 11 "=====" lines followed by "a ==x== b"
Then all 11 lines are restored unchanged and the last line becomes "a x b"

Given bodies that already contain sentinel-shaped text:
      "\x000\x00 literal\n=====\n", "\x0000\x00 literal\n=====\n",
      "\x0001\x00 literal\n=====\n=====\n"
Then the output equals the input byte for byte

Given these inputs, then markdown_to_plain returns exactly:
  "***bold italic***"                            -> "**bold italic**"
  "~~a~~~~b~~"                                   -> "ab"
  "==a====b=="                                   -> "ab"
  "**a****b**"                                   -> "*a**b*"
  "**bold**"                                     -> "*bold*"
  "a ~~b~~ c"                                    -> "a b c"
  "a ==x== b"                                    -> "a x b"
  "[t](http://x)"                                -> "t <http://x>"
  "[long label\ncontinued](https://example.com)" -> "long label\ncontinued <https://example.com>"
  "[alpha\n=====\nomega](https://example.com)\n~~~~~"
                                                 -> "alpha\n=====\nomega <https://example.com>\n~~~~~"
  "**bold\ncontinued**"                          -> "**bold\ncontinued**"
  "# Heading\n\n- list item\n\n> quote"          -> "# Heading\n\n- list item\n\n> quote"
  ""                                             -> ""
```

The second block is the regression gate: rows 1 and 4 are what r1 broke, row 9 is what r2 broke.
Row 10 is the case a naive shield breaks — a link spanning two protected lines, which must keep
both sentinels intact while still converting.

- [ ] **AC4 — the draft response states the format actually used**

Parameterised over both branches and all three ways of arriving at a format, because a hard-coded
line in one branch would otherwise pass.

```gherkin
Given a draft call in {create, modify} with format {omitted, "markdown"}
Then the response contains "**Format:** markdown → HTML + plain text"

Given a draft call in {create, modify} with format "plain"
Then the response contains "**Format:** plain text only"
```

- [ ] **AC5 — the contract is stated where the model reads it, within budget**

Baselines measured 2026-08-24, before any edit: `MailAction.payload` description **192** chars,
the `use_mail` docstring draft-example line **65** chars, combined **257**.

```gherkin
Given the use_mail docstring and the MailAction.payload description
Then together they state that the draft body is markdown rendered to HTML
And together they state that a newline is a line break and a blank line a paragraph
And together they state that markdown block syntax still takes precedence
And together they state that format "plain" disables conversion

Given the payload description and the docstring draft-example line after the change
Then their combined length is at most 418 (baseline 257 + 161)
```

Informational, not asserted: the whole always-loaded description measured
`len(use_mail.__doc__) + sum(len(f.description) for f in MailAction.model_fields.values())` =
**1919** (docstring 1357, field descriptions 562). `use_mail` remains a plain function after
`@mcp.tool`, so `__doc__` is readable.

- [ ] **AC6 — no regression**

```gherkin
Given the pre-existing test suite, green before this change
When the suite is run after the change
Then every pre-existing test still passes, none modified or deleted
And test_bold_italic_combined in tests/imap-slim-mcp/test_markdown.py passes unchanged
```

No test count is pinned — this cut adds tests to existing files, so a count cannot identify the
pre-existing set.

- [ ] **AC7 — help text matches behaviour**

```gherkin
Given HELP_TOPICS["draft"]
Then its Format section states the newline rule and that block syntax takes precedence
And it names fenced code blocks and tables as unsupported
```

## Testing Strategy

- **Unit, deterministic, no IMAP**: AC1–AC3 and AC7 in `tests/imap-slim-mcp/test_markdown_utils.py`.
- **Tool-level with mocks**: AC4 parameterised in `tests/imap-slim-mcp/test_imap_stream_mcp.py`,
  following the existing mocked-draft pattern (`test_imap_stream_mcp.py:601-620`).
- **Static assertion**: AC5 in a new `tests/imap-slim-mcp/test_tool_description.py` — required
  phrases plus the two-fragment length ceiling.
- **Manual, raw MIME not rendering**: one draft written to HC's own Drafts folder containing a
  signature block, a `=====` line preceded by a blank line, a list and a quoted `>` block.
  Verified by reading the raw message source: `text/plain` must retain the five `=`, `text/html`
  must contain `<br />` inside the signature. Expected HTML for the `=====` line, measured
  2026-08-24 with the post-change extension list:

  ```
  'teksti\n\n=====\n'    → '<p>teksti</p>\n<p>=====</p>'     blank line before: plain paragraph
  '\n\n=====\n'          → '<p>=====</p>'
  'teksti\n=====\nVille'  → '<h1>teksti</h1>\n<p>Ville</p>'   no blank line: setext heading
  ```

  So a blank line before the `=====` keeps it a literal paragraph — that is the form the manual
  draft uses, and `pymdownx.mark` does not touch it. Without the blank line it is a setext
  heading, which is markdown working as specified, not a defect.
  Thunderbird's rendered view alone cannot prove the plain part, as it displays the HTML
  alternative. Writes to HC's live mailbox — a draft only, never a send, and HC confirms before
  it runs.
- Outside-in per AC: failing test first, then implementation.

## Out of Scope

- **Fenced code blocks and tables.** Not supported by the current extension list (verified above).
  Adding `fenced_code`/`tables` is a behaviour change with its own risk surface, not part of
  stating the existing contract. Documented as a limitation in `HELP_TOPICS["draft"]`.
- **Inline spans crossing a newline.** `**bold\ncontinued**` is left literal in the plain part
  because `.` does not match newline; after `nl2br` the HTML renders it as emphasis. A known
  HTML/plain divergence, narrower than the one this cut closes. Recorded in `TODO.md`, not fixed.
- **Whitespace-inside-delimiters, escaped markers, and inline code spans.** `** not bold **` →
  `* not bold *` and `` `**x**` `` → `` `*x*` `` are pre-existing behaviours of the five
  substitutions, unchanged by this cut. Fixing them needs real tokenisation — a separate cut if
  ever worth it.
- **`preprocess_markdown` block handling.** It inserts a blank line between consecutive `>` lines
  and before a closing fence (`test_markdown.py:33-38` asserts the latter). Pre-existing, untouched.
- **Test-file duplication.** `test_markdown.py` and `test_markdown_utils.py` overlap heavily
  (`TestPreprocessMarkdown` is near-verbatim in both). Noted, not merged — unrelated churn.
- Everything in cuts 2–5: connection handling, rename, daemon, CLI, MCP role.

## Tasks

- [ ] 1. Write failing tests for AC1–AC3 in `test_markdown_utils.py`, including the AC3 regression block.
- [ ] 2. Write failing parameterised tests for AC4 in `test_imap_stream_mcp.py`.
- [ ] 3. Write the failing AC5 phrase + length test in new `test_tool_description.py`.
- [ ] 4. Add `nl2br` to `MARKDOWN_EXTENSIONS`; update the `convert_body` docstring.
- [ ] 5. Add `_MARKER_RUN_LINE` and the shield/restore wrapper to `markdown_to_plain`; update its docstring.
- [ ] 6. Update the `payload` field description and the `use_mail` docstring draft example.
- [ ] 7. Derive the `**Format:**` line from `format_type` and add it to both draft responses.
- [ ] 8. Update `HELP_TOPICS["draft"]` Format block, including block-precedence and unsupported constructs (AC7).
- [ ] 9. `TODO.md` entry for the multi-line-span divergence; `CHANGELOG.md` Unreleased entry.
- [ ] 10. Verify: full suite green, then the raw-MIME manual check.

## Files Changed

| file | change |
|---|---|
| `imap-slim-mcp/markdown_utils.py` | `MARKDOWN_EXTENSIONS:14-20`, `markdown_to_plain:104-131`, docstrings |
| `imap-slim-mcp/imap_stream_mcp.py` | `MailAction.payload:152-155`, docstring `:424-441`, responses `:807-813` and `:849-855`, `HELP_TOPICS["draft"]:288-292` |
| `tests/imap-slim-mcp/test_markdown_utils.py` | AC1–AC3, AC7 |
| `tests/imap-slim-mcp/test_imap_stream_mcp.py` | AC4 |
| `tests/imap-slim-mcp/test_tool_description.py` | new — AC5 |
| `imap-slim-mcp/TODO.md`, `imap-slim-mcp/CHANGELOG.md` | limitation + Unreleased entry |

## Reflection

<!-- Written post-implementation by IMP -->
