"""Tests for validate_structure.py."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "builder-skill" / "scripts"))

from validate_structure import (
    check_script_syntax,
    check_subskill_validity,
    check_test_coverage,
    validate,
    validate_file,
)


class TestTokenEstimation:
    def test_short_skill_under_budget(self, valid_skill):
        result = validate(valid_skill)
        token_issues = [i for i in result["issues"] if "token" in i["msg"].lower()]
        assert len(token_issues) == 0

    def test_over_budget_skill_fails(self, skill_over_budget):
        result = validate(skill_over_budget)
        assert result["pass"] is False
        token_issues = [i for i in result["issues"] if "token" in i["msg"].lower()]
        assert len(token_issues) > 0

    def test_empty_string_passes_token_check(self):
        result = validate("")
        token_issues = [i for i in result["issues"] if "token" in i["msg"].lower()]
        assert len(token_issues) == 0


class TestFrontmatter:
    def test_valid_frontmatter_passes(self, valid_skill):
        result = validate(valid_skill)
        fm_issues = [i for i in result["issues"] if "frontmatter" in i["msg"].lower()]
        assert len(fm_issues) == 0

    def test_missing_frontmatter_fails(self, skill_no_frontmatter):
        result = validate(skill_no_frontmatter)
        assert result["pass"] is False
        fm_issues = [i for i in result["issues"] if "frontmatter" in i["msg"].lower()]
        assert len(fm_issues) > 0

    def test_missing_name_fails(self):
        skill = """---
description: Use when building widgets
keywords: widget
---

# Widgets
"""
        result = validate(skill)
        assert any("name" in i["msg"].lower() for i in result["issues"])

    def test_missing_description_fails(self):
        skill = """---
name: creating-widgets
keywords: widget
---

# Widgets
"""
        result = validate(skill)
        assert any("description" in i["msg"].lower() for i in result["issues"])

    def test_missing_keywords_fails(self):
        skill = """---
name: creating-widgets
description: Use when building widgets
---

# Widgets
"""
        result = validate(skill)
        assert any("keywords" in i["msg"].lower() for i in result["issues"])

    def test_yaml_list_keywords_parsed(self):
        """Keywords as YAML list should be captured as non-empty value."""
        skill = """---
name: creating-widgets
description: Use when building widgets
keywords:
  - widget
  - component
---

# Widgets
"""
        result = validate(skill)
        # Must not report keywords as missing OR empty
        kw_issues = [i for i in result["issues"] if "keywords" in i["msg"].lower()]
        assert len(kw_issues) == 0

    def test_allowed_tools_list_not_breaking(self):
        """YAML list fields should not break parsing of other fields."""
        skill = """---
name: creating-widgets
description: Use when building widgets
keywords: widget
allowed-tools:
  - Bash
  - Read
---

# Widgets
"""
        result = validate(skill)
        fm_issues = [i for i in result["issues"] if "frontmatter" in i["msg"].lower()]
        assert len(fm_issues) == 0


class TestDescriptionFormat:
    def test_valid_description_passes(self, valid_skill):
        result = validate(valid_skill)
        desc_issues = [i for i in result["issues"] if "description" in i["msg"].lower() and "workflow" in i["msg"].lower()]
        assert len(desc_issues) == 0

    def test_workflow_in_description_fails(self, skill_bad_description):
        result = validate(skill_bad_description)
        assert result["pass"] is False
        desc_issues = [i for i in result["issues"] if "workflow" in i["msg"].lower() or "description" in i["msg"].lower()]
        assert len(desc_issues) > 0

    def test_workflow_with_and_connector_fails(self):
        skill = """---
name: creating-widgets
description: Use when creating widgets - gathers requirements and generates skeleton
keywords: widget
---

# Widgets
"""
        result = validate(skill)
        assert any("workflow" in i["msg"].lower() for i in result["issues"])

    def test_workflow_with_then_connector_fails(self):
        skill = """---
