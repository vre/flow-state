"""Shared fixtures for skill-builder tests."""

import pytest


@pytest.fixture
def valid_skill():
    """Minimal valid SKILL.md content."""
    return """---
name: creating-widgets
description: Use when building new widgets or converting existing components into reusable widgets
keywords: widget, component, reusable, build
---

# Creating Widgets

## Step 1: Gather requirements

AskUserQuestion: "What should the widget do?"

## Step 2: Generate

```bash
python3 ./scripts/generate_widget.py "${NAME}"
```

Creates: `widgets/${NAME}/widget.py`

## Step 3: Validate

```bash
python3 ./scripts/validate_widget.py "${NAME}"
```

Creates: `widgets/${NAME}/validation.json`

DONE.
"""


@pytest.fixture
def skill_bad_description():
    """Skill with workflow summary in description (Description Trap)."""
    return """---
name: creating-widgets
description: Use when creating widgets - gathers requirements, generates skeleton, validates output
keywords: widget
---

# Creating Widgets

DONE.
"""


@pytest.fixture
def skill_prose_heavy():
    """Skill with explanatory prose patterns."""
    return """---
name: creating-widgets
description: Use when building new widgets
keywords: widget
---

# Creating Widgets

## Step 1: Setup

This step will initialize the project structure.
The script handles all configuration automatically.
This will create the necessary files.
"""


@pytest.fixture
def skill_bad_name():
    """Skill with invalid name (single segment, not kebab-case)."""
    return """---
name: widget
description: Use when building new widgets
keywords: widget
---

# Widget

DONE.
"""


@pytest.fixture
def skill_no_frontmatter():
    """Skill missing frontmatter."""
    return """# Creating Widgets

## Step 1: Do stuff

DONE.
"""


@pytest.fixture
def skill_over_budget():
    """Skill that exceeds token budget."""
    # ~400 tokens worth of text (1600+ chars)
    padding = "Lorem ipsum dolor sit amet consectetur. " * 40
    return f"""---
name: creating-widgets
description: Use when building new widgets
keywords: widget
---

# Creating Widgets

{padding}

DONE.
"""
