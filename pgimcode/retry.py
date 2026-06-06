"""Retry policy, recovery strategies, and fallback inspection."""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable


class RecoveryStrategy(Enum):
    RETRY = "retry"
    FALLBACK = "fallback"
    ASK_HUMAN = "ask_human"
    ABORT = "abort"


@dataclass
class RetryPolicy:
    max_retries: int = 3
    backoff_factor: float = 1.0
    max_delay: float = 30.0
    exponential: bool = True
    jitter: float = 0.0  # random jitter fraction, e.g. 0.1 = ±10%
    log_fn: Callable[[str], None] | None = None

    def _log(self, msg: str) -> None:
        if self.log_fn:
            self.log_fn(msg)

    def compute_delay(self, attempt: int) -> float:
        if self.exponential:
            delay = self.backoff_factor * (2 ** attempt)
        else:
            delay = self.backoff_factor * (attempt + 1)
        delay = min(delay, self.max_delay)
        if self.jitter > 0:
            import random
            delay = delay * (1 + random.uniform(-self.jitter, self.jitter))
        return max(0.0, delay)


def determine_recovery(operation: str, failure_message: str) -> RecoveryStrategy:
    """Map a failure to a recovery strategy. Caller's retry loop decides exhaustion."""
    msg = failure_message.lower()

    # Specific failure patterns
    if "not found" in msg and "text" in msg:
        return RecoveryStrategy.FALLBACK  # replace_block: search for text
    if "multiple" in msg and "times" in msg:
        return RecoveryStrategy.FALLBACK  # replace_block: ambiguous match
    if "diff context mismatch" in msg:
        return RecoveryStrategy.FALLBACK  # patch_file: re-read
    if "tim" in msg and "out" in msg:
        return RecoveryStrategy.RETRY     # timeout
    if "allowlist" in msg:
        return RecoveryStrategy.ABORT     # shell: command not allowed
    if "already exists" in msg:
        return RecoveryStrategy.FALLBACK  # create_file: overwrite
    if "no test framework" in msg:
        return RecoveryStrategy.FALLBACK  # test_runner: inspect repo
    if "syntax" in msg:
        return RecoveryStrategy.RETRY     # syntax error: might be transient
    if "exit_code" in msg:
        return RecoveryStrategy.RETRY     # generic command failure

    return RecoveryStrategy.RETRY


def retry_with_policy(
    fn: Callable[..., Any],
    policy: RetryPolicy,
    *args,
    **kwargs,
) -> Any:
    """Run fn with retries. fn must return an object with a `.success` boolean attribute."""
    last_result = None
    for attempt in range(policy.max_retries + 1):
        try:
            result = fn(*args, **kwargs)
        except Exception as exc:
            result = type("FakeResult", (), {"success": False, "message": str(exc)})()

        if getattr(result, "success", True):
            policy._log(f"✅ {fn.__name__} succeeded")
            return result

        last_result = result
        failure = getattr(result, "message", str(result))
        strategy = determine_recovery(fn.__name__, failure)

        policy._log(f"⚠️ {fn.__name__} attempt {attempt + 1}/{policy.max_retries + 1} failed: {failure}")
        policy._log(f"   → strategy: {strategy.value}")

        if strategy == RecoveryStrategy.ABORT:
            policy._log(f"❌ {fn.__name__} aborted")
            return result
        elif strategy == RecoveryStrategy.ASK_HUMAN:
            policy._log(f"🛑 {fn.__name__} escalated to human")
            return result
        elif strategy == RecoveryStrategy.FALLBACK:
            policy._log(f"🔧 {fn.__name__} falling back")
            # Don't sleep; let the caller handle fallback
            return result

        # RETRY
        if attempt < policy.max_retries:
            delay = policy.compute_delay(attempt)
            policy._log(f"   → retrying in {delay:.1f}s...")
            time.sleep(delay)
        else:
            # Exhausted retries
            policy._log(f"🛑 {fn.__name__} exhausted retries — escalating to human")
            return last_result

    policy._log(f"❌ {fn.__name__} exhausted retries")
    return last_result


class FallbackInspector:
    """Provides fallback actions when primary operations fail."""

    def __init__(self, workspace_root: Path):
        self.workspace = workspace_root

    def fallback_replace(self, old_text: str) -> str:
        """Search for where old_text actually appears."""
        from pgimcode.tools.grep import rg_search
        query = old_text[:40].strip()
        results = rg_search(query, self.workspace, max_results=5, context_lines=1)
        if results:
            return "Found similar text:\n" + "\n".join(r.text for r in results)
        return "No similar text found in repo"

    def fallback_patch(self, path: Path) -> str:
        """Re-read the file to show current state."""
        from pgimcode.tools.read import read_file_chunk
        result = read_file_chunk(path, 1, 20)
        return f"Current state of {path}:\n{result.content[:400]}"

    def fallback_test(self, root: Path) -> str:
        """Inspect repo for test framework."""
        from pgimcode.tools.test_runner import detect_framework
        fw = detect_framework(root)
        if fw:
            return f"Detected framework: {fw}"
        return "No test framework found"