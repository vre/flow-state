# Code reflection — cut 1b, fenced code and tables

583 tests pass (540 before), ruff clean.

## The plan's first draft would have shipped four wrong rules

Adding two extension names took one line. Getting the *grammar* right took a measurement table,
and every row of it contradicted something I had written down as obvious:

| I assumed | python-markdown actually does |
|---|---|
| fences may be indented (`^[ \t]*`) | column zero only; 2-space is not a fence, 4-space is an indented code block of literal backticks |
| closer matches on the same character | the delimiter run must repeat **exactly** — 3 open / 4 close is not a fence |
| language tags are `[\w+-]*` | `c#`, `foo.bar` and `{.python #ex}` are all valid |
| pair each delimiter type independently | a `~~~` inside a backtick fence is content; independent pairing produces overlapping regions |
| tables need outer pipes | `a \| b` over `--- \| ---` is a table too |
| my separator regex was safe | it accepted `:---:`, which is *not* a separator, and would have split a paragraph |

None of that was discoverable by reading my own code. It came from running the extension and
writing down what it returned. **When the job is "agree with a library", the library is the
specification, and approximating its grammar is how you build something that disagrees in ways no
test you thought to write will catch.**

## What the design got right by accident, and then on purpose

The first draft protected marker-run lines and fenced regions as two separate passes. Review
pointed out they could nest — a `=====` inside a fence would be shielded twice, and restoring the
inner token before the outer one leaves an unrestored token in the output. The fix was not
ordering; it was making the spans non-overlapping by construction: marker detection runs *only*
outside fenced regions. One list of maximal spans, one token scheme, one verification loop.

## Changed from plan

- The blank line before an *opening* fence has to be inserted in the verbatim branch, because that
  line is itself flagged as fenced. The first implementation put the check in the non-fenced branch
  where it was unreachable, and `intro\n```…` silently kept the fence glued to the paragraph. Caught
  by running the prototype cases, not by a test — the test came after.
- `_line_records()` returns `(content, separator)` pairs so both callers see identical lines.
  Previously `preprocess_markdown` split on `"\n"` and `markdown_to_plain` on `(\r\n|\n|\r)`; with a
  shared fence helper that divergence would have made them disagree about what is fenced on any
  CRLF body.

## Honest limits, stated rather than implied

- `autolink_urls` is **not** an HTML parser. It assumes balanced, lowercase markup with no literal
  `</code>` in an attribute — true because its only caller is `convert_body`, one line after
  `markdown.markdown()`. Hand-written nested `<code>` would defeat it. The docstring says so.
- Fences inside lists or blockquotes are not supported, matching the extension.
- Lazy blockquote continuation (`> a` / bare line / `> b`) still resets the state.
