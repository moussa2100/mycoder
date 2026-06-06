"""Tests for retry and recovery logic."""

import pytest

from pgimcode.retry import (
    RetryPolicy, RecoveryStrategy, determine_recovery,
    retry_with_policy, FallbackInspector,
)


def make_result(success, message=""):
    """Helper to create fake result objects."""
    return type("Res", (), {"success": success, "message": message})()


def test_retry_succeeds_first_try():
    calls = []
    def good():
        calls.append(1)
        return make_result(True)
    policy = RetryPolicy(max_retries=2)
    result = retry_with_policy(good, policy)
    assert result.success is True
    assert len(calls) == 1


def test_retry_exhausts():
    calls = []
    def bad():
        calls.append(1)
        return make_result(False, "always fails")
    policy = RetryPolicy(max_retries=1, backoff_factor=0.01)
    result = retry_with_policy(bad, policy)
    assert result.success is False
    assert len(calls) == 2  # initial + 1 retry


def test_retry_succeeds_on_second():
    calls = []
    def flaky():
        calls.append(1)
        if len(calls) < 2:
            return make_result(False, "flaky")
        return make_result(True)
    policy = RetryPolicy(max_retries=2, backoff_factor=0.01)
    result = retry_with_policy(flaky, policy)
    assert result.success is True
    assert len(calls) == 2


def test_determine_recovery_not_found():
    s = determine_recovery("replace_block", "old_text not found")
    assert s == RecoveryStrategy.FALLBACK


def test_determine_recovery_timeout():
    s = determine_recovery("run", "timed out")
    assert s == RecoveryStrategy.RETRY


def test_determine_recovery_allowlist():
    s = determine_recovery("run", "Command not in allowlist")
    assert s == RecoveryStrategy.ABORT


def test_determine_recovery_default_retry():
    s = determine_recovery("do_something", "unknown error")
    assert s == RecoveryStrategy.RETRY


def test_retry_policy_delay():
    p = RetryPolicy(backoff_factor=1.0, exponential=True, max_delay=10)
    assert p.compute_delay(0) == 1.0
    assert p.compute_delay(1) == 2.0
    assert p.compute_delay(10) <= 10.0  # clamped by max_delay