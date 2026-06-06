"""Test framework detection and execution."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from pgimcode.tools.shell import ShellRunner, CommandResult


@dataclass
class TestResult:
    success: bool
    framework: str
    pass_count: int
    fail_count: int
    skip_count: int
    total: int
    stdout: str
    stderr: str
    duration_ms: float
    timed_out: bool


def detect_framework(root: Path) -> str | None:
    """Detect test framework from repo files."""
    files = {p.name for p in root.iterdir() if p.is_file()}
    if "pyproject.toml" in files or "setup.py" in files or "requirements.txt" in files:
        return "pytest"
    if "package.json" in files:
        return "npm"
    if "Cargo.toml" in files:
        return "cargo"
    if "go.mod" in files:
        return "go"
    # Check for test directories
    for p in root.iterdir():
        if p.is_dir() and p.name.lower() in ("tests", "test", "__tests__", "spec"):
            # Default to pytest for Python test dirs with .py files
            if any(f.suffix == ".py" for f in p.rglob("*.py")):
                return "pytest"
    return None


def run_tests(root: Path, framework: str | None = None, timeout: int = 60) -> TestResult:
    framework = framework or detect_framework(root)
    if framework is None:
        return TestResult(
            success=False, framework="unknown", pass_count=0, fail_count=0,
            skip_count=0, total=0, stdout="", stderr="No test framework detected",
            duration_ms=0, timed_out=False,
        )

    runner = ShellRunner(workspace_root=root, default_timeout=timeout)

    if framework == "pytest":
        result = runner.run(["pytest", "-v", "--tb=short"], cwd=root, timeout=timeout)
        return _parse_pytest_result(result)
    elif framework == "npm":
        result = runner.run(["npm", "test"], cwd=root, timeout=timeout)
        return _parse_npm_result(result)
    elif framework == "cargo":
        result = runner.run(["cargo", "test"], cwd=root, timeout=timeout)
        return _parse_cargo_result(result)
    elif framework == "go":
        result = runner.run(["go", "test", "./..."], cwd=root, timeout=timeout)
        return _parse_go_result(result)
    else:
        return TestResult(
            success=False, framework=framework, pass_count=0, fail_count=0,
            skip_count=0, total=0, stdout="", stderr=f"Unknown framework: {framework}",
            duration_ms=0, timed_out=False,
        )


def _parse_pytest_result(result: CommandResult) -> TestResult:
    stdout = result.stdout
    if isinstance(stdout, bytes):
        stdout = stdout.decode("utf-8", errors="replace")
    # Match patterns like "3 passed, 1 failed, 2 skipped"
    pattern = re.compile(
        r"(\d+)\s+passed.*?"  # pass count
        r"(?:,\s*(\d+)\s+failed)?"  # fail count
        r"(?:,\s*(\d+)\s+skipped)?"  # skip count
        r"(?:,\s*(\d+)\s+error)?",  # error count
        re.IGNORECASE,
    )
    match = pattern.search(stdout)
    pass_count = int(match.group(1)) if match and match.group(1) else 0
    fail_count = int(match.group(2)) if match and match.group(2) else 0
    skip_count = int(match.group(3)) if match and match.group(3) else 0
    error_count = int(match.group(4)) if match and match.group(4) else 0
    total = pass_count + fail_count + skip_count + error_count

    # Also look for summary line
    if not match:
        summary = re.search(r"(\d+) passed in", stdout)
        if summary:
            pass_count = int(summary.group(1))
            total = pass_count

    success = result.exit_code == 0 and fail_count == 0 and error_count == 0 and not result.timed_out
    return TestResult(
        success=success,
        framework="pytest",
        pass_count=pass_count,
        fail_count=fail_count,
        skip_count=skip_count,
        total=total,
        stdout=result.stdout,
        stderr=result.stderr,
        duration_ms=result.duration_ms,
        timed_out=result.timed_out,
    )


def _parse_npm_result(result: CommandResult) -> TestResult:
    stdout = result.stdout
    if isinstance(stdout, bytes):
        stdout = stdout.decode("utf-8", errors="replace")
    # Simple: count pass/fail from output
    passes = len(re.findall(r"✓|PASS|passing", stdout))
    fails = len(re.findall(r"✗|FAIL|failing", stdout))
    total = passes + fails
    success = result.exit_code == 0 and fails == 0 and not result.timed_out
    return TestResult(
        success=success, framework="npm", pass_count=passes, fail_count=fails,
        skip_count=0, total=total, stdout=stdout, stderr=result.stderr,
        duration_ms=result.duration_ms, timed_out=result.timed_out,
    )


def _parse_cargo_result(result: CommandResult) -> TestResult:
    stdout = result.stdout
    if isinstance(stdout, bytes):
        stdout = stdout.decode("utf-8", errors="replace")
    match = re.search(r"test result:\s*(ok|FAILED)\.\s*(\d+) passed(?:;\s*(\d+) failed)?", stdout)
    pass_count = int(match.group(2)) if match else 0
    fail_count = int(match.group(3)) if match and match.group(3) else 0
    total = pass_count + fail_count
    success = result.exit_code == 0 and fail_count == 0 and not result.timed_out
    return TestResult(
        success=success, framework="cargo", pass_count=pass_count, fail_count=fail_count,
        skip_count=0, total=total, stdout=stdout, stderr=result.stderr,
        duration_ms=result.duration_ms, timed_out=result.timed_out,
    )


def _parse_go_result(result: CommandResult) -> TestResult:
    stdout = result.stdout
    if isinstance(stdout, bytes):
        stdout = stdout.decode("utf-8", errors="replace")
    # go test output: "ok ... 0.123s" or "FAIL ... 0.123s"
    lines = stdout.splitlines()
    packages = [l for l in lines if l.startswith("ok") or l.startswith("FAIL")]
    success = result.exit_code == 0 and all(l.startswith("ok") for l in packages) and not result.timed_out
    return TestResult(
        success=success, framework="go", pass_count=len([l for l in packages if l.startswith("ok")]),
        fail_count=len([l for l in packages if l.startswith("FAIL")]),
        skip_count=0, total=len(packages), stdout=stdout, stderr=result.stderr,
        duration_ms=result.duration_ms, timed_out=result.timed_out,
    )