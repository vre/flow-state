"""Tests for generate_skill.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "builder-skill" / "scripts"))

from generate_skill import generate_skill_md


class TestGenerateSkillMd:
    def test_returns_string(self):
        result = generate_skill_md(
            name="creating-widgets",
            trigger="building new widgets or converting components into reusable widgets",
            outputs=["widget.py"],
            flow_type="sequential",
        )
        assert isinstance(result, str)

    def test_has_frontmatter(self):
        result = generate_skill_md(
            name="creating-widgets",
            trigger="building new widgets",
            outputs=["widget.py"],
            flow_type="sequential",
        )
        assert result.startswith("---\n")
        assert "\n---\n" in result[3:]

    def test_name_in_frontmatter(self):
        result = generate_skill_md(
            name="creating-widgets",
            trigger="building new widgets",
            outputs=["widget.py"],
            flow_type="sequential",
        )
        assert "name: creating-widgets" in result

    def test_description_starts_with_use_when(self):
        result = generate_skill_md(
            name="creating-widgets",
            trigger="building new widgets",
            outputs=["widget.py"],
            flow_type="sequential",
        )
        lines = result.split("\n")
        desc_lines = [line for line in lines if line.startswith("description:")]
        assert len(desc_lines) == 1
        assert "Use when" in desc_lines[0]

    def test_keywords_in_frontmatter(self):
        result = generate_skill_md(
            name="creating-widgets",
            trigger="building new widgets",
            outputs=["widget.py"],
            flow_type="sequential",
        )
        assert "keywords:" in result

    def test_has_done_condition(self):
        result = generate_skill_md(
            name="creating-widgets",
            trigger="building new widgets",
            outputs=["widget.py"],
            flow_type="sequential",
        )
        assert "DONE" in result

    def test_has_creates_line(self):
        result = generate_skill_md(
            name="creating-widgets",
            trigger="building new widgets",
            outputs=["widget.py", "config.json"],
            flow_type="sequential",
        )
        assert "Creates:" in result


class TestTokenBudget:
    def test_under_300_tokens(self):
        result = generate_skill_md(
            name="creating-widgets",
            trigger="building new widgets",
            outputs=["widget.py"],
            flow_type="sequential",
        )
        token_est = len(result) / 4
        assert token_est < 300, f"Token estimate {int(token_est)} exceeds 300"

    def test_multiple_outputs_still_under_budget(self):
        result = generate_skill_md(
            name="creating-widgets",
            trigger="building new widgets",
            outputs=["widget.py", "config.json", "test_widget.py"],
            flow_type="sequential",
        )
        token_est = len(result) / 4
        assert token_est < 300, f"Token estimate {int(token_est)} exceeds 300"


class TestFlowTypes:
    def test_sequential_flow(self):
        result = generate_skill_md(
            name="creating-widgets",
            trigger="building new widgets",
            outputs=["widget.py"],
            flow_type="sequential",
        )
        assert "Step 1" in result

    def test_parallel_flow_marker(self):
        result = generate_skill_md(
            name="creating-widgets",
            trigger="building new widgets",
            outputs=["widget.py"],
            flow_type="parallel",
        )
        # Parallel flows should indicate concurrency
        assert "|" in result or "concurrent" in result.lower() or "parallel" in result.lower()


class TestNoProsePatterns:
    def test_no_this_step(self):
        result = generate_skill_md(
            name="creating-widgets",
            trigger="building new widgets",
            outputs=["widget.py"],
            flow_type="sequential",
        )
        for line in result.split("\n"):
            assert not line.strip().startswith("This step")

    def test_no_the_script(self):
        result = generate_skill_md(
            name="creating-widgets",
            trigger="building new widgets",
            outputs=["widget.py"],
            flow_type="sequential",
        )
        for line in result.split("\n"):
            assert not line.strip().startswith("The script")

    def test_no_this_will(self):
        result = generate_skill_md(
            name="creating-widgets",
            trigger="building new widgets",
            outputs=["widget.py"],
            flow_type="sequential",
        )
        for line in result.split("\n"):
            assert not line.strip().startswith("This will")


class TestJsonInput:
    def test_from_dict(self):
        spec = {
            "name": "building-apis",
            "trigger": "creating REST APIs",
            "outputs": ["api.py"],
            "flow_type": "sequential",
        }
        result = generate_skill_md(**spec)
        assert "name: building-apis" in result
        assert "Use when" in result
