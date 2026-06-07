"""Reusable policy blocks for agent prompting."""

from __future__ import annotations


INVESTIGATION_POLICY = """
Before editing, form hypotheses, gather evidence from multiple tools, and make the
smallest safe change only after the target and blast radius are concrete.
""".strip()


EXECUTION_POLICY = """
- Read or search before editing.
- Prefer multiple weak signals over one shallow guess.
- Track task progress explicitly for non-trivial work.
- State uncertainty and open questions instead of pretending confidence.
""".strip()


COMPLETION_POLICY = """
Do not say the task is done until verification and self-review are complete, and
the final summary names the affected files, checks performed, and residual risk.
""".strip()


def build_policy_block() -> str:
    """Return the shared policy text injected into system prompts."""
    return "\n\n".join(
        [
            "## Investigation Policy\n" + INVESTIGATION_POLICY,
            "## Execution Policy\n" + EXECUTION_POLICY,
            "## Completion Policy\n" + COMPLETION_POLICY,
        ]
    )
