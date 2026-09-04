# Code reflection — cut 1a, draft body contract

540 tests pass (472 before), ruff clean. Description budget 2212 of 2249.

The incident body, now:

```
format=markdown  <p>Terveisin<br /> Ville Reijonen<br /> Itio Consulting Oy</p>
                 <p>=====</p>  <ul><li>kohta yksi</li>...
                 plain part identical to the input
format=plain     html is None, plain byte-identical
```

## What the plan did not predict

**FastMCP wraps the whole model.** The served schema is `{properties: {params: $ref}}` with
`MailAction` under `$defs`, not a flat property list. The enum does reach the model, one level
deeper than the annotation suggests. The plan's AC said "a top-level `format` property exists" and
the test failed with `KeyError: 'format'` — which is the reason review insisted on asserting the
*served* schema rather than `model_json_schema()`. Had I only asserted the Pydantic output, the
test would have passed while telling me nothing about what the model actually sees.

**`set_content()` appends a trailing newline.** The markdown MIME test failed on
`'Terveisin\nVille Reijonen\n' != 'Terveisin\nVille Reijonen'`. Harmless and standard, but it is
precisely why the plan said "decoded payload" rather than "raw bytes" — and even decoded, equality
needs the trailing newline accounted for. The assertion now says so instead of hiding it in a
`.strip()`.

## The migration was the bulk of it

Thirteen tests failed on the first run, all callers rather than logic. Two of them encoded the old
contract as an assertion — `test_default_format_is_markdown` and
`test_edit_draft_html_regenerated_from_edited_plain`, the latter asserting as correct exactly the
behaviour that destroys formatting. Both were rewritten with docstrings saying what was superseded
and why, so the next reader does not re-derive the old rule from a deleted test.

A blanket regex adding `format="markdown"` to every `MailAction(action="draft"` also added it to
the one test that must omit it, and duplicated it where I had already written it by hand. Two
compile errors and a confusing failure. A mechanical edit across tests needs the exceptions listed
first, not discovered by the compiler.

## Changed from plan

- `edit_draft` no longer calls `convert_body` at all — with HTML-bearing drafts refused, there is
  nothing to regenerate, so `html=None` is passed unconditionally and the import went with it.
  The plan implied the call would remain.
- The empty-HTML-part case refuses, because `_extract_draft_bodies` yields `""` and `"" is not
  None`. That matches the AC, but it is emergent from the existing extractor rather than designed.

## For cut 1b

`preprocess_markdown` is untouched here, and the blockquote limitation is pinned by a test that
asserts two paragraphs inside one blockquote. Cut 1b changes that assertion deliberately rather
than discovering it. The four fenced-code and table defects are already measured in
`2026-08-26-cut1b-code-and-tables.md`; the shield built here generalises from lines to regions, and
the nonce-verification loop carries over unchanged.
