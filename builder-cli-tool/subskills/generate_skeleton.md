---
name: generate_skeleton
description: "Generate or scaffold CLI tool from discovered requirements."
---

# Generate Skeleton

## New Project

```bash
python3 ./scripts/generate_cli.py \
  --name "${TOOL_NAME}" \
  --operations '["list", "get", "create", "delete", "help"]' \
  --output "${OUTPUT_DIR}"
```

Creates: `${NAME}.py`, `cli.py`, `pyproject.toml`, `tests/test_core.py`, `tests/test_cli.py`

## Existing Project

If pyproject.toml exists in output dir, generator patches it (adds entry points + extras)
instead of overwriting.

## After Generation

1. Run tests — they should FAIL (TDD stubs)
2. Implement action functions in `${NAME}.py`
3. Run tests again — they should PASS
4. Run `validate_tool.py` for compliance check
