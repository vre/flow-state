# TODO

## Flat mode validation broken

- `--flat` generates single `.py` file
- `validate_tool.py` only accepts directories — exits with error on flat files
- Workaround: skip validation for `--flat` output

## Domain flag unused

- `subskills/discover_intent.md` defines domain categories
- Generator supports `--domain` flag
- SKILL.md and `subskills/generate_skeleton.md` never pass `--domain` — collected but dropped

## pyproject.toml patch claim false

- `subskills/generate_skeleton.md` claims existing pyproject.toml is patched
- Generator only warns about existing file, does not patch
