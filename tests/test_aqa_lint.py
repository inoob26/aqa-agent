"""The linter the agent relies on: every rule must fire, and every escape hatch must hold."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

import aqa_lint

COVERAGE = """\
---
slug: checkout-discounts
status: {status}   # draft | approved
approved_by:
---

| ID | Requirement | Scenario | Category | Priority | Layer | Oracle | Automation |
|----|-------------|----------|----------|----------|-------|--------|------------|
| SC-001 | REQ-1 | Valid code reduces the total | Happy path | P0 | API | total | auto |
| SC-002 | REQ-1 | Expired code is rejected | Negative | P0 | API | 422 | auto |
| SC-003 | REQ-2 | Screen reader announces it | Accessibility | P2 | E2E | live region | manual |
"""


def rules(findings: list[aqa_lint.Finding]) -> list[str]:
    return [f.rule for f in findings]


@pytest.mark.parametrize(
    ("line", "rule"),
    [
        ("    time.sleep(2)", "fixed-wait"),
        ("    await asyncio.sleep(0.5)", "fixed-wait"),
        ("    sleep(1)", "fixed-wait"),
        ("    page.wait_for_timeout(500)", "fixed-wait"),
        ("@pytest.mark.flaky(reruns=3)", "retry"),
        ('addopts = "--reruns 2"', "retry"),
        ("    assert True", "empty-assertion"),
        ('    assert True, "reached"', "empty-assertion"),
        ('TOKEN = "ghp_' + "a" * 36 + '"', "secret"),
        ('headers = {"Authorization": "Bearer abcdefghijklmnopqrstuvwx"}', "secret"),
        ('api_key = "9f8e7d6c5b4a39281706f5e4d3c2b1a0"', "secret"),
    ],
)
def test_python_rule_fires(line: str, rule: str) -> None:
    assert rule in rules(aqa_lint.lint_text("tests/test_x.py", line + "\n", "py"))


@pytest.mark.parametrize(
    ("line", "rule"),
    [
        ("  await page.waitForTimeout(1000);", "fixed-wait"),
        ("  await new Promise((r) => setTimeout(r, 500));", "fixed-wait"),
        ("  retries: 2,", "retry"),
        ("  retries: process.env.CI ? 2 : 0,", "retry"),
        ("test.describe.configure({ retries: 3 });", "retry"),
        ("test.only('x', async () => {});", "focused-test"),
        ("test.describe.only('suite', () => {});", "focused-test"),
        ("  expect(true).toBe(true);", "empty-assertion"),
        ("  expect(response).toBeTruthy();", "empty-assertion"),
        ("const jwt = 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdefghijklmnop';",
         "secret"),
    ],
)
def test_typescript_rule_fires(line: str, rule: str) -> None:
    assert rule in rules(aqa_lint.lint_text("e2e/x.spec.ts", line + "\n", "js"))


@pytest.mark.parametrize(
    ("line", "kind"),
    [
        ("        time.sleep(POLL_INTERVAL_S)  # aqa: allow-sleep poll interval", "py"),
        ("    # time.sleep(2) was here", "py"),
        ("    expect(page.get_by_role('alert')).to_be_visible()", "py"),
        ('    api_key = os.environ["API_KEY"]', "py"),
        ('    token = "expired-token-0000000000"', "py"),
        ('    headers = {"Authorization": f"Bearer {token}"}', "py"),
        ("    assert response.status_code == 422", "py"),
        ("  retries: 0,", "js"),
        ("  { name: 'quarantine', retries: 3 }, // aqa: allow-retries QA-142", "js"),
        ("  await expect(page.getByRole('alert')).toBeVisible();", "js"),
        ("  expect(order.total).toBeTruthy();", "js"),
    ],
)
def test_clean_line_passes(line: str, kind: str) -> None:
    assert aqa_lint.lint_text("f", line + "\n", kind) == []


def test_allow_marker_needs_a_reason() -> None:
    line = "    time.sleep(1)  # aqa: allow-sleep\n"
    assert rules(aqa_lint.lint_text("f", line, "py")) == ["fixed-wait"]


@pytest.mark.parametrize(
    ("path", "kind"),
    [
        ("tests/api/test_orders.py", "py"),
        ("tests/conftest.py", "py"),
        ("tests/helpers/polling.py", "py"),
        ("src/orders/service.py", None),
        ("e2e/checkout.spec.ts", "js"),
        ("src/cart.test.tsx", "js"),
        ("playwright.config.ts", "js"),
        ("src/cart.ts", None),
        ("pytest.ini", "config"),
        ("pyproject.toml", "config"),
        ("README.md", None),
    ],
)
def test_file_classification(path: str, kind: str | None) -> None:
    assert aqa_lint.kind_of(Path(path)) == kind


def test_lint_walks_directories_and_skips_product_code(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "worker.py").write_text("import time\ntime.sleep(5)\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_a.py").write_text(
        "import time\n\ndef test_a():\n    time.sleep(1)\n"
    )
    (tmp_path / "node_modules" / "tests").mkdir(parents=True)
    (tmp_path / "node_modules" / "tests" / "x.spec.ts").write_text("page.waitForTimeout(1)\n")

    findings = aqa_lint.lint_paths([tmp_path])

    found = [(Path(f.path).name, f.line, f.rule) for f in findings]
    assert found == [("test_a.py", 4, "fixed-wait")]


def test_parse_coverage() -> None:
    coverage = aqa_lint.parse_coverage(COVERAGE.format(status="approved"))
    assert coverage.status == "approved"
    assert coverage.scenarios == {"SC-001": "auto", "SC-002": "auto", "SC-003": "manual"}


@pytest.mark.parametrize(("status", "expected"), [("approved", []), ("draft", ["not-approved"])])
def test_gate(tmp_path: Path, status: str, expected: list[str]) -> None:
    (tmp_path / "coverage.md").write_text(COVERAGE.format(status=status))
    assert rules(aqa_lint.gate(tmp_path)) == expected


def test_gate_without_matrix(tmp_path: Path) -> None:
    assert rules(aqa_lint.gate(tmp_path)) == ["no-coverage"]


PY_TESTS = '''\
import pytest


def test_valid_code_reduces_total(api):
    """Scenario: SC-001 — Valid code reduces the total. Requirement: REQ-1."""
    assert api.post("/discount").status_code == 200


# Scenario: SC-002, SC-009 — rejected codes. Requirement: REQ-1.
@pytest.mark.parametrize("code", ["EXPIRED", "UNKNOWN"])
def test_code_is_rejected(api, code):
    assert api.post("/discount", json={"code": code}).status_code == 422


def test_untraced(api):
    assert api.get("/health").status_code == 200
'''

TS_TESTS = """\
import { test, expect } from '@playwright/test';

