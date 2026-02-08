#!/usr/bin/env python3
"""Generate minimal SKILL.md skeleton from structured input."""

from __future__ import annotations

import json
import sys


def generate_skill_md(
    name: str,
    trigger: str,
    outputs: list[str],
    flow_type: str = "sequential",
) -> str:
    """Generate a SKILL.md skeleton.

    Args:
        name: Skill name in kebab-case (e.g. "worktree-manager").
        trigger: What triggers this skill (becomes "Use when {trigger}").
        outputs: List of files/artifacts the skill produces.
        flow_type: "sequential" or "parallel".

    Returns:
        SKILL.md content string.
    """
    # Frontmatter
    lines = [
        "---",
        f"name: {name}",
        f"description: Use when {trigger}",
        "keywords:",
        "---",
        "",
        f"# {_to_title(name)}",
        "",
    ]

    # Steps
    if flow_type == "parallel":
        lines.extend(
            [
                "## Step 1: Execute (parallel)",
                "",
                "Run concurrently:",
                "",
            ]
        )
        for i, output in enumerate(outputs, start=1):
            lines.append(f"- Task {i} | Creates: `{output}`")
        lines.extend(["", "DONE."])
    else:
        lines.extend(
            [
                "## Step 1: Execute",
                "",
                f"Creates: {', '.join(f'`{o}`' for o in outputs)}",
                "",
                "DONE.",
            ]
        )

    return "\n".join(lines) + "\n"


def _to_title(name: str) -> str:
    """Convert kebab-case name to Title Case."""
    return " ".join(w.capitalize() for w in name.split("-"))


def main() -> None:
    """CLI entry point. Reads JSON from stdin or file argument."""
    if len(sys.argv) == 2:
        with open(sys.argv[1]) as f:
            spec = json.load(f)
    elif not sys.stdin.isatty():
        spec = json.load(sys.stdin)
    else:
        print(f"Usage: {sys.argv[0]} <spec.json>  or  echo '{{...}}' | {sys.argv[0]}", file=sys.stderr)
        raise SystemExit(2)

    result = generate_skill_md(**spec)
    print(result, end="")


if __name__ == "__main__":
    main()
