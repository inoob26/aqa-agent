#!/usr/bin/env python3
"""aqa-agent lint: gate, structure, traceability and static checks for .agents/aqa/<slug>/.

Commands:
  gate   <dir>                                  exit 1 unless test-cases.md has status: approved
  cases  <dir>                                  check requirements.md, test-cases.md, coverage.md
  trace  <dir> <paths...> [--layer api|ui]      check TC/REQ tags in test code against the artifacts
  lint   <paths...>                             check test code and feature files for bad patterns
  report <dir> --results <json> [--mutations <json>] [--out <md>]
                                                write report.md from a Playwright JSON report

Exit codes: 0 = ok, 1 = check failed, 2 = usage or missing files.
Standard library only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

TC_RE = re.compile(r"\bTC-\d{3,}\b")
REQ_RE = re.compile(r"\bREQ-\d+\b")
TC_HEAD_RE = re.compile(r"^###\s+(TC-\d{3,})\s*:\s*(.+?)\s*$")
REQ_HEAD_RE = re.compile(r"^###\s+(REQ-\d+)\s*:\s*(.+?)\s*$")
FIELD_RE = re.compile(r"^-\s+([A-Za-z][A-Za-z ]*?)\s*:\s*(.*)$")

STATUSES = {"draft", "approved"}
PRIORITIES = {"P0", "P1", "P2", "P3"}
LAYERS = {"api", "ui", "unit"}
AUTOMATION = {"auto", "manual", "deferred", "removed"}
TECHNIQUES = {
    "happy-path", "EP", "BVA", "negative", "state-transition",
    "decision-table", "pairwise", "error-guessing",
}
TC_FIELDS = [
    "Requirement", "Priority", "Layer", "Technique",
    "Preconditions", "Test data", "Steps", "Expected",
]
CODE_EXT = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts"}
SCAN_EXT = CODE_EXT | {".feature"}
SKIP_DIRS = {"node_modules", ".git", ".features-gen", "test-results", "playwright-report", "dist"}


# --------------------------------------------------------------------------- output

class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def finish(self, ok_msg: str) -> int:
        for w in self.warnings:
            print(f"WARN  {w}")
        for e in self.errors:
            print(f"ERROR {e}")
        if self.errors:
            print(f"FAILED: {len(self.errors)} error(s), {len(self.warnings)} warning(s)")
            return 1
        print(f"OK: {ok_msg}" + (f" ({len(self.warnings)} warning(s))" if self.warnings else ""))
        return 0


def die(msg: str) -> "NoReturn":  # type: ignore[name-defined]
    print(f"ERROR {msg}", file=sys.stderr)
    sys.exit(2)


# --------------------------------------------------------------------------- parsing

@dataclass
class TestCase:
    id: str
    title: str
    line: int
    fields: dict[str, str] = field(default_factory=dict)

    @property
    def reqs(self) -> list[str]:
        return REQ_RE.findall(self.fields.get("Requirement", ""))


@dataclass
class CoverageRow:
    tc: str
    requirement: str
    layer: str
    priority: str
    automation: str
    test: str
    notes: str
    line: int

    @property
    def reqs(self) -> list[str]:
        return REQ_RE.findall(self.requirement)


def read(path: Path) -> str:
    if not path.is_file():
        die(f"missing file: {path}")
    return path.read_text(encoding="utf-8")


def front_matter(text: str) -> dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    out: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return out
        if ":" in line and not line.lstrip().startswith("#"):
            key, _, value = line.partition(":")
            out[key.strip()] = value.split(" #")[0].strip()
    return {}  # no closing marker


def parse_requirements(text: str) -> dict[str, tuple[str, int]]:
    reqs: dict[str, tuple[str, int]] = {}
    for n, line in enumerate(text.splitlines(), 1):
        m = REQ_HEAD_RE.match(line)
        if m:
            reqs.setdefault(m.group(1), (m.group(2), n))
    return reqs


def parse_requirement_dupes(text: str) -> list[str]:
    seen, dupes = set(), []
    for line in text.splitlines():
        m = REQ_HEAD_RE.match(line)
        if m:
            if m.group(1) in seen:
                dupes.append(m.group(1))
            seen.add(m.group(1))
    return dupes


def parse_cases(text: str) -> list[TestCase]:
    cases: list[TestCase] = []
    current: TestCase | None = None
    last_key: str | None = None
    for n, line in enumerate(text.splitlines(), 1):
        head = TC_HEAD_RE.match(line)
        if head:
            current = TestCase(head.group(1), head.group(2), n)
            cases.append(current)
            last_key = None
            continue
        if current is None:
            continue
        if line.startswith("#"):
            current, last_key = None, None
            continue
        m = FIELD_RE.match(line)
        if m and m.group(1) in TC_FIELDS:
            last_key = m.group(1)
            current.fields[last_key] = m.group(2).strip()
        elif last_key and line.strip() and (line.startswith(" ") or line.startswith("|")):
            sep = "\n" if current.fields[last_key] else ""
            current.fields[last_key] += sep + line.strip()
    return cases


def split_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def parse_coverage(text: str) -> list[CoverageRow]:
    rows: list[CoverageRow] = []
    for n, line in enumerate(text.splitlines(), 1):
        if not line.lstrip().startswith("|"):
            continue
        cells = split_row(line)
        if not cells or not TC_RE.fullmatch(cells[0]):
            continue
        cells += [""] * (7 - len(cells))
        rows.append(CoverageRow(*cells[:7], line=n))
    return rows


def load(dir_: Path):
    if not dir_.is_dir():
        die(f"not a folder: {dir_}")
    req_text = read(dir_ / "requirements.md")
    tc_text = read(dir_ / "test-cases.md")
    cov_text = read(dir_ / "coverage.md")
    return req_text, tc_text, cov_text


def iter_files(paths: list[str]):
    for p in paths:
        path = Path(p)
        if path.is_file():
            if path.suffix in SCAN_EXT:
                yield path
        elif path.is_dir():
            for f in sorted(path.rglob("*")):
                if f.is_file() and f.suffix in SCAN_EXT and not (set(f.parts) & SKIP_DIRS):
                    yield f
        else:
            die(f"path does not exist: {p}")


# --------------------------------------------------------------------------- gate

def cmd_gate(args) -> int:
    dir_ = Path(args.dir)
    fm = front_matter(read(dir_ / "test-cases.md"))
    status = fm.get("status", "")
    if status == "approved":
        who = fm.get("approved_by") or "unknown reviewer"
        print(f"OK: {dir_} is approved by {who}")
        return 0
    print(
        f"GATE CLOSED: {dir_ / 'test-cases.md'} has status '{status or 'missing'}'.\n"
        "A person must review the test cases and set 'status: approved' in the front matter."
    )
    return 1


# --------------------------------------------------------------------------- cases

def cmd_cases(args) -> int:
    dir_ = Path(args.dir)
    req_text, tc_text, cov_text = load(dir_)
    r = Report()

    fm = front_matter(tc_text)
    if not fm:
        r.error("test-cases.md: no front matter between '---' lines")
    elif fm.get("status") not in STATUSES:
        r.error(f"test-cases.md: status must be one of {sorted(STATUSES)}, got '{fm.get('status')}'")
    elif fm.get("status") == "approved" and not fm.get("approved_by"):
        r.warn("test-cases.md: status is approved but approved_by is empty")

    reqs = parse_requirements(req_text)
    if not reqs:
        r.error("requirements.md: no '### REQ-N: <title>' headings")
    for d in parse_requirement_dupes(req_text):
        r.error(f"requirements.md: duplicate {d}")
    for rid, (_, line) in reqs.items():
        block = req_text.splitlines()[line:line + 6]
        if not any(l.startswith("- Source:") and l.partition(":")[2].strip() for l in block):
            r.error(f"requirements.md:{line}: {rid} has no Source")

    cases = parse_cases(tc_text)
    if not cases:
        r.error("test-cases.md: no '### TC-NNN: <title>' headings")
    seen: dict[str, TestCase] = {}
    for tc in cases:
        where = f"test-cases.md:{tc.line}: {tc.id}"
        if tc.id in seen:
            r.error(f"{where}: duplicate ID (first at line {seen[tc.id].line})")
            continue
        seen[tc.id] = tc
        for f in TC_FIELDS:
            if not tc.fields.get(f, "").strip():
                r.error(f"{where}: field '{f}' is missing or empty")
        if tc.fields.get("Priority") and tc.fields["Priority"] not in PRIORITIES:
            r.error(f"{where}: Priority '{tc.fields['Priority']}' is not one of {sorted(PRIORITIES)}")
        if tc.fields.get("Layer") and tc.fields["Layer"] not in LAYERS:
            r.error(f"{where}: Layer '{tc.fields['Layer']}' is not one of {sorted(LAYERS)}")
        for t in [t.strip() for t in tc.fields.get("Technique", "").split(",") if t.strip()]:
            if t not in TECHNIQUES:
                r.error(f"{where}: Technique '{t}' is not one of {sorted(TECHNIQUES)}")
        if tc.fields.get("Requirement") and not tc.reqs:
            r.error(f"{where}: Requirement has no REQ-N reference")
        for rid in tc.reqs:
            if rid not in reqs:
                r.error(f"{where}: {rid} is not in requirements.md")
        if re.search(r"\b(works correctly|works as expected|shows an error|is fast)\b",
                     tc.fields.get("Expected", ""), re.I):
            r.warn(f"{where}: Expected contains a vague oracle")

    covered = {rid for tc in seen.values() for rid in tc.reqs}
    for rid in reqs:
        if rid not in covered:
            r.error(f"requirements.md: {rid} has no test case")

    rows = parse_coverage(cov_text)
    by_tc: dict[str, CoverageRow] = {}
    for row in rows:
        where = f"coverage.md:{row.line}: {row.tc}"
        if row.tc in by_tc:
            r.error(f"{where}: duplicate row")
            continue
        by_tc[row.tc] = row
        if row.automation not in AUTOMATION:
            r.error(f"{where}: Automation '{row.automation}' is not one of {sorted(AUTOMATION)}")
        if row.automation in {"manual", "deferred"} and not row.notes:
            r.error(f"{where}: '{row.automation}' needs a reason in Notes")
        tc = seen.get(row.tc)
        if tc is None:
            r.error(f"{where}: TC is not in test-cases.md")
            continue
        if sorted(row.reqs) != sorted(tc.reqs):
            r.error(f"{where}: Requirement '{row.requirement}' differs from test-cases.md '{tc.fields.get('Requirement')}'")
        if row.layer != tc.fields.get("Layer"):
            r.error(f"{where}: Layer '{row.layer}' differs from test-cases.md '{tc.fields.get('Layer')}'")
        if row.priority != tc.fields.get("Priority"):
            r.error(f"{where}: Priority '{row.priority}' differs from test-cases.md '{tc.fields.get('Priority')}'")
        if row.test and not Path(row.test).is_file():
            r.warn(f"{where}: Test file '{row.test}' does not exist (relative to the current folder)")
    for tid in seen:
        if tid not in by_tc:
            r.error(f"coverage.md: {tid} has no row")

    return r.finish(f"{len(reqs)} requirement(s), {len(seen)} test case(s), {len(by_tc)} coverage row(s)")


# --------------------------------------------------------------------------- trace

def cmd_trace(args) -> int:
    dir_ = Path(args.dir)
    _, tc_text, cov_text = load(dir_)
    r = Report()
    cases = {tc.id: tc for tc in parse_cases(tc_text)}
    rows = {row.tc: row for row in parse_coverage(cov_text)}

    found: dict[str, set[Path]] = {}
    for f in iter_files(args.paths):
        text = f.read_text(encoding="utf-8", errors="replace")
        ids = set(TC_RE.findall(text))
        file_reqs = set(REQ_RE.findall(text))
        for tid in sorted(ids):
            found.setdefault(tid, set()).add(f)
            tc = cases.get(tid)
            if tc is None:
                r.error(f"{f}: {tid} is not in test-cases.md")
                continue
            if args.layer and tc.fields.get("Layer") != args.layer:
                r.warn(f"{f}: {tid} has Layer '{tc.fields.get('Layer')}', not '{args.layer}'")
            missing = [rid for rid in tc.reqs if rid not in file_reqs]
            if missing:
                r.error(f"{f}: {tid} has no tag for {', '.join(missing)}")
            row = rows.get(tid)
            if row and row.automation in {"deferred", "removed"}:
                r.warn(f"{f}: {tid} is '{row.automation}' in coverage.md but has a test")

    # A feature-only path set is enough for BDD: the steps carry no tags.
    expected = [
        row for row in rows.values()
        if row.automation == "auto"
        and (row.layer == args.layer if args.layer else row.layer in {"api", "ui"})
    ]
    for row in expected:
        if row.tc not in found:
            r.error(f"{row.tc} ({row.layer}, auto) has no test in the given paths")
        elif row.test and all(Path(row.test).resolve() != p.resolve() for p in found[row.tc]):
            r.warn(f"coverage.md: {row.tc} Test column '{row.test}' is not a file that contains the tag")
        elif not row.test:
            r.warn(f"coverage.md: {row.tc} has a test but the Test column is empty")

    return r.finish(f"{len(found)} TC id(s) traced, {len(expected)} auto row(s) expected")


# --------------------------------------------------------------------------- lint

CODE_RULES: list[tuple[str, re.Pattern[str], str]] = [
    ("error", re.compile(r"\b(test|describe|it|Scenario)\.only\s*\("), "focused test (.only)"),
    ("error", re.compile(r"\bwaitForTimeout\s*\("), "waitForTimeout: use a web-first assertion"),
    ("warn", re.compile(r"""\b(password|passwd|secret|token|apiKey|api_key)\s*[:=]\s*['"`][^'"`$]{4,}['"`]""", re.I),
     "hard-coded secret: read it from an env var"),
    ("warn", re.compile(r"\bnew Promise\s*\(\s*\w+\s*=>\s*setTimeout"), "sleep with setTimeout"),
    ("warn", re.compile(r"\bpage\.\$\$?\s*\("), "page.$ / page.$$: use a locator"),
    ("warn", re.compile(r"""locator\(\s*['"`](xpath=|//)"""), "XPath locator"),
    ("warn", re.compile(r"\bforce\s*:\s*true\b"), "force: true hides an actionability problem"),
    ("warn", re.compile(r"\b(test|it)\.(skip|fixme)\s*\(\s*['\"`]"), "skipped test: add the reason as a condition or remove it"),
    ("warn", re.compile(r"\.nth\(\s*\d+\s*\)"), "nth(): check that the position is stable"),
    ("warn", re.compile(r"\bwaitForLoadState\(\s*['\"]networkidle['\"]"), "networkidle is not reliable"),
]
TEST_TITLE_RE = re.compile(r"""(?<![\w.])test\(\s*(['"`])((?:\\.|(?!\1).)*)\1\s*,\s*(\{[^)]*?\})?""", re.S)