name: creating-widgets
description: Use when creating widgets - gathers requirements then validates output
keywords: widget
---

# Widgets
"""
        result = validate(skill)
        assert any("workflow" in i["msg"].lower() for i in result["issues"])

    def test_description_without_use_when_warns(self):
        skill = """---
name: creating-widgets
description: Creates widgets from templates
keywords: widget
---

# Widgets
"""
        result = validate(skill)
        assert any("Use when" in i["msg"] for i in result["issues"])


class TestProseDetection:
    def test_no_prose_passes(self, valid_skill):
        result = validate(valid_skill)
        prose_issues = [i for i in result["issues"] if "prose" in i["msg"].lower()]
        assert len(prose_issues) == 0

    def test_this_step_detected(self, skill_prose_heavy):
        result = validate(skill_prose_heavy)
        assert result["pass"] is False
        prose_issues = [i for i in result["issues"] if "prose" in i["msg"].lower()]
        assert len(prose_issues) > 0

    def test_the_script_detected(self):
        skill = """---
name: creating-widgets
description: Use when building widgets
keywords: widget
---

# Widgets

The script handles all the heavy lifting.
"""
        result = validate(skill)
        assert any("prose" in i["msg"].lower() for i in result["issues"])

    def test_this_will_detected(self):
        skill = """---
name: creating-widgets
description: Use when building widgets
keywords: widget
---

# Widgets

This will generate the output files.
"""
        result = validate(skill)
        assert any("prose" in i["msg"].lower() for i in result["issues"])

    def test_prose_inside_code_block_not_flagged(self):
        skill = """---
name: creating-widgets
description: Use when building widgets
keywords: widget
---

# Widgets

```
This step is inside a code block
The script output goes here
This will not be real prose
```

DONE.
"""
        result = validate(skill)
        prose_issues = [i for i in result["issues"] if "prose" in i["msg"].lower()]
        assert len(prose_issues) == 0

    def test_prose_after_code_block_still_flagged(self):
        skill = """---
name: creating-widgets
description: Use when building widgets
keywords: widget
---

# Widgets

```bash
echo "safe"
```

This step should still be caught.
"""
        result = validate(skill)
        prose_issues = [i for i in result["issues"] if "prose" in i["msg"].lower()]
        assert len(prose_issues) > 0


class TestNaming:
    def test_kebab_case_passes(self, valid_skill):
        """valid_skill uses 'creating-widgets' — valid kebab-case with >=2 segments."""
        result = validate(valid_skill)
        name_issues = [i for i in result["issues"] if "kebab" in i["msg"].lower() or "name" in i["msg"].lower()]
        assert len(name_issues) == 0

    def test_single_segment_fails(self, skill_bad_name):
        """skill_bad_name uses 'widget' — single segment, must fail."""
        result = validate(skill_bad_name)
        assert result["pass"] is False
        assert any("kebab" in i["msg"].lower() for i in result["issues"])

    def test_uppercase_fails(self):
        skill = """---
name: LOUD-NAME
description: Use when building things
keywords: thing
---

# Loud Name

DONE.
"""
        result = validate(skill)
        assert result["pass"] is False
        assert any("kebab" in i["msg"].lower() for i in result["issues"])

    def test_log_analyzer_passes(self):
        skill = """---
name: log-analyzer
description: Use when analyzing logs
keywords: log, analyze
---

# Log Analyzer

DONE.
"""
        result = validate(skill)
        name_issues = [i for i in result["issues"] if "name" in i["msg"].lower()]
        assert len(name_issues) == 0

    def test_widget_creator_passes(self):
        skill = """---
name: widget-creator
description: Use when building new widgets
keywords: widget
---

# Widget Creator

DONE.
"""
        result = validate(skill)
        name_issues = [i for i in result["issues"] if "name" in i["msg"].lower()]
        assert len(name_issues) == 0

    def test_skill_builder_passes(self):
        skill = """---
