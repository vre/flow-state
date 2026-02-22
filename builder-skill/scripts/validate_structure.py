#!/usr/bin/env python3
"""Validate SKILL.md structure: tokens, frontmatter, prose, naming, paths."""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

TOKEN_BUDGET_WORKFLOW = 300
TOKEN_BUDGET_BUILDER = 500
_VERB = r"(gathers?|generates?|validates?|creates?|processes?|builds?|checks?|runs?|executes?)"
_SEP = r"(,|\band\b|\bthen\b)"
WORKFLOW_VERBS = re.compile(
    rf"\b{_VERB}\b.*{_SEP}.*\b{_VERB}\b",
    re.IGNORECASE,
)
PROSE_PATTERNS = [
    re.compile(r"^\s*This step\b", re.IGNORECASE),
    re.compile(r"^\s*The script\b", re.IGNORECASE),
    re.compile(r"^\s*This will\b", re.IGNORECASE),
]
KEBAB_RE = re.compile(r"^[a-z]+(-[a-z]+)+$")
PATH_REF_RE = re.compile(r"\./scripts/([^\s\"'`]+\.py)|\./subskills/([^\s\"'`]+\.md)")


def _parse_frontmatter(text: str) -> tuple[dict[str, str], int]:
    """Parse YAML frontmatter between --- delimiters.

    Handles both inline values (key: value) and YAML lists (key:\\n  - item).

    Returns:
        Tuple of (parsed fields dict, line number of closing ---).
    """
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, 0

    fields: dict[str, str] = {}
    current_key: str | None = None
    list_items: list[str] = []

    for i, line in enumerate(lines[1:], start=2):
        stripped = line.strip()
        if stripped == "---":
            # Flush pending list
            if current_key and list_items:
                fields[current_key] = ", ".join(list_items)
            return fields, i

        if stripped.startswith("- ") and current_key is not None:
            list_items.append(stripped[2:].strip())
        elif ":" in line:
            # Flush previous list
            if current_key and list_items:
                fields[current_key] = ", ".join(list_items)
                list_items = []
            key, _, value = line.partition(":")
            current_key = key.strip()
            value = value.strip()
            if value:
                fields[current_key] = value
                current_key = None
            else:
                fields[current_key] = ""
    return {}, 0


def check_script_syntax(script_refs: list[str], skill_dir: Path) -> list[dict]:
    """Check Python scripts referenced in SKILL.md for syntax errors.

    Args:
        script_refs: Relative paths like 'scripts/foo.py' extracted via PATH_REF_RE.
        skill_dir: Directory containing the skill.

    Returns:
        List of issue dicts with line=0, msg containing filename and error.
    """
    issues: list[dict] = []
    for ref in script_refs:
        path = skill_dir / ref
        if not path.exists():
            continue  # path check handles missing files
        try:
            source = path.read_text(encoding="utf-8")
            ast.parse(source, filename=ref)
        except SyntaxError as e:
            issues.append({"line": 0, "msg": f"Syntax error in {ref}: line {e.lineno}: {e.msg}"})
    return issues


def check_subskill_validity(subskill_refs: list[str], skill_dir: Path) -> list[dict]:
    """Light validation on referenced subskill markdown files.

    NOT recursive SKILL.md validation (subskills lack frontmatter).
    Checks: not empty, has heading, under 2000 chars (~500 tokens).

    Args:
        subskill_refs: Relative paths like 'subskills/foo.md'.
        skill_dir: Directory containing the skill.

    Returns:
        List of issue dicts prefixed with [filename].
    """
    issues: list[dict] = []
    for ref in subskill_refs:
        path = skill_dir / ref
        if not path.exists():
            continue  # path check handles missing files
        filename = Path(ref).name
        content = path.read_text(encoding="utf-8")
        if not content.strip():
            issues.append({"line": 0, "msg": f"[{filename}] Subskill is empty"})
            continue
        has_heading = any(line.strip().startswith("#") for line in content.split("\n"))
        if not has_heading:
            issues.append({"line": 0, "msg": f"[{filename}] Subskill has no markdown headings"})
        if len(content) > 2000:
            issues.append(
                {
                    "line": 0,
                    "msg": f"[{filename}] Subskill too long: {len(content)} chars (max 2000)",
                }
            )
    return issues


def check_test_coverage(skill_dir: Path) -> list[dict]:
    """Warn if scripts/ exists but no test directory found.

    Checks three locations:
    1. {skill_dir}/tests/
    2. {skill_dir}/../tests/
    3. {skill_dir}/../../tests/{skill_dir_name}/  (repo-root pattern)

    Args:
        skill_dir: Directory containing the skill.

    Returns:
        List of warning-severity issue dicts.
    """
    scripts_dir = skill_dir / "scripts"
    if not scripts_dir.is_dir():
        return []

    skill_dir_name = skill_dir.name
    test_locations = [
        skill_dir / "tests",
        skill_dir.parent / "tests",
        skill_dir.parent.parent / "tests" / skill_dir_name,
    ]
    for loc in test_locations:
        if loc.is_dir():
            return []

    return [
        {
            "line": 0,
            "severity": "warning",
            "msg": f"No test directory found for scripts in {skill_dir_name}/",
        }
    ]


