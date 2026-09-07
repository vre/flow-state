# 0004 — The draft body format is required and top-level

Status: accepted (v1.1.0). Breaking.

## Context

`payload` is a JSON **string**, so nothing inside it reaches the tool schema — no type, no enum, no
description. A `format` living there was undiscoverable without calling `help`, and it defaulted to
`markdown`, so a caller intending plain text got HTML silently.

## Decision

`format` is a required top-level `MailAction` field, `Literal["markdown", "plain"]`, with no default
at any layer including `convert_body`. A `format` key inside the payload is an error naming the
top-level parameter. The response echoes the format used.

## Consequences

- A draft call without `format` fails. Removing the default is the fix; documenting it is not.
- Conditionally required at runtime, not in JSON Schema `required` — the schema cannot express
  "required when the action is create or replace". The model still sees the enum and its meaning.
- **Anything else added to `payload` is invisible the same way.** New parameters that a caller must
  choose deliberately belong at the top level.