name: skill-builder
description: Use when scaffolding skills
keywords: skill, scaffold
---

# Skill Builder

DONE.
"""
        result = validate(skill)
        name_issues = [i for i in result["issues"] if "name" in i["msg"].lower()]
        assert len(name_issues) == 0

    def test_creating_widgets_passes(self):
        skill = """---
name: creating-widgets
description: Use when building widgets
keywords: widget
---

# Creating Widgets

DONE.
"""
        result = validate(skill)
        name_issues = [i for i in result["issues"] if "name" in i["msg"].lower()]
        assert len(name_issues) == 0

    def test_three_segments_passes(self):
        skill = """---
name: building-cool-apis
description: Use when building APIs
keywords: api
---

# Building Cool APIs

DONE.
"""
        result = validate(skill)
        name_issues = [i for i in result["issues"] if "name" in i["msg"].lower()]
        assert len(name_issues) == 0


class TestReferencedPaths:
    def test_existing_paths_pass(self, tmp_path, valid_skill):
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "scripts").mkdir()
        (skill_dir / "scripts" / "generate_widget.py").write_text("# script")
        (skill_dir / "scripts" / "validate_widget.py").write_text("# script")
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(valid_skill)

        result = validate_file(str(skill_file))
        path_issues = [i for i in result["issues"] if "path" in i["msg"].lower() or "missing" in i["msg"].lower()]
        assert len(path_issues) == 0

    def test_missing_script_warns(self, tmp_path):
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        skill_content = """---
name: creating-widgets
description: Use when building widgets
keywords: widget
---

# Widgets