def _detect_token_budget(text: str, fields: dict[str, str]) -> int:
    """Detect appropriate token budget based on skill type.

    Builder skills get TOKEN_BUDGET_BUILDER (500). Detection:
    - Name ends with "-builder", OR
    - Body contains ./scripts/ path references.

    Args:
        text: Raw SKILL.md content.
        fields: Parsed frontmatter fields.

    Returns:
        Token budget (300 for workflow, 500 for builder).
    """
    name = fields.get("name", "")
    if name.endswith("-builder"):
        return TOKEN_BUDGET_BUILDER
    if re.search(r"\./scripts/", text):
        return TOKEN_BUDGET_BUILDER
    return TOKEN_BUDGET_WORKFLOW


def validate(text: str, skill_dir: Path | None = None) -> dict:
    """Validate skill text content.

    Args:
        text: Raw SKILL.md content.
        skill_dir: Directory containing the skill (for path checks).

    Returns:
        Dict with "pass" (bool) and "issues" (list of {line, msg}).
    """
    issues: list[dict] = []
    lines = text.split("\n")

    # Frontmatter (parse first — needed for budget detection)
    fields, fm_end = _parse_frontmatter(text)

    # Token estimation (tiered: workflow=300, builder=500)
    budget = _detect_token_budget(text, fields)
    token_est = len(text) / 4
    if token_est > budget:
        issues.append({"line": 0, "msg": f"Token budget exceeded: ~{int(token_est)} > {budget}"})

    # Frontmatter validation
    if not fields:
        issues.append({"line": 1, "msg": "Missing frontmatter (no --- delimiters found)"})
    else:
        for required in ("name", "description", "keywords"):
            if required not in fields:
                issues.append({"line": 1, "msg": f"Frontmatter missing '{required}'"})

        # Description format
        desc = fields.get("description", "")
        if desc and not desc.startswith("Use when"):
            issues.append({"line": 1, "msg": "Description should start with 'Use when'"})
        if desc and WORKFLOW_VERBS.search(desc):
            issues.append({"line": 1, "msg": "Description contains workflow summary (Description Trap)"})

        # Kebab-case naming: lowercase, hyphen-separated, >=2 segments
        name = fields.get("name", "")
        if name and not KEBAB_RE.match(name):
            issues.append(
                {
                    "line": 1,
                    "msg": f"Name '{name}' must be kebab-case with >=2 segments (e.g. 'log-analyzer', 'skill-builder')",
                }
            )

    # Prose detection (skip code blocks)
    in_code_block = False
    for i, line in enumerate(lines, start=1):
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        for pattern in PROSE_PATTERNS:
            if pattern.search(line):
                issues.append({"line": i, "msg": f"Prose pattern detected: '{line.strip()}'"})
                break

    # Referenced paths + collect refs for deeper checks
    script_refs: list[str] = []
    subskill_refs: list[str] = []
    if skill_dir:
        for i, line in enumerate(lines, start=1):
            for match in PATH_REF_RE.finditer(line):
                ref = match.group(1) or match.group(2)
                prefix = "scripts" if match.group(1) else "subskills"
                ref_path = skill_dir / prefix / ref
                if match.group(1):
                    script_refs.append(f"{prefix}/{ref}")
                else:
                    subskill_refs.append(f"{prefix}/{ref}")
                if not ref_path.exists():
                    issues.append({"line": i, "msg": f"Referenced path missing: {prefix}/{ref}"})

        # Script syntax check
        issues.extend(check_script_syntax(script_refs, skill_dir))

        # Subskill validity check
        issues.extend(check_subskill_validity(subskill_refs, skill_dir))

        # Test coverage check
        issues.extend(check_test_coverage(skill_dir))

    errors = [i for i in issues if i.get("severity") != "warning"]
    return {"pass": len(errors) == 0, "issues": issues}


def validate_file(file_path: str) -> dict:
    """Validate a SKILL.md file on disk.

    Args:
        file_path: Path to SKILL.md.

    Returns:
        Validation result dict.
    """
    path = Path(file_path)
    if not path.exists():
        print(f"Error: {file_path} not found", file=sys.stderr)
        raise SystemExit(1)

    if path.is_dir():
        skill_md = path / "SKILL.md"
        if skill_md.exists():
            path = skill_md
        else:
            print(
                f"Error: {file_path} is a directory with no SKILL.md. Try: validate_structure.py {file_path}/SKILL.md",
                file=sys.stderr,
            )
            raise SystemExit(1)

    text = path.read_text(encoding="utf-8")
    skill_dir = path.parent
    return validate(text, skill_dir=skill_dir)


def main() -> None:
    """CLI entry point."""
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} SKILL.md", file=sys.stderr)
        raise SystemExit(2)

    result = validate_file(sys.argv[1])
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["pass"] else 1)


if __name__ == "__main__":
    main()
