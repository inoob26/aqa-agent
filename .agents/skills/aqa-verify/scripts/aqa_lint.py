#!/usr/bin/env python3
"""Mechanical checks for tests written by the aqa agent.

    aqa_lint.py lint  <path>...             forbidden patterns in test files
    aqa_lint.py trace <artifacts> <path>... tests <-> coverage.md, both directions
    aqa_lint.py gate  <artifacts>           is the coverage matrix approved?
    aqa_lint.py hook                        PostToolUse hook: lint the file just written

Exit codes: 0 clean, 1 findings, 2 usage error (hook: 2 = findings, reported on stderr).
Standard library only, Python 3.9+, so it runs in any target project.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

SKIP_DIRS = {
    ".git", ".hg", ".venv", "venv", "node_modules", "__pycache__", ".tox", ".mypy_cache",
    ".ruff_cache", ".pytest_cache", "dist", "build", "test-results", "playwright-report",
}
JS_SUFFIXES = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts")
JS_TEST = re.compile(r"\.(spec|test|e2e)\.(ts|tsx|js|jsx|mjs|cjs|mts|cts)$")
PY_CONFIG_NAMES = {"pytest.ini", "tox.ini", "setup.cfg", "pyproject.toml"}

ALLOW_SLEEP = re.compile(r"aqa:\s*allow-sleep\s+\S")
ALLOW_RETRIES = re.compile(r"aqa:\s*allow-retries\s+\S")


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    rule: str
    message: str

    def render(self) -> str:
        return f"{self.path}:{self.line}: {self.rule}: {self.message}"


@dataclass(frozen=True)
class Rule:
    name: str
    pattern: re.Pattern[str]
    message: str
    allow: re.Pattern[str] | None = None


def _rule(name: str, pattern: str, message: str, allow: re.Pattern[str] | None = None) -> Rule:
    return Rule(name, re.compile(pattern), message, allow)


SLEEP_MSG = "fixed wait; use auto-waiting or a poll with an explicit deadline"
RETRY_MSG = "retries hide flakiness; fix the isolation, the locator, or the product"

PY_RULES = [
    _rule("fixed-wait", r"\b(time|asyncio)\.sleep\s*\(|(?<![\w.])sleep\s*\(\s*[\d.]",
          SLEEP_MSG, ALLOW_SLEEP),
    _rule("fixed-wait", r"\.wait_for_timeout\s*\(", SLEEP_MSG, ALLOW_SLEEP),
    _rule("retry", r"--reruns\b|\breruns\s*=\s*[1-9]|pytest\.mark\.flaky|^\s*@flaky\b",
          RETRY_MSG, ALLOW_RETRIES),
    _rule("empty-assertion", r"^\s*assert\s+(True|1)\s*(,.*)?$",
          "assertion that cannot fail"),
]
JS_RULES = [
    _rule("fixed-wait", r"\.waitForTimeout\s*\(|new\s+Promise\s*\(.*\bsetTimeout\b",
          SLEEP_MSG, ALLOW_SLEEP),
    _rule("retry", r"\bretries\s*:\s*(?!0\s*[,}\n]|0\s*$)\S", RETRY_MSG, ALLOW_RETRIES),
    _rule("focused-test", r"\b(test|it|describe)(\.describe)?\.only\s*\(|\b(fdescribe|fit)\s*\(",
          "focused test silently disables the rest of the suite"),
    _rule("empty-assertion",
          r"expect\(\s*(true|1)\s*\)|expect\(\s*\w*(response|resp|res|result|body|data)\w*\s*\)"
          r"\.toBeTruthy\(\)",
          "assertion that cannot fail; assert the status, the schema or the value"),
]
CONFIG_RULES = [
    _rule("retry", r"--reruns\b|\breruns\s*=\s*[1-9]", RETRY_MSG, ALLOW_RETRIES),
]
PLACEHOLDER = r"(?i:test|fake|dummy|example|invalid|expired|wrong|placeholder|changeme|xxx|\$\{|<)"
SECRET_RULES = [
    _rule("secret", r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "private key in test code"),
    _rule("secret", r"\bAKIA[0-9A-Z]{16}\b", "AWS access key id in test code"),
    _rule("secret", r"\bgh[pousr]_[A-Za-z0-9]{36,}\b", "GitHub token in test code"),
    _rule("secret", r"\bxox[baprs]-[A-Za-z0-9-]{10,}", "Slack token in test code"),
    _rule("secret", r"\bsk-[A-Za-z0-9_-]{20,}", "API key in test code"),
    _rule("secret", r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}",
          "JWT in test code; obtain a token through a fixture"),
    _rule("secret", r"Bearer\s+(?!" + PLACEHOLDER + r")[A-Za-z0-9._~+/-]{20,}",
          "literal bearer token; read it from the environment"),
    _rule("secret",
          r"(?i)\b(api[_-]?key|secret|token)\b[\"']?\s*[:=]\s*[\"']"
          r"(?![^\"']*" + PLACEHOLDER + r")[A-Za-z0-9._~+/=-]{16,}[\"']",
          "literal credential; read it from the environment"),
]


def kind_of(path: Path) -> str | None:
    """Classify a file: 'py', 'js', 'config', or None when it is not test code."""
    name = path.name
    if name in PY_CONFIG_NAMES:
        return "config"
    if name.endswith(".py"):
        in_tests = any(p in ("tests", "test", "e2e") for p in path.parts[:-1])
        if name.startswith("test_") or name.endswith("_test.py") or name == "conftest.py":
            return "py"
        return "py" if in_tests else None
    if name.startswith("playwright.config.") or JS_TEST.search(name):
        return "js"
    if name.endswith(JS_SUFFIXES):
        in_tests = any(p in ("tests", "test", "e2e", "__tests__") for p in path.parts[:-1])
        return "js" if in_tests else None
    return None


def iter_files(paths: Iterable[Path]) -> Iterator[Path]:
    for root in paths:
        if root.is_file():
            yield root
        elif root.is_dir():
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
                for filename in sorted(filenames):
                    yield Path(dirpath) / filename


def _is_comment(line: str, kind: str) -> bool:
    stripped = line.lstrip()
    if kind == "js":
        return stripped.startswith(("//", "*", "/*"))
    return stripped.startswith(("#", ";"))


def lint_text(path: str, text: str, kind: str) -> list[Finding]:
    rules = {"py": PY_RULES, "js": JS_RULES, "config": CONFIG_RULES}[kind]
    findings: list[Finding] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not _is_comment(line, kind):
            for rule in rules:
                if rule.pattern.search(line) and not (rule.allow and rule.allow.search(line)):
                    findings.append(Finding(path, number, rule.name, rule.message))
        if kind != "config":
            for rule in SECRET_RULES:
                if rule.pattern.search(line):
                    findings.append(Finding(path, number, rule.name, rule.message))
    return findings


def lint_paths(paths: Sequence[Path]) -> list[Finding]:
    findings: list[Finding] = []
    for path in iter_files(paths):
        kind = kind_of(path)
        if kind is None:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        findings.extend(lint_text(str(path), text, kind))
    return findings


# --- coverage.md -----------------------------------------------------------------------

SC_ID = re.compile(r"\bSC-\d+\b")


@dataclass(frozen=True)
class Coverage:
    status: str
    scenarios: dict[str, str]  # SC id -> automation (auto | manual | deferred)


def parse_coverage(text: str) -> Coverage:
    lines = text.splitlines()
    meta: dict[str, str] = {}
    body_start = 0
    if lines and lines[0].strip() == "---":
        for index, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                body_start = index + 1
                break
            key, sep, value = line.partition(":")
            if sep:
                meta[key.strip().lower()] = value.split("#", 1)[0].strip()

    scenarios: dict[str, str] = {}
    automation_col: int | None = None
    id_col = 0
    for line in lines[body_start:]:
        if not line.lstrip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        lowered = [cell.lower() for cell in cells]
        if "id" in lowered:
            id_col = lowered.index("id")
            automation_col = lowered.index("automation") if "automation" in lowered else None
            continue
        if id_col >= len(cells):
            continue
        match = SC_ID.fullmatch(cells[id_col])
        if not match:
            continue
        automation = "auto"
        if automation_col is not None and automation_col < len(cells):
            automation = (cells[automation_col].lower().split() or ["auto"])[0]
        scenarios[match.group(0)] = automation
    return Coverage(meta.get("status", "").lower(), scenarios)


def load_coverage(artifacts: Path) -> Coverage | None:
    path = artifacts / "coverage.md" if artifacts.is_dir() else artifacts
    try:
        return parse_coverage(path.read_text(encoding="utf-8"))
    except OSError:
        return None


# --- traceability ----------------------------------------------------------------------

PY_TEST = re.compile(r"^\s*(?:async\s+)?def\s+(test_\w+)\s*\(")
JS_TEST_CALL = re.compile(r"^\s*(?:test|it)(?:\.(?:only|skip|fixme|fail|slow))?\s*\(\s*[`'\"](.*)")
LOOKBACK = 40
PY_LOOKAHEAD = 12
JS_LOOKAHEAD = 3


@dataclass(frozen=True)
class TestRef:
    path: str
    line: int
    name: str
    scenarios: frozenset[str]


def _leaves_test(line: str, indent: int, kind: str) -> bool:
    stripped = line.strip()
    if kind == "js":
        return not stripped or stripped.startswith("})") or bool(JS_TEST_CALL.match(line))
    if not stripped:
        return False
    # A dedent ends the body; `) -> None:` closing a multi-line signature does not.
    return len(line) - len(line.lstrip()) <= indent and not stripped.startswith(")")


def find_tests(path: str, text: str, kind: str) -> list[TestRef]:
    lines = text.splitlines()
    pattern = PY_TEST if kind == "py" else JS_TEST_CALL
    lookahead = PY_LOOKAHEAD if kind == "py" else JS_LOOKAHEAD
    tests: list[TestRef] = []
    for index, line in enumerate(lines):
        match = pattern.match(line)
        if not match:
            continue
        window = [line]
        # Above: decorators and comments attached to the test, up to the first blank line.
        for above in reversed(lines[max(0, index - LOOKBACK):index]):
            if not above.strip():
                break
            window.append(above)
        # Below: the docstring or the first lines of the body, never past the test's end.
        indent = len(line) - len(line.lstrip())
        for below in lines[index + 1:index + 1 + lookahead]:
            if _leaves_test(below, indent, kind):
                break
            window.append(below)
        ids = frozenset(SC_ID.findall("\n".join(window)))
        name = match.group(1)[:60].rstrip("`'\",( ") if kind == "js" else match.group(1)
        tests.append(TestRef(path, index + 1, name, ids))
    return tests


def trace(artifacts: Path, paths: Sequence[Path]) -> list[Finding]:
    coverage = load_coverage(artifacts)
    if coverage is None:
        return [Finding(str(artifacts), 0, "no-coverage", "coverage.md not found")]
    if not coverage.scenarios:
        return [Finding(str(artifacts), 0, "no-coverage", "coverage.md has no SC-NNN rows")]

    findings: list[Finding] = []
    seen: set[str] = set()
    for path in iter_files(paths):
        kind = kind_of(path)
        if kind not in ("py", "js") or path.name == "conftest.py":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for test in find_tests(str(path), text, kind):
            if not test.scenarios:
                findings.append(Finding(test.path, test.line, "untraced-test",
                                        f"{test.name}: no 'Scenario: SC-NNN' reference"))
            for scenario in sorted(test.scenarios):
                seen.add(scenario)
                if scenario not in coverage.scenarios:
                    findings.append(Finding(test.path, test.line, "unknown-scenario",
                                            f"{test.name}: {scenario} is not in coverage.md"))
    for scenario, automation in sorted(coverage.scenarios.items()):
        if automation == "auto" and scenario not in seen:
            findings.append(Finding(str(artifacts), 0, "uncovered-scenario",
                                    f"{scenario} is 'auto' but no test references it"))
    return findings


def gate(artifacts: Path) -> list[Finding]:
    coverage = load_coverage(artifacts)
    if coverage is None:
        return [Finding(str(artifacts), 0, "no-coverage",
                        "coverage.md not found; derive the test cases first (aqa-cases)")]
    if coverage.status != "approved":
        status = coverage.status or "missing"
        return [Finding(str(artifacts), 0, "not-approved",
                        f"coverage.md status is '{status}'; a human must review the matrix "
                        "and set 'status: approved' before test code is written")]
    return []


# --- CLI -------------------------------------------------------------------------------

def run_hook() -> int:
    """PostToolUse hook: lint the file a Write/Edit just produced. Never blocks on errors."""
    try:
        payload = json.load(sys.stdin)
        file_path = payload.get("tool_input", {}).get("file_path")
    except (ValueError, AttributeError):
        return 0
    if not isinstance(file_path, str):
        return 0
    path = Path(file_path)
    if not path.is_file():
        return 0
    findings = lint_paths([path])
    if not findings:
        return 0
    print("aqa_lint: forbidden patterns in the test file just written "
          "(see the aqa-workflow skill, 'Hard prohibitions'):", file=sys.stderr)
    for finding in findings:
        print("  " + finding.render(), file=sys.stderr)
    return 2


def report(findings: Sequence[Finding], as_json: bool) -> int:
    if as_json:
        print(json.dumps([asdict(f) for f in findings], indent=2))
    else:
        for finding in findings:
            print(finding.render())
        if findings:
            print(f"{len(findings)} finding(s)", file=sys.stderr)
    return 1 if findings else 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aqa_lint.py", description=(__doc__ or "").split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p_lint = sub.add_parser("lint", help="forbidden patterns in test files")
    p_lint.add_argument("paths", nargs="+", type=Path)
    p_trace = sub.add_parser("trace", help="tests <-> coverage.md")
    p_trace.add_argument("artifacts", type=Path, help=".agents/aqa/<slug>")
    p_trace.add_argument("paths", nargs="+", type=Path)
    p_gate = sub.add_parser("gate", help="is the coverage matrix approved?")
    p_gate.add_argument("artifacts", type=Path, help=".agents/aqa/<slug>")
    for p in (p_lint, p_trace, p_gate):
        p.add_argument("--json", action="store_true", help="print findings as JSON")
    sub.add_parser("hook", help="PostToolUse hook (reads the event from stdin)")

    args = parser.parse_args(argv)
    if args.command == "hook":
        return run_hook()
    if args.command in ("lint", "trace"):
        missing = [str(p) for p in args.paths if not p.exists()]
        if missing:
            print(f"aqa_lint: no such path: {', '.join(missing)}", file=sys.stderr)
            return 2
    if args.command == "lint":
        return report(lint_paths(args.paths), args.json)
    if args.command == "trace":
        return report(trace(args.artifacts, args.paths), args.json)
    return report(gate(args.artifacts), args.json)


if __name__ == "__main__":
    sys.exit(main())
