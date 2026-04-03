# TODO

## Auth support incomplete

- `oauth` not implemented in generator — SKILL.md now documents this
- `keyring` generates code but does not add `keyring` to pyproject.toml dependencies
- `keyring` references `setup.py` that is never generated
- `env_var` generates helper function that is never called by the generated server

## Subskill variables undefined

- `${DESCRIPTION}` required by both subskills but not collected in parent SKILL.md Step 1
- `${API_BASE_URL}` and `${first_action}` required by `with_api.md` but not collected
- Parent sets: DOMAIN, TRANSPORT, ACTIONS_JSON, AUTH_METHOD, INSTRUCTIONS — missing: DESCRIPTION, API_BASE_URL, first_action

## HTTP workflow inconsistent

- SKILL.md requires HOST, PORT, STREAMABLE_HTTP_PATH in .env.example
- Generator hardcodes transport and ignores HOST and STREAMABLE_HTTP_PATH

## Validator misses TODOs

- Generator emits TODO placeholders in action handlers, help text, tool title
- `validate_mcp.py` does not check for TODOs — unfinished scaffold passes validation

## Stale doc reference

- `references/Designing MCP Servers.md:3` references a CLAUDE.md section that doesn't exist
