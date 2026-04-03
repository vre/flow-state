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
SUBSKILL_CHAR_LIMIT = 8000
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
TASK_CONTEXT_RE = re.compile(r"\btask[_ ]tool\b", re.IGNORECASE)
TASK_LINE_RE = re.compile(r"^\s*TASK\s*:", re.IGNORECASE | re.MULTILINE)
INPUT_LINE_RE = re.compile(r"^\s*INPUT[A-Z_]*\s*:", re.IGNORECASE | re.MULTILINE)
OUTPUT_LINE_RE = re.compile(r"^\s*OUTPUT[A-Z_]*\s*:", re.IGNORECASE | re.MULTILINE)
RUN_IN_BACKGROUND_RE = re.compile(r"run_in_background\s*:\s*true", re.IGNORECASE)
CONSTRAINED_OUTPUT_RE = re.compile(r"do not output text during execution", re.IGNORECASE)
FINAL_MESSAGE_RE = re.compile(
    r"your final message must be only one of|final message:|on failure:",
    re.IGNORECASE,
)
PERMISSION_TEST_RE = re.compile(r"permission test", re.IGNORECASE)
MODE_A_RE = re.compile(r"\bmode a\b", re.IGNORECASE)
MODE_B_RE = re.compile(r"\bmode b\b", re.IGNORECASE)


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


def _iter_code_blocks(lines: list[str]) -> list[dict[str, object]]:
    """Extract fenced code blocks with line numbers and nearby context."""
    blocks: list[dict[str, object]] = []
    in_code_block = False
    lang = ""
    start_line = 0
    context_lines: list[str] = []
    content_lines: list[str] = []

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("```"):
            if not in_code_block:
                in_code_block = True
                start_line = i
                lang = stripped[3:].strip().lower()
                context_lines = lines[max(0, i - 6) : i - 1]
                content_lines = []
            else:
                blocks.append(
                    {
                        "lang": lang,
                        "content": "\n".join(content_lines),
                        "start_line": start_line,
                        "end_line": i,
                        "context": context_lines,
                    }
                )
                in_code_block = False
            continue

        if in_code_block:
            content_lines.append(line)

    return blocks


def _format_issue(line: int, msg: str, prefix: str | None = None, severity: str | None = None) -> dict:
    """Build an issue dict with optional filename prefix and severity."""
    issue = {"line": line, "msg": f"[{prefix}] {msg}" if prefix else msg}
    if severity:
        issue["severity"] = severity
    return issue


def _is_task_block(block: dict[str, object]) -> bool:
    """Return True when a fenced block looks like a Task/tool prompt."""
    context_text = "\n".join(block["context"])  # type: ignore[arg-type]
    content = str(block["content"])
    return bool(TASK_CONTEXT_RE.search(context_text) or TASK_LINE_RE.search(content))


def check_content_patterns(text: str, prefix: str | None = None) -> list[dict]:
    """Run targeted content checks on fenced task and bash blocks."""
    issues: list[dict] = []
    lines = text.split("\n")

    for block in _iter_code_blocks(lines):
        content = str(block["content"])
        context_text = "\n".join(block["context"])  # type: ignore[arg-type]
        start_line = int(block["start_line"])
        end_line = int(block["end_line"])
        lang = str(block["lang"]).split()[0] if str(block["lang"]).strip() else ""

        if lang == "bash":
            next_nonempty = ""
            for line in lines[end_line:]:
                if line.strip():
                    next_nonempty = line.strip()
                    break
            if not next_nonempty.lower().startswith("creates:"):
                issues.append(
                    _format_issue(
                        end_line,
                        "creates_after_bash: Bash block should be followed by a Creates: line",
                        prefix=prefix,
                        severity="warning",
                    )
                )

        if not _is_task_block(block):
            continue

        has_input = bool(INPUT_LINE_RE.search(content))
        has_output = bool(OUTPUT_LINE_RE.search(content))
        if not (has_input and has_output):
            issues.append(
                _format_issue(
                    start_line,
                    "subagent_has_io: Task block must include INPUT and OUTPUT paths",
                    prefix=prefix,
                )
            )

        if not (CONSTRAINED_OUTPUT_RE.search(content) and FINAL_MESSAGE_RE.search(content)):
            issues.append(
                _format_issue(
                    start_line,
                    "subagent_output_constrained: Task block should constrain the final message format",
                    prefix=prefix,
                    severity="warning",
                )
            )

        if RUN_IN_BACKGROUND_RE.search(context_text) or RUN_IN_BACKGROUND_RE.search(content):
            has_degradation = bool(PERMISSION_TEST_RE.search(content) and MODE_A_RE.search(content) and MODE_B_RE.search(content))
            if not has_degradation:
                issues.append(
                    _format_issue(
                        start_line,
                        "background_has_degradation: Background task should include Permission Test and Mode A/B fallback",
                        prefix=prefix,
                        severity="warning",
                    )
                )

    return issues


def check_subskill_validity(subskill_refs: list[str], skill_dir: Path) -> list[dict]:
    """Light validation on referenced subskill markdown files.

    NOT recursive SKILL.md validation (subskills lack frontmatter).
    Checks: not empty, has heading, under 8000 chars, targeted content checks.

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
        if len(content) > SUBSKILL_CHAR_LIMIT:
            issues.append(
                {
                    "line": 0,
                    "msg": f"[{filename}] Subskill too long: {len(content)} chars (max {SUBSKILL_CHAR_LIMIT})",
                }
            )
        issues.extend(check_content_patterns(content, prefix=filename))
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

    skill_dir_name = skill_dir.resolve().name
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

    issues.extend(check_content_patterns(text))

    # Referenced paths + collect refs for deeper checks
    script_refs: list[str] = []
    subskill_refs: list[str] = []
    seen_script_refs: set[str] = set()
    seen_subskill_refs: set[str] = set()
    if skill_dir:
        for i, line in enumerate(lines, start=1):
            for match in PATH_REF_RE.finditer(line):
                ref = match.group(1) or match.group(2)
                prefix = "scripts" if match.group(1) else "subskills"
                ref_path = skill_dir / prefix / ref
                if match.group(1):
                    if ref not in seen_script_refs:
                        script_refs.append(f"{prefix}/{ref}")
                        seen_script_refs.add(ref)
                else:
                    if ref not in seen_subskill_refs:
                        subskill_refs.append(f"{prefix}/{ref}")
                        seen_subskill_refs.add(ref)
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