```bash
python3 ./scripts/nonexistent.py
```
"""
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(skill_content)

        result = validate_file(str(skill_file))
        path_issues = [i for i in result["issues"] if "missing" in i["msg"].lower()]
        assert len(path_issues) > 0


class TestOutputFormat:
    def test_returns_dict_with_pass_and_issues(self, valid_skill):
        result = validate(valid_skill)
        assert "pass" in result
        assert "issues" in result
        assert isinstance(result["pass"], bool)
        assert isinstance(result["issues"], list)

    def test_valid_skill_passes(self, valid_skill):
        result = validate(valid_skill)
        assert result["pass"] is True
        assert len(result["issues"]) == 0

    def test_issues_have_line_and_msg(self, skill_bad_description):
        result = validate(skill_bad_description)
        for issue in result["issues"]:
            assert "line" in issue
            assert "msg" in issue

    def test_json_serializable(self, valid_skill):
        result = validate(valid_skill)
        json_str = json.dumps(result)
        assert json_str is not None


class TestCLI:
    def test_file_not_found_exits(self):
        with pytest.raises(SystemExit):
            validate_file("/nonexistent/SKILL.md")

    def test_directory_with_skill_md_works(self, tmp_path, valid_skill):
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(valid_skill)
        result = validate_file(str(skill_dir))
        assert "pass" in result
        assert "issues" in result

    def test_directory_without_skill_md_exits(self, tmp_path):
        empty_dir = tmp_path / "empty-skill"
        empty_dir.mkdir()
        with pytest.raises(SystemExit):
            validate_file(str(empty_dir))


class TestScriptSyntax:
    def test_valid_script_passes(self, tmp_path):
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "good.py").write_text("x = 1\n")
        issues = check_script_syntax(["scripts/good.py"], tmp_path)
        assert len(issues) == 0

    def test_invalid_script_reports_error(self, tmp_path):
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "bad.py").write_text("def foo(\n")
        issues = check_script_syntax(["scripts/bad.py"], tmp_path)
        assert len(issues) == 1
        assert "bad.py" in issues[0]["msg"]

    def test_no_script_refs_no_issues(self, tmp_path):
        issues = check_script_syntax([], tmp_path)
        assert len(issues) == 0

    def test_multiple_scripts_one_bad(self, tmp_path):
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "good.py").write_text("x = 1\n")
        (scripts_dir / "bad.py").write_text("def foo(\n")
        issues = check_script_syntax(["scripts/good.py", "scripts/bad.py"], tmp_path)
        assert len(issues) == 1

    def test_missing_script_no_crash(self, tmp_path):
        issues = check_script_syntax(["scripts/missing.py"], tmp_path)
        assert len(issues) == 0

    def test_error_includes_filename(self, tmp_path):
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "broken.py").write_text("x =\n")
        issues = check_script_syntax(["scripts/broken.py"], tmp_path)
        assert len(issues) == 1
        assert "broken.py" in issues[0]["msg"]


class TestSubskillValidity:
    def test_valid_subskill_passes(self, tmp_path):
        subskills_dir = tmp_path / "subskills"
        subskills_dir.mkdir()
        (subskills_dir / "good.md").write_text("# Good Subskill\n\nContent here.\n")
        issues = check_subskill_validity(["subskills/good.md"], tmp_path)
        assert len(issues) == 0

    def test_empty_subskill_reports_issue(self, tmp_path):
        subskills_dir = tmp_path / "subskills"
        subskills_dir.mkdir()
        (subskills_dir / "empty.md").write_text("")
        issues = check_subskill_validity(["subskills/empty.md"], tmp_path)
        assert len(issues) == 1
        assert "empty" in issues[0]["msg"].lower()

    def test_missing_subskill_no_crash(self, tmp_path):
        issues = check_subskill_validity(["subskills/missing.md"], tmp_path)
        assert len(issues) == 0

    def test_no_headings_reports_issue(self, tmp_path):
        subskills_dir = tmp_path / "subskills"
        subskills_dir.mkdir()
        (subskills_dir / "nohead.md").write_text("Just plain text without headings.\n")
        issues = check_subskill_validity(["subskills/nohead.md"], tmp_path)
        assert len(issues) == 1
        assert "heading" in issues[0]["msg"].lower()

    def test_issues_prefixed_with_filename(self, tmp_path):
        subskills_dir = tmp_path / "subskills"
        subskills_dir.mkdir()
        (subskills_dir / "bad.md").write_text("No headings here.\n")
        issues = check_subskill_validity(["subskills/bad.md"], tmp_path)
        assert len(issues) == 1
        assert issues[0]["msg"].startswith("[bad.md]")

    def test_subskill_at_8000_chars_passes(self, tmp_path):
        subskills_dir = tmp_path / "subskills"
        subskills_dir.mkdir()
        base = "# Good Subskill\n\n"
        content = base + ("a" * (8000 - len(base)))
        (subskills_dir / "good.md").write_text(content)
        issues = check_subskill_validity(["subskills/good.md"], tmp_path)
        assert len(issues) == 0

    def test_subskill_over_8000_chars_reports_issue(self, tmp_path):
        subskills_dir = tmp_path / "subskills"
        subskills_dir.mkdir()
        base = "# Good Subskill\n\n"
        content = base + ("a" * (8001 - len(base)))
        (subskills_dir / "too_long.md").write_text(content)
        issues = check_subskill_validity(["subskills/too_long.md"], tmp_path)
        assert len(issues) == 1
        assert "max 8000" in issues[0]["msg"]


class TestContentChecks:
    def test_subagent_has_io_errors_when_output_missing(self):
        skill = """---
name: task-checker
description: Use when checking subagent prompts
keywords: task, prompt
---

# Task Checker

Task tool:

```text
INPUT: /tmp/input.md
TASK: Review the file.
Steps:
1. Read INPUT with Read.
Do not output text during execution — only make tool calls.
Your final message must be ONLY one of:
review: wrote /tmp/output.md
review: FAIL - reason
```

DONE.
"""
        result = validate(skill)
        io_issues = [i for i in result["issues"] if "subagent_has_io" in i["msg"]]
        assert result["pass"] is False
        assert len(io_issues) == 1

    def test_subagent_output_constrained_warns_when_missing(self):
        skill = """---
