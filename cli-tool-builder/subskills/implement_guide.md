---
name: implement_guide
description: "Guide for implementing action logic in generated CLI tool."
---

# Implementation Guide

## Pattern: Pure Action Functions

Each action is a pure function: inputs → Result.

```python
def list_items(**kwargs) -> Result:
    """List all items. Supports --format and --quiet."""
    # Your logic here
    items = [...]
    return Result(data=items, metadata={"count": len(items)})
```

## Checklist Per Action

- [ ] Returns Result (not raw data)
- [ ] Handles missing/invalid args → Result(error=..., exit_code=2)
- [ ] Suggests fix in error: `"Missing <id>. Try: mytool list"`
- [ ] Destructive actions check `--yes` flag
- [ ] No print() — return Result, let cli.py handle output

## Testing

Run tests after each action: `pytest tests/test_core.py -v`
Tests are pre-written stubs — fill in expected values as you implement.
