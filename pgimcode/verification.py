"""Post-edit verification pipeline."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from pgimcode.tools.shell import ShellRunner
from pgimcode.tools.test_runner import run_tests, TestResult
from pgimcode.tools.edit import EditResult


@dataclass
class CheckResult:
    name: str
    status: str  # pass | fail | warn | skip
    message: str
    details: str = ""


@dataclass
class VerificationReport:
    verdict: str  # pass | warn | fail
    checks: list[CheckResult]
    changed_files: list[Path] = field(default_factory=list)
    diff_summary: str = ""
    test_result: TestResult | None = None

    def to_markdown(self) -> str:
        lines = ["# Verification Report", ""]
        verdict_icon = {"pass": "✅", "warn": "⚠️", "fail": "❌"}.get(self.verdict, "❓")
        lines.append(f"**Verdict: {verdict_icon} {self.verdict.upper()}**")
        lines.append("")

        lines.append("## Checks")
        lines.append("")
        for check in self.checks:
            icon = {"pass": "✅", "fail": "❌", "warn": "⚠️", "skip": "⏭️"}.get(check.status, "❓")
            lines.append(f"{icon} **{check.name}** — {check.status}")
            lines.append(f"  {check.message}")
            if check.details:
                lines.append(f"  ```")
                for d in check.details.splitlines()[:10]:
                    lines.append(f"  {d}")
                if len(check.details.splitlines()) > 10:
                    lines.append("  ...")
                lines.append(f"  ```")
            lines.append("")

        if self.test_result:
            lines.append("## Test Results")
            lines.append(f"  Framework: {self.test_result.framework}")
            lines.append(f"  {self.test_result.pass_count} passed, {self.test_result.fail_count} failed, {self.test_result.skip_count} skipped")
            lines.append(f"  Duration: {self.test_result.duration_ms:.0f}ms")
            lines.append("")

        if self.diff_summary:
            lines.append("## Diff Summary")
            lines.append(f"```diff\n{self.diff_summary}\n```")
            lines.append("")

        return "\n".join(lines)


class Verifier:
    """Runs post-edit verification checks."""

    def __init__(self, workspace_root: Path, runner: ShellRunner | None = None):
        self.workspace = workspace_root.resolve()
        self.runner = runner or ShellRunner(workspace_root=self.workspace)

    def check_file_exists(self, paths: list[Path]) -> CheckResult:
        missing = [p for p in paths if not p.exists()]
        if missing:
            return CheckResult(
                name="File existence",
                status="fail",
                message=f"{len(missing)} file(s) missing: {', '.join(str(p) for p in missing)}",
            )
        return CheckResult(
            name="File existence",
            status="pass",
            message=f"{len(paths)} file(s) exist",
        )

    def check_syntax(self, paths: list[Path]) -> CheckResult:
        """Check syntax for supported languages (Python only for V1)."""
        failures = []
        for p in paths:
            if p.suffix == ".py" and p.exists():
                result = self.runner.run(
                    ["python", "-m", "py_compile", str(p)],
                    cwd=self.workspace,
                    timeout=10,
                )
                if result.exit_code != 0:
                    failures.append(f"{p}: {result.stderr[:200]}")

        if failures:
            return CheckResult(
                name="Syntax check",
                status="fail",
                message=f"{len(failures)} file(s) have syntax errors",
                details="\n".join(failures),
            )
        elif not paths:
            return CheckResult(name="Syntax check", status="skip", message="No supported files to check")
        else:
            return CheckResult(name="Syntax check", status="pass", message="All Python files compile")

    def check_lint(self, paths: list[Path]) -> CheckResult:
        """Run ruff check on the workspace (if available)."""
        # Try to run ruff check directly - if not in allowlist, it will fail
        try:
            result = self.runner.run(["ruff", "check", "."], timeout=30)
            if result.exit_code != 0:
                return CheckResult(
                    name="Lint check",
                    status="warn",
                    message="Lint issues found",
                    details=result.stdout[:500] + result.stderr[:500],
                )
            return CheckResult(name="Lint check", status="pass", message="No lint issues")
        except ValueError:
            return CheckResult(name="Lint check", status="skip", message="ruff not available")

    def verify_tests(self) -> TestResult | None:
        """Run test suite. Returns None if no framework detected."""
        result = run_tests(self.workspace, timeout=120)
        if result.framework == "unknown":
            return None
        return result

    def verify_build(self) -> CheckResult:
        """Attempt a build check."""
        # Check if poetry is available by trying to run it
        try:
            result = self.runner.run(["poetry", "check"], cwd=self.workspace, timeout=30)
            if result.exit_code != 0:
                return CheckResult(
                    name="Build check",
                    status="warn",
                    message="poetry check found issues",
                    details=result.stdout + result.stderr,
                )
            return CheckResult(name="Build check", status="pass", message="poetry check passed")
        except ValueError:
            return CheckResult(name="Build check", status="skip", message="poetry not available")

    def verify(self, changed_paths: list[Path]) -> VerificationReport:
        checks = []
        test_result = None

        # Structural
        checks.append(self.check_file_exists(changed_paths))

        # Syntax
        checks.append(self.check_syntax(changed_paths))

        # Lint
        checks.append(self.check_lint(changed_paths))

        # Build
        checks.append(self.verify_build())

        # Tests
        test_result = self.verify_tests()
        if test_result:
            test_status = "pass" if test_result.success else "fail"
            if test_result.timed_out:
                test_status = "warn"
            checks.append(CheckResult(
                name="Tests",
                status=test_status,
                message=f"{test_result.pass_count} passed, {test_result.fail_count} failed, {test_result.skip_count} skipped",
            ))
        else:
            checks.append(CheckResult(name="Tests", status="skip", message="No test framework detected"))

        # Verdict
        if any(c.status == "fail" for c in checks):
            verdict = "fail"
        elif any(c.status == "warn" for c in checks):
            verdict = "warn"
        elif all(c.status in ("pass", "skip") for c in checks):
            verdict = "pass"
        else:
            verdict = "fail"

        return VerificationReport(
            verdict=verdict,
            checks=checks,
            changed_files=changed_paths,
            test_result=test_result,
        )