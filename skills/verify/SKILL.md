---
name: verify
description: >-
  Prove that the generated tests for .agents/aqa/<slug>/ run and can fail: runs them with the
  Playwright JSON reporter, makes a mutation check (changes one oracle per test and expects a
  red result), checks the trace from REQ to TC to test, and writes report.md.
  Use when: "verify the tests," "do the tests really check anything," "coverage report for
  <slug>," after api-tests or playwright-tests.
  Not for: writing tests — use api-tests or playwright-tests.
  Related: workflow, test-cases, bdd, api-tests, playwright-tests.
argument-hint: "<slug | .agents/aqa/<slug>> [--no-mutation] [TC ids]"
license: MIT
metadata:
  author: Nikolay Morgunov
  version: "0.1"
  category: workflow
---

<objective>
Give the reviewer evidence, not a claim: which requirements have passing tests, which tests
fail and why, and proof that each test detects a wrong result.
</objective>

Input: $ARGUMENTS

Load the `workflow` skill of this plugin first.

## Steps

1. **Static checks.** Collect the test files from the `Test` column of `coverage.md`.

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/aqa_lint.py" cases .agents/aqa/<slug>
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/aqa_lint.py" lint <test files>
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/aqa_lint.py" trace .agents/aqa/<slug> <test files>
   ```

   Report each error. Continue with the run only when `lint` passes.
2. **Run the tests.** Select them by tag, so that BDD and plain tests both run:

   ```bash
   npx bddgen   # only if the project uses playwright-bdd
   PLAYWRIGHT_JSON_OUTPUT_NAME=.agents/aqa/<slug>/results.json \
     npx playwright test --grep "@TC-001|@TC-002" --reporter=list,json
   ```

   Put every `auto` TC ID with a test in the `--grep` pattern.
3. **Classify each failure.** Read the error and the trace. A test defect → fix the test and
   run again. A product defect → keep it red, write it in the `Notes` column of `coverage.md`
   as `BUG: <one line>`. An environment problem → stop and tell the person.
4. **Mutation check** (skip with `--no-mutation`). For each passed test of priority P0 and
   P1 (all tests if there are 20 or fewer):
   1. Save the original file content.
   2. Change exactly one oracle in the test: an expected status code (202 → 203), an
      expected text, an expected count, or negate one `expect` (`.not`).
   3. Run only that test. Expected result: failure. A pass means the test does not check its
      oracle: record it as `survived`.
   4. Restore the original file content and confirm with `git diff --quiet -- <file>` (or a
      byte compare when there is no git).

   Write the results to `.agents/aqa/<slug>/mutations.json`:
   `[{"tc": "TC-001", "mutation": "status 202 -> 203", "result": "killed"}]`.
   Never mutate product code.
5. **Fix survivors.** A survived mutation means a weak oracle. Make the assertion stronger,
   run the test and the mutation again. If it is not possible, write the reason in `Notes`.
6. **Write the report.**

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/aqa_lint.py" report .agents/aqa/<slug> \
     --results .agents/aqa/<slug>/results.json --mutations .agents/aqa/<slug>/mutations.json
   ```

   This writes `report.md`. Add a short `## Findings` section at the end: product defects,
   flaky tests, deferred rows and their blockers, survived mutations.
7. **Tell the person** the totals: REQs covered by a passing test, TCs passed / failed /
   not run, product defects, mutation score.

## Done when

- `report.md` exists and lists every TC with its result.
- Every failure is classified as a product defect (with a `BUG:` note) or fixed.
- Every mutated test file is equal to its original content.
- No product file was modified.