name: task-checker
description: Use when checking subagent prompts
keywords: task, prompt
---

# Task Checker

Task tool:

```text
INPUT: /tmp/input.md
OUTPUT: /tmp/output.md
TASK: Review the file.
Steps:
1. Read INPUT with Read.
2. Write output to OUTPUT with Write.
```

DONE.
"""
        result = validate(skill)
        constrained_issues = [i for i in result["issues"] if "subagent_output_constrained" in i["msg"]]
        assert result["pass"] is True
        assert len(constrained_issues) == 1
        assert constrained_issues[0]["severity"] == "warning"

    def test_creates_after_bash_warns_when_missing(self):
        skill = """---
name: bash-checker
description: Use when checking bash steps
keywords: bash, creates
---

# Bash Checker

```bash
python3 ./scripts/run.py
```

DONE.
"""
        result = validate(skill)
        creates_issues = [i for i in result["issues"] if "creates_after_bash" in i["msg"]]
        assert result["pass"] is True
        assert len(creates_issues) == 1
        assert creates_issues[0]["severity"] == "warning"

    def test_background_has_degradation_warns_without_permission_test(self):
        skill = """---
name: background-checker
description: Use when checking background task prompts
keywords: background, task
---

# Background Checker

Launch a `task_tool`:
- run_in_background: true
- prompt:

```text
INPUT: /tmp/input.md
OUTPUT: /tmp/output.md
TASK: Process the file.
Steps:
1. Read INPUT with Read.
2. Write output to OUTPUT with Write.
Do not output text during execution — only make tool calls.
Your final message must be ONLY one of:
process: wrote /tmp/output.md
process: FAIL - reason
```

DONE.
"""
        result = validate(skill)
        background_issues = [i for i in result["issues"] if "background_has_degradation" in i["msg"]]
        assert result["pass"] is True
        assert len(background_issues) == 1
        assert background_issues[0]["severity"] == "warning"

    def test_content_checks_pass_for_well_formed_skill(self):
        skill = """---
name: task-checker
description: Use when checking subagent prompts
keywords: task, prompt
---

# Task Checker

Launch a `task_tool`:
- run_in_background: true
- prompt:

```text
INPUT: /tmp/input.md
OUTPUT: /tmp/output.md
TASK: Process the file.
PERMISSION TEST: First, Write "test" to OUTPUT. If succeeds -> Mode A. If fails -> Mode B.
Steps:
1. Read INPUT with Read.
2. Write output to OUTPUT with Write.
Mode A: Write to OUTPUT. Final message:
  process: wrote /tmp/output.md
Mode B: Return content. Final message:
  CONTENT:/tmp/output.md
  <content>
  END_CONTENT
Do not output text during execution — only make tool calls.
On failure: process: FAIL - reason
```

```bash
python3 ./scripts/run.py
```

Creates: /tmp/output.md

