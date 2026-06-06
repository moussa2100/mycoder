"""Tests for verification pipeline."""

from pathlib import Path

from pgimcode.verification import Verifier, VerificationReport, CheckResult


def test_verifier_exists():
    v = Verifier(Path("."))
    assert v is not None


def test_check_file_exists(tmp_path):
    v = Verifier(tmp_path)
    f = tmp_path / "test.py"
    f.write_text("x = 1\n")
    cr = v.check_file_exists([f])
    assert cr.status == "pass"

    missing = tmp_path / "missing.py"
    cr = v.check_file_exists([missing])
    assert cr.status == "fail"


def test_check_syntax_python(tmp_path):
    v = Verifier(tmp_path)
    bad = tmp_path / "bad.py"
    bad.write_text("def foo(\n")
    cr = v.check_syntax([bad])
    assert cr.status == "fail"

    good = tmp_path / "good.py"
    good.write_text("def foo():\n    pass\n")
    cr = v.check_syntax([good])
    assert cr.status == "pass"


def test_verification_report_markdown():
    report = VerificationReport(
        verdict="pass",
        checks=[
            CheckResult(name="File existence", status="pass", message="2 files exist"),
            CheckResult(name="Tests", status="pass", message="5 passed"),
        ],
    )
    md = report.to_markdown()
    assert "Verification Report" in md
    assert "PASS" in md
    assert "File existence" in md