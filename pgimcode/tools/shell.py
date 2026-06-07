"""Safe shell command execution."""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class CommandResult:
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float
    timed_out: bool
    command: list[str]


# Default allowlist — restrict what commands can run for safety
DEFAULT_ALLOWLIST: set[str] = {
    "pytest", "python", "python3",
    "poetry", "pip",
    "npm", "npx", "yarn", "pnpm",
    "cargo", "rustc", "go",
    "make",
    "ruff", "mypy", "black", "isort", "flake8",
    "git", "echo", "cat", "ls", "pwd", "wc",
    "mkdir", "cp", "mv", "rm", "touch",
    # Windows
    "cmd", "dir", "findstr", "where", "tree",
    "powershell", "pwsh",
}


class ShellRunner:
    """Run shell commands safely within a workspace."""

    def __init__(self, workspace_root: Path, allowlist: set[str] | None = None, default_timeout: int = 60):
        self.workspace_root = workspace_root.resolve()
        self.allowlist = allowlist or DEFAULT_ALLOWLIST
        self.default_timeout = default_timeout

    def _check_command(self, command: list[str]) -> None:
        if not command:
            raise ValueError("Empty command")
        cmd_name = command[0]
        # Handle paths like ./venv/bin/pytest or absolute paths
        base = Path(cmd_name).name
        if base not in self.allowlist:
            raise ValueError(f"Command '{base}' not in allowlist")

    def _check_cwd(self, cwd: Path) -> Path:
        resolved = cwd.resolve()
        # cwd must be within workspace_root
        try:
            resolved.relative_to(self.workspace_root)
        except ValueError:
            raise ValueError(f"cwd '{resolved}' is outside workspace '{self.workspace_root}'")
        return resolved

    def run(
        self,
        command: list[str],
        cwd: Path | None = None,
        timeout: int | None = None,
        env: dict[str, str] | None = None,
        shell: bool = False,
    ) -> CommandResult:
        timeout = timeout or self.default_timeout
        cwd = cwd or self.workspace_root
        self._check_command(command)
        checked_cwd = self._check_cwd(cwd)

        start = time.perf_counter()
        try:
            proc = subprocess.run(
                command,
                cwd=checked_cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env={**subprocess.os.environ, **(env or {})},
                shell=shell,
            )
            duration_ms = (time.perf_counter() - start) * 1000
            return CommandResult(
                exit_code=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                duration_ms=duration_ms,
                timed_out=False,
                command=command,
            )
        except subprocess.TimeoutExpired as exc:
            duration_ms = (time.perf_counter() - start) * 1000
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")
            return CommandResult(
                exit_code=-1,
                stdout=stdout,
                stderr=stderr,
                duration_ms=duration_ms,
                timed_out=True,
                command=command,
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000
            return CommandResult(
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration_ms=duration_ms,
                timed_out=False,
                command=command,
            )