def lint_code(f: Path, text: str, r: Report) -> None:
    for n, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("//"):
            continue
        for level, rx, msg in CODE_RULES:
            if rx.search(line):
                (r.error if level == "error" else r.warn)(f"{f}:{n}: {msg}")
    is_spec = re.search(r"\.(spec|test)\.[cm]?[jt]sx?$", f.name) is not None
    if not is_spec:
        return
    for m in TEST_TITLE_RE.finditer(text):
        title, opts = m.group(2), m.group(3) or ""
        n = text.count("\n", 0, m.start()) + 1
        if not (TC_RE.search(title) or TC_RE.search(opts)):
            # a title built from a loop variable is checked by `trace`, not here
            if "${" not in title:
                r.error(f"{f}:{n}: test '{title[:60]}' has no TC id in the title or tags")


def lint_feature(f: Path, text: str, r: Report) -> None:
    pending: list[str] = []
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("@"):
            pending += line.split()
            if "@only" in line.split():
                r.error(f"{f}:{n}: @only tag")
            continue
        if re.match(r"(Scenario|Scenario Outline|Scenario Template|Example)\s*:", line):
            if not any(TC_RE.fullmatch(t.lstrip("@")) for t in pending):
                r.error(f"{f}:{n}: scenario has no @TC-NNN tag")
            if not any(REQ_RE.fullmatch(t.lstrip("@")) for t in pending):
                r.error(f"{f}:{n}: scenario has no @REQ-N tag")
            if not ({"@api", "@ui"} & set(pending)):
                r.warn(f"{f}:{n}: scenario has no @api or @ui tag")
        if re.match(r"(Given|When|Then|And|But)\b", line):
            if re.search(r"\b(GET|POST|PUT|PATCH|DELETE)\s+/", line) or re.search(r"\b(locator|getBy\w+|css=|xpath)", line):
                r.warn(f"{f}:{n}: implementation detail in a step: use business language")
        pending = []


