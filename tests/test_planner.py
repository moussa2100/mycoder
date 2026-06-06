"""Tests for the TaskPlanner."""

import pytest

from pgimcode.planner import Plan, TaskPlanner, STEP_TEMPLATES


class TestTaskPlanner:
    """Test suite for TaskPlanner."""

    def test_plan_from_task(self):
        """Test simple task with keywords generates plan with steps, criteria, confidence."""
        planner = TaskPlanner()
        task = "add user authentication to the app"
        plan = planner.plan(task)

        assert plan.task == task
        assert len(plan.steps) > 0
        assert len(plan.acceptance_criteria) > 0
        assert 0.0 <= plan.confidence <= 1.0
        assert plan.interpretation != ""
        assert plan.objective != ""

    def test_plan_add_verb(self):
        """Test that 'add' verb triggers add new functionality template."""
        planner = TaskPlanner()
        task = "build new login feature"
        plan = planner.plan(task)

        # Check interpretation says "add new functionality"
        assert "add new functionality" in plan.interpretation.lower()

        # Check steps match add template
        expected_steps = [s.description for s in STEP_TEMPLATES["add new functionality"]]
        actual_steps = [s.description for s in plan.steps]
        assert actual_steps == expected_steps

        # Check steps match add template
        expected_steps = [s.description for s in STEP_TEMPLATES["add new functionality"]]
        actual_steps = [s.description for s in plan.steps]
        assert actual_steps == expected_steps

    def test_plan_fix_verb(self):
        """Test that 'fix bug' triggers fix a bug template."""
        planner = TaskPlanner()
        task = "fix bug in the parser"
        plan = planner.plan(task)

        # Check steps match fix template
        expected_steps = [s.description for s in STEP_TEMPLATES["fix a bug"]]
        actual_steps = [s.description for s in plan.steps]
        assert actual_steps == expected_steps

    def test_plan_to_markdown(self):
        """Test that to_markdown output contains expected sections."""
        planner = TaskPlanner()
        task = "update configuration handling"
        plan = planner.plan(task)

        md = plan.to_markdown()

        assert "Plan:" in md
        assert "Steps" in md
        assert "Acceptance Criteria" in md
        assert "Confidence" in md
        assert "Interpretation:" in md
        assert "Objective:" in md

    def test_plan_confidence_no_context(self):
        """Test that confidence is low but positive when no repo context provided."""
        planner = TaskPlanner()
        task = "add new feature"
        plan = planner.plan(task)

        # With no repo context, confidence should be > 0 (minimum 0.3)
        assert plan.confidence > 0
        assert plan.confidence <= 1.0