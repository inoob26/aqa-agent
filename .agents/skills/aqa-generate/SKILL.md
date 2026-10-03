---
name: aqa-generate
description: >-
  Write executable tests from an approved coverage matrix in .agents/aqa/<slug>/: checks
  the review gate, picks language and layer from the project, reuses existing fixtures and
  page objects, and adds a traceability reference to every test.
  Use when: "write the tests," "generate tests from the matrix," "implement SC-001..SC-010,"
  after aqa-cases has been reviewed.
  Not for: deriving the test cases — use aqa-cases first.
  Not for: proving the tests can fail — use aqa-verify afterwards.
  Related: aqa-workflow, aqa-cases, aqa-verify, python-test-automation, playwright-automation, api-testing, unit-testing.
argument-hint: "<slug> [SC ids]"
license: MIT
metadata:
  author: initk.tech
  version: "1.0"
  category: workflow
---

<objective>
Translate approved scenarios and oracles into test code that looks like it was written by
the team that owns the suite — same fixtures, same naming, same layout — and that a script
can trace back to the matrix.
</objective>

Rules are in `aqa-workflow`. Load it, then the one language skill the layer needs:
`unit-testing` (unit, any language), `python-test-automation` (Python API and E2E),
`playwright-automation` (TypeScript E2E), `api-testing` (TypeScript API). Read a skill's
`references/` file only when the task needs that depth.

## Steps

1. **Check the gate.** Run the linter that ships next to the `aqa-verify` skill:

   ```bash
   python3 <skills dir>/aqa-verify/scripts/aqa_lint.py gate .agents/aqa/<slug>
   ```

   A non-zero exit means the matrix is still `draft`: stop and ask for the review. Do not
   edit the status yourself.
2. **Read the artifacts** — `coverage.md`, `scenarios.md`, `oracles.md` — and select the rows
   to implement: the given ids, or every `auto` row that has no test yet.
3. **Read the existing suite** before writing a line: test layout, `conftest.py` or fixture
   files, page objects, data factories, naming, markers, how auth is obtained. Reuse them.
   A new helper is justified only when nothing existing fits.
4. **Ground every reference.** Endpoints come from the router or the OpenAPI file; selectors
   from the component source or a live page snapshot (Playwright MCP `browser_snapshot`, or
   `npx playwright codegen <url>`); fixtures and imports from the suite. If a scenario needs
   something that does not exist (a missing `data-testid`, no seeding endpoint), mark the row
   `deferred` with the reason instead of inventing it.
5. **Write the tests.** One scenario per test unless parametrization merges rows; setup and
   teardown in fixtures; every test carries `Scenario: SC-NNN` and `Requirement: REQ-N` as
   `aqa-workflow` specifies.
6. **Static pass.**

   ```bash
   python3 <skills dir>/aqa-verify/scripts/aqa_lint.py lint <test paths>
   python3 <skills dir>/aqa-verify/scripts/aqa_lint.py trace .agents/aqa/<slug> <test paths>
   ```

   Plus the project's own linters and type check (`ruff`, `mypy`, `tsc --noEmit`, `eslint`).
7. **Run the new tests once.** A failure is either a defect in the test (fix it) or a defect
   in the product (keep the test red, record the bug). Never change the product.
8. **Hand over to `aqa-verify`** for the mutation check and the report.

## Done when

- Every selected `auto` row has a test, or is marked `deferred` with a reason in `coverage.md`.
- `aqa_lint.py lint` and `aqa_lint.py trace` exit 0.
- The project's linters and type check pass on the new files.
- No file outside the test tree and `.agents/aqa/<slug>/` was modified.
