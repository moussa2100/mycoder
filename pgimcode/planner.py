"""Rules-based task planner."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pgimcode.discovery.repo_map import RepoMap
    from pgimcode.tools.ranker import RankedFile


@dataclass
class Step:
    description: str
    status: str = "pending"  # pending | in_progress | done | skipped
    tool: str | None = None   # read | search | edit | test | verify | ask
    target: str | None = None
    reasoning: str = ""


@dataclass
class Plan:
    task: str
    interpretation: str = ""
    objective: str = ""
    constraints: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    steps: list[Step] = field(default_factory=list)
    files_to_inspect: list[str] = field(default_factory=list)
    next_action: str = ""
    confidence: float = 0.0

    def to_markdown(self) -> str:
        lines = [f"# Plan: {self.task}", ""]

        lines += [f"**Interpretation:** {self.interpretation}", ""]
        lines += [f"**Objective:** {self.objective}", ""]

        if self.constraints:
            lines += ["## Constraints", ""]
            for c in self.constraints:
                lines.append(f"- {c}")
            lines.append("")

        if self.assumptions:
            lines += ["## Assumptions", ""]
            for a in self.assumptions:
                lines.append(f"- {a}")
            lines.append("")

        lines += ["## Steps", ""]
        for i, step in enumerate(self.steps, 1):
            status_icon = {"pending": "○", "in_progress": "◐", "done": "✓", "skipped": "⊘"}.get(step.status, "○")
            lines.append(f"{status_icon} **{step.description}**")
            if step.reasoning:
                lines.append(f"   → {step.reasoning}")
            if step.tool:
                lines.append(f"   tool: `{step.tool}`")
            if step.target:
                lines.append(f"   target: `{step.target}`")
            lines.append("")

        if self.files_to_inspect:
            lines += ["## Files to Inspect", ""]
            for f in self.files_to_inspect:
                lines.append(f"- `{f}`")
            lines.append("")

        if self.acceptance_criteria:
            lines += ["## Acceptance Criteria", ""]
            for ac in self.acceptance_criteria:
                lines.append(f"- [ ] {ac}")
            lines.append("")

        lines += [f"**Next Action:** {self.next_action}", ""]
        lines += [f"**Confidence:** {self.confidence:.0%}", ""]

        return "\n".join(lines)

    def summarize(self) -> str:
        return f"{self.interpretation} ({len(self.steps)} steps, {self.confidence:.0%} confidence)"


VERB_MAP: dict[str, str] = {
    "add": "add new functionality",
    "implement": "add new functionality",
    "create": "add new functionality",
    "build": "add new functionality",
    "fix": "fix a bug",
    "bug": "fix a bug",
    "error": "fix a bug",
    "repair": "fix a bug",
    "refactor": "restructure code",
    "restructure": "restructure code",
    "rewrite": "restructure code",
    "test": "add or fix tests",
    "coverage": "add or fix tests",
    "update": "update existing behavior",
    "change": "update existing behavior",
    "modify": "update existing behavior",
    "remove": "remove functionality",
    "delete": "remove functionality",
    "drop": "remove functionality",
}

STEP_TEMPLATES: dict[str, list[Step]] = {
    "add new functionality": [
        Step("Inspect repository structure", tool="search", reasoning="Understand where changes should go"),
        Step("Read relevant files", tool="read", reasoning="Understand existing patterns"),
        Step("Plan implementation", tool="ask", reasoning="Design the change"),
        Step("Implement changes", tool="edit", reasoning="Apply the planned edits"),
        Step("Run tests", tool="test", reasoning="Verify correctness"),
        Step("Final verification", tool="verify", reasoning="Check no regressions"),
    ],
    "fix a bug": [
        Step("Search for bug location", tool="search", reasoning="Find where the bug manifests"),
        Step("Read relevant code", tool="read", reasoning="Understand root cause"),
        Step("Reproduce bug", tool="test", reasoning="Confirm the issue"),
        Step("Fix the bug", tool="edit", reasoning="Apply minimal fix"),
        Step("Run tests", tool="test", reasoning="Verify fix works"),
        Step("Regression check", tool="verify", reasoning="Check side effects"),
    ],
    "restructure code": [
        Step("Inspect current structure", tool="search", reasoning="Map dependencies"),
        Step("Read affected files", tool="read", reasoning="Understand what changes"),
        Step("Plan refactoring", tool="ask", reasoning="Design new structure"),
        Step("Apply refactoring", tool="edit", reasoning="Move/rename/update code"),
        Step("Run tests", tool="test", reasoning="Verify nothing broke"),
        Step("Final check", tool="verify", reasoning="Validate improvements"),
    ],
    "add or fix tests": [
        Step("Identify untested areas", tool="search", reasoning="Find gaps"),
        Step("Read existing tests", tool="read", reasoning="Follow patterns"),
        Step("Implement tests", tool="edit", reasoning="Add test coverage"),
        Step("Run tests", tool="test", reasoning="Check pass/fail"),
        Step("Fix failures", tool="edit", reasoning="Address issues"),
    ],
    "update existing behavior": [
        Step("Find current implementation", tool="search", reasoning="Locate code to update"),
        Step("Read existing code", tool="read", reasoning="Understand current behavior"),
        Step("Plan changes", tool="ask", reasoning="Design update"),
        Step("Apply update", tool="edit", reasoning="Modify code"),
        Step("Run tests", tool="test", reasoning="Verify changes"),
        Step("Verify no regressions", tool="verify", reasoning="Check side effects"),
    ],
    "remove functionality": [
        Step("Find all usages", tool="search", reasoning="Map what depends on it"),
        Step("Read affected code", tool="read", reasoning="Understand impact"),
        Step("Remove code", tool="edit", reasoning="Delete safely"),
        Step("Update dependents", tool="edit", reasoning="Remove references"),
        Step("Run tests", tool="test", reasoning="Verify nothing broken"),
    ],
}


class TaskPlanner:
    """Generate a structured Plan from a task description and repo context."""

    def __init__(self, repo_map: RepoMap | None = None, ranked_files: list[RankedFile] | None = None):
        self.repo_map = repo_map
        self.ranked_files = ranked_files or []

    def plan(self, task: str) -> Plan:
        from pgimcode.tools.ranker import extract_keywords

        keywords = extract_keywords(task)
        verb = self._detect_verb(keywords)

        interpretation = self._interpret_task(task, verb, keywords)
        objective = self._derive_objective(task, verb, keywords)
        constraints = self._extract_constraints(task)
        acceptance = self._derive_acceptance(verb, objective)
        assumptions = self._derive_assumptions()
        steps = self._build_steps(verb)
        files = [str(rf.file.path) for rf in self.ranked_files[:8]]
        next_action = steps[0].description if steps else "No action needed"
        confidence = self._compute_confidence(keywords, files)

        return Plan(
            task=task,
            interpretation=interpretation,
            objective=objective,
            constraints=constraints,
            acceptance_criteria=acceptance,
            assumptions=assumptions,
            steps=steps,
            files_to_inspect=files,
            next_action=next_action,
            confidence=confidence,
        )

    def _detect_verb(self, keywords: list[str]) -> str:
        for kw in keywords:
            if kw in VERB_MAP:
                return VERB_MAP[kw]
        return "update existing behavior"

    def _interpret_task(self, task: str, verb: str, keywords: list[str]) -> str:
        if verb == "add new functionality":
            return f"User wants to add new functionality related to: {', '.join(keywords[:3])}"
        elif verb == "fix a bug":
            return f"User wants to fix a bug in: {', '.join(keywords[:3])}"
        elif verb == "restructure code":
            return f"User wants to restructure code involving: {', '.join(keywords[:3])}"
        elif verb == "add or fix tests":
            return f"User wants to add or fix tests for: {', '.join(keywords[:3])}"
        elif verb == "remove functionality":
            return f"User wants to remove functionality related to: {', '.join(keywords[:3])}"
        else:
            return f"User wants to update existing behavior for: {', '.join(keywords[:3])}"

    def _derive_objective(self, task: str, verb: str, keywords: list[str]) -> str:
        kw_str = ', '.join(keywords[:5])
        return f"{verb.replace('-', ' ').title()} involving {kw_str}"

    def _extract_constraints(self, task: str) -> list[str]:
        constraints = []
        task_lower = task.lower()
        if "without breaking" in task_lower or "no regression" in task_lower:
            constraints.append("Must not break existing tests")
        if "minimal" in task_lower or "small" in task_lower:
            constraints.append("Should make minimal changes")
        if "quick" in task_lower or "fast" in task_lower:
            constraints.append("Should be quick to implement")
        if "using" in task_lower:
            # crude extraction
            idx = task_lower.index("using")
            rest = task[idx + 5:].strip().split()[0]
            if rest:
                constraints.append(f"Must use {rest}")
        if self.repo_map and self.repo_map.test_locations:
            constraints.append("Must ensure tests pass")
        return constraints

    def _derive_acceptance(self, verb: str, objective: str) -> list[str]:
        if verb == "add new functionality":
            return [
                "Feature is implemented correctly",
                "All tests pass",
                "No regressions introduced",
            ]
        elif verb == "fix a bug":
            return [
                "Bug is resolved",
                "Reproduction test passes",
                "No new regressions",
            ]
        elif verb == "restructure code":
            return [
                "Code is restructured as planned",
                "All tests pass",
                "No behavioral changes",
            ]
        elif verb == "add or fix tests":
            return [
                "Tests are added or fixed",
                "Coverage improved or maintained",
                "All tests pass",
            ]
        elif verb == "remove functionality":
            return [
                "Feature is removed cleanly",
                "No dangling references",
                "All tests pass",
            ]
        else:
            return [
                "Changes implemented correctly",
                "All tests pass",
                "No regressions",
            ]

    def _derive_assumptions(self) -> list[str]:
        assumptions = []
        if self.repo_map:
            if "python" in self.repo_map.languages:
                assumptions.append("Repository uses Python")
            if self.repo_map.frameworks:
                assumptions.append(f"Frameworks: {', '.join(self.repo_map.frameworks[:3])}")
            if self.repo_map.test_locations:
                assumptions.append(f"Tests found in: {', '.join(self.repo_map.test_locations[:3])}")
            else:
                assumptions.append("No test directories detected")
        return assumptions

    def _build_steps(self, verb: str) -> list[Step]:
        template = STEP_TEMPLATES.get(verb, STEP_TEMPLATES["update existing behavior"])
        # Return fresh copies so status mutations don't affect template
        return [Step(description=s.description, status=s.status, tool=s.tool, reasoning=s.reasoning) for s in template]

    def _compute_confidence(self, keywords: list[str], files: list[str]) -> float:
        if not keywords or not files:
            return 0.3

        # Match keywords against file paths
        matched = sum(1 for kw in keywords if any(kw in f.lower() for f in files))
        keyword_score = (matched / len(keywords)) * 0.4

        entry_point_bonus = 0.2 if self.repo_map and self.repo_map.entry_points else 0.0
        test_bonus = 0.2 if self.repo_map and self.repo_map.test_locations else 0.0
        file_bonus = 0.2 if self.ranked_files else 0.0

        score = keyword_score + entry_point_bonus + test_bonus + file_bonus
        return min(1.0, round(score, 2))