test.describe('discounts', () => {
  // Scenario: SC-001 — Valid code reduces the total. Requirement: REQ-1.
  test('valid code reduces the total', async ({ page }) => {
    await expect(page.getByTestId('total')).toHaveText('$90.00');
  });

  test('SC-002 expired code is rejected', async ({ page }) => {
    await expect(page.getByRole('alert')).toBeVisible();
  });
});
"""


def test_trace_python(tmp_path: Path) -> None:
    (tmp_path / "coverage.md").write_text(COVERAGE.format(status="approved"))
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_discount.py").write_text(PY_TESTS)

    found = {(f.rule, f.message.split(":")[0]) for f in aqa_lint.trace(tmp_path, [tests])}

    assert found == {
        ("unknown-scenario", "test_code_is_rejected"),  # SC-009 is not in the matrix
        ("untraced-test", "test_untraced"),
    }


def test_trace_typescript_and_uncovered_rows(tmp_path: Path) -> None:
    (tmp_path / "coverage.md").write_text(COVERAGE.format(status="approved"))
    e2e = tmp_path / "e2e"
    e2e.mkdir()
    (e2e / "discount.spec.ts").write_text(TS_TESTS)
    assert aqa_lint.trace(tmp_path, [e2e]) == []

    (e2e / "discount.spec.ts").write_text(TS_TESTS.replace("SC-002 ", ""))
    assert sorted(rules(aqa_lint.trace(tmp_path, [e2e]))) == ["uncovered-scenario", "untraced-test"]


def run_hook(monkeypatch: pytest.MonkeyPatch, payload: object) -> int:
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    return aqa_lint.main(["hook"])


def test_hook_reports_a_violation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "test_a.py"
    target.write_text("import time\n\ndef test_a():\n    time.sleep(1)\n")

    code = run_hook(monkeypatch, {"tool_name": "Write", "tool_input": {"file_path": str(target)}})

    assert code == 2
    assert "fixed-wait" in capsys.readouterr().err


def test_hook_ignores_product_code_and_bad_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    product = tmp_path / "worker.py"
    product.write_text("import time\ntime.sleep(5)\n")
    assert run_hook(monkeypatch, {"tool_input": {"file_path": str(product)}}) == 0
    assert run_hook(monkeypatch, {"tool_input": {}}) == 0
    assert run_hook(monkeypatch, ["not", "an", "event"]) == 0


def test_cli_exit_codes(tmp_path: Path) -> None:
    clean = tmp_path / "test_ok.py"
    clean.write_text("def test_ok():\n    assert 1 + 1 == 2\n")
    assert aqa_lint.main(["lint", str(clean)]) == 0
    assert aqa_lint.main(["lint", str(tmp_path / "missing")]) == 2
    assert aqa_lint.main(["gate", str(tmp_path)]) == 1