def cmd_lint(args) -> int:
    r = Report()
    count = 0
    for f in iter_files(args.paths):
        count += 1
        text = f.read_text(encoding="utf-8", errors="replace")
        if f.suffix == ".feature":
            lint_feature(f, text, r)
        else:
            lint_code(f, text, r)
    if count == 0:
        r.error("no .ts/.js/.feature files in the given paths")
    return r.finish(f"{count} file(s) checked")


# --------------------------------------------------------------------------- report

RANK = {"unexpected": 4, "flaky": 3, "skipped": 2, "expected": 1}
LABEL = {"unexpected": "failed", "flaky": "flaky", "skipped": "skipped", "expected": "passed"}


def walk_specs(suite: dict):
    for spec in suite.get("specs", []):
        yield spec
    for child in suite.get("suites", []):
        yield from walk_specs(child)


def cmd_report(args) -> int:
    dir_ = Path(args.dir)
    req_text, tc_text, cov_text = load(dir_)
    reqs = parse_requirements(req_text)
    cases = {tc.id: tc for tc in parse_cases(tc_text)}
    rows = {row.tc: row for row in parse_coverage(cov_text)}

    try:
        data = json.loads(read(Path(args.results)))
    except json.JSONDecodeError as e:
        die(f"{args.results}: not valid JSON: {e}")
    results: dict[str, str] = {}
    for suite in data.get("suites", []):
        for spec in walk_specs(suite):
            ids = set(TC_RE.findall(spec.get("title", "")))
            ids |= {t.lstrip("@") for t in spec.get("tags", []) if TC_RE.fullmatch(t.lstrip("@"))}
            for t in spec.get("tests", []):
                status = t.get("status", "skipped")
                for tid in ids:
                    if RANK.get(status, 0) > RANK.get(results.get(tid, ""), 0):
                        results[tid] = status

    mutations: dict[str, list[dict]] = {}
    if args.mutations and Path(args.mutations).is_file():
        for m in json.loads(read(Path(args.mutations))):
            mutations.setdefault(m.get("tc", "?"), []).append(m)

    def result_of(tid: str) -> str:
        row = rows.get(tid)
        if row and row.automation != "auto":
            return row.automation
        return LABEL.get(results.get(tid, ""), "not run")

    def mut_of(tid: str) -> str:
        ms = mutations.get(tid, [])
        if not ms:
            return ""
        killed = sum(1 for m in ms if m.get("result") == "killed")
        return f"{killed}/{len(ms)} killed"

    lines = [f"# Report: {dir_.name}", ""]
    totals: dict[str, int] = {}
    for tid in cases:
        totals[result_of(tid)] = totals.get(result_of(tid), 0) + 1
    all_m = [m for ms in mutations.values() for m in ms]
    killed = sum(1 for m in all_m if m.get("result") == "killed")
    req_ok = sum(
        1 for rid in reqs
        if any(result_of(tc.id) == "passed" for tc in cases.values() if rid in tc.reqs)
    )
    lines += [
        "## Totals", "",
        f"- Requirements with at least one passed test: {req_ok} / {len(reqs)}",
        "- Test cases: " + ", ".join(f"{k} {v}" for k, v in sorted(totals.items())),
        f"- Mutation score: {killed} / {len(all_m)}" if all_m else "- Mutation score: not measured",
        "",
        "## Test cases", "",
        "| TC | Requirement | Layer | Priority | Result | Mutation | Test | Notes |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for tid, tc in cases.items():
        row = rows.get(tid)
        lines.append(
            f"| {tid} | {', '.join(tc.reqs)} | {tc.fields.get('Layer', '')} | "
            f"{tc.fields.get('Priority', '')} | {result_of(tid)} | {mut_of(tid)} | "
            f"{row.test if row else ''} | {row.notes if row else ''} |"
        )
    lines += ["", "## Requirements", "", "| REQ | Title | Test cases | Status |", "|---|---|---|---|"]
    for rid, (title, _) in reqs.items():
        tcs = [tc.id for tc in cases.values() if rid in tc.reqs]
        states = [result_of(t) for t in tcs]
        if "failed" in states:
            status = "failed"
        elif "passed" in states:
            status = "covered" if all(s in {"passed", "manual"} for s in states) else "partial"
        else:
            status = "not covered by a passed test"
        lines.append(f"| {rid} | {title} | {', '.join(tcs)} | {status} |")
    unknown = sorted(set(results) - set(cases))
    if unknown:
        lines += ["", f"Results for unknown TC ids (ignored): {', '.join(unknown)}"]

    out = Path(args.out) if args.out else dir_ / "report.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"OK: wrote {out}")
    return 0


# --------------------------------------------------------------------------- main

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="aqa_lint.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("gate"); s.add_argument("dir"); s.set_defaults(fn=cmd_gate)
    s = sub.add_parser("cases"); s.add_argument("dir"); s.set_defaults(fn=cmd_cases)
    s = sub.add_parser("trace"); s.add_argument("dir"); s.add_argument("paths", nargs="+")
    s.add_argument("--layer", choices=["api", "ui"]); s.set_defaults(fn=cmd_trace)
    s = sub.add_parser("lint"); s.add_argument("paths", nargs="+"); s.set_defaults(fn=cmd_lint)
    s = sub.add_parser("report"); s.add_argument("dir"); s.add_argument("--results", required=True)
    s.add_argument("--mutations"); s.add_argument("--out"); s.set_defaults(fn=cmd_report)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