DONE.
"""
        result = validate(skill)
        content_issues = [
            i
            for i in result["issues"]
            if "subagent_has_io" in i["msg"]
            or "subagent_output_constrained" in i["msg"]
            or "creates_after_bash" in i["msg"]
            or "background_has_degradation" in i["msg"]
        ]
        assert len(content_issues) == 0


class TestTestCoverage:
    def test_scripts_with_tests_same_level(self, tmp_path):
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "scripts").mkdir()
        (skill_dir / "tests").mkdir()
        issues = check_test_coverage(skill_dir)
        assert len(issues) == 0

    def test_scripts_without_tests_warns(self, tmp_path):
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "scripts").mkdir()
        issues = check_test_coverage(skill_dir)
        assert len(issues) == 1
        assert "test" in issues[0]["msg"].lower()

    def test_no_scripts_dir_not_triggered(self, tmp_path):
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        issues = check_test_coverage(skill_dir)
        assert len(issues) == 0

    def test_tests_at_grandparent_with_skill_name(self, tmp_path):
        # Simulates: repo/tests/my-skill/ and repo/my-skill/scripts/
        repo = tmp_path / "repo"
        repo.mkdir()
        skill_dir = repo / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "scripts").mkdir()
        tests_dir = repo / "tests" / "my-skill"
        tests_dir.mkdir(parents=True)
        issues = check_test_coverage(skill_dir)
        assert len(issues) == 0

    def test_warning_severity(self, tmp_path):
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "scripts").mkdir()
        issues = check_test_coverage(skill_dir)
        assert len(issues) == 1
        assert issues[0]["severity"] == "warning"


class TestTieredTokenBudget:
    def _make_skill(self, name: str, body_chars: int, script_ref: bool = False) -> str:
        """Helper to build skill text with controlled size."""
        script_line = "\npython3 ./scripts/gen.py\n" if script_ref else ""
        # frontmatter + heading ~120 chars, pad body to target total
        base = f"""---
name: {name}
description: Use when building things
keywords: thing
---

# Skill
{script_line}
"""
        padding_needed = body_chars - len(base)
        if padding_needed > 0:
            base += "x " * (padding_needed // 2) + "\n"
        return base

    def test_workflow_at_350_tokens_fails(self):
        # 350 tokens = ~1400 chars, workflow budget is 300 tokens = 1200 chars
        skill = self._make_skill("creating-widgets", 1400)
        result = validate(skill)
        token_issues = [i for i in result["issues"] if "token" in i["msg"].lower()]
        assert len(token_issues) == 1
        assert "300" in token_issues[0]["msg"]

    def test_builder_named_at_350_tokens_passes(self):
        # Builder name → 500 token budget, 350 tokens = ~1400 chars < 2000
        skill = self._make_skill("cli-tool-builder", 1400)
        result = validate(skill)
        token_issues = [i for i in result["issues"] if "token" in i["msg"].lower()]
        assert len(token_issues) == 0

    def test_script_ref_at_350_tokens_passes(self):
        # Script reference → builder budget 500
        skill = self._make_skill("creating-things", 1400, script_ref=True)
        result = validate(skill)
        token_issues = [i for i in result["issues"] if "token" in i["msg"].lower()]
        assert len(token_issues) == 0

    def test_builder_at_550_tokens_fails(self):
        # 550 tokens = ~2200 chars, builder budget is 500 = 2000 chars
        skill = self._make_skill("cli-tool-builder", 2200)
        result = validate(skill)
        token_issues = [i for i in result["issues"] if "token" in i["msg"].lower()]
        assert len(token_issues) == 1

    def test_error_shows_correct_limit(self):
        # Builder over budget → message should show 500
        skill = self._make_skill("cli-tool-builder", 2200)
        result = validate(skill)
        token_issues = [i for i in result["issues"] if "token" in i["msg"].lower()]
        assert len(token_issues) == 1
        assert "500" in token_issues[0]["msg"]


class TestRealSkillFiles:
    """Validate actual SKILL.md files in the repo."""

    def test_skill_builder_passes(self):
        skill_md = Path(__file__).parent.parent.parent / "builder-skill" / "SKILL.md"
        if not skill_md.exists():
            pytest.skip("skill-builder/SKILL.md not found")
        result = validate_file(str(skill_md))
        errors = [i for i in result["issues"] if i.get("severity") != "warning"]
        assert len(errors) == 0, f"Errors: {errors}"

    def test_cli_tool_builder_passes_with_builder_budget(self):
        skill_md = Path(__file__).parent.parent.parent / "builder-cli-tool" / "SKILL.md"
        if not skill_md.exists():
            pytest.skip("cli-tool-builder/SKILL.md not found")
        result = validate_file(str(skill_md))
        errors = [i for i in result["issues"] if i.get("severity") != "warning"]
        assert len(errors) == 0, f"Errors: {errors}"
