---
name: aqa-verify
description: >-
  Verify generated tests before they are handed over: static lint for forbidden patterns
  (fixed sleeps, retries, focused tests, hardcoded secrets), traceability against the
  coverage matrix, a full and a parallel run, and a mutation check proving each test fails
  when the behavior breaks — without leaving any change in the product. Ships aqa_lint.py.
  Use when: "verify the tests," "check these tests can fail," "lint the generated tests,"
  after aqa-generate, or to audit tests this agent wrote earlier.
  Not for: diagnosing a test that fails intermittently — use test-reliability.
  Related: aqa-workflow, aqa-generate, test-reliability.
argument-hint: "<slug> [test paths]"
license: MIT
metadata:
  author: initk.tech
  version: "1.0"
  category: workflow
---

<objective>
A generated test that passes is not evidence. This skill produces the evidence: the test is
clean, traceable, stable in parallel, and red when the behavior it covers is broken.
</objective>

Rules are in `aqa-workflow` — in particular "Proving a test can fail".

## The linter

`scripts/aqa_lint.py` sits next to this file. Python 3.9+, standard library only.

```bash
L="python3 <this skill's directory>/scripts/aqa_lint.py"

$L lint tests/                           # forbidden patterns in test files
$L trace .agents/aqa/<slug> tests/       # tests ↔ coverage.md, both directions
$L gate  .agents/aqa/<slug>              # is the matrix approved?
```

Exit code 0 is clean, 1 is findings, 2 is a usage error. `--json` prints findings as JSON.

| Rule | Finds | Escape hatch |
|------|-------|--------------|
| `fixed-wait` | `time.sleep`, `asyncio.sleep`, `wait_for_timeout`, `waitForTimeout` | `aqa: allow-sleep <reason>` on the line — polling helpers only |
| `retry` | `--reruns`, `@pytest.mark.flaky`, `retries: N>0`, `test.describe.configure({ retries })` | `aqa: allow-retries <ticket>` — quarantine only |
| `focused-test` | `.only(`, `fdescribe`, `fit(` | none |
| `secret` | Private keys, cloud and API tokens, JWTs, literal bearer tokens and API keys | none — read it from the environment |
| `empty-assertion` | `assert True`, `expect(true)`, `expect(response).toBeTruthy()` | none |
| `untraced-test` | A test with no `SC-NNN` reference | — |
| `unknown-scenario` | A referenced `SC-NNN` that is not in `coverage.md` | — |
| `uncovered-scenario` | An `auto` row with no test | Mark the row `manual` or `deferred` with a reason |

The same script runs as a `PostToolUse` hook in the Claude Code plugin, so a forbidden
pattern is reported the moment a test file is written.

## Steps

1. **Static.** `lint` and `trace` exit 0. Then the project's type check and linters, which
   also catch hallucinated imports: `tsc --noEmit`, `ruff check`, `mypy`.
2. **Grounding.** For each new test, confirm the endpoints, selectors and test ids it uses
   exist in the source or the running app. Anything that does not is a hallucination: fix
   it or mark the row `deferred`.
3. **Run in isolation, then in parallel.** The new tests alone, then the whole suite with
   `-n auto` / `fullyParallel`. A test that passes alone and fails in parallel has shared
   state — fix the isolation, do not add a retry.
4. **Mutation check, per test.** Follow "Proving a test can fail" in `aqa-workflow`: mutate
   in a throwaway worktree (or at the network boundary when the product is not local), run
   the one test, confirm it fails on the oracle's assertion, discard the mutation. A
   surviving mutation means the oracle is weak — strengthen the test.
5. **Confirm the product is untouched.** `git status --porcelain` shows only test files and
   `.agents/aqa/<slug>/`; `git worktree list` shows no leftover worktree.
6. **Write `verification.md`:**

   ```markdown
   | Test | SC | Lint | Run | Parallel | Mutation | Result | Decision |
   |------|----|------|-----|----------|----------|--------|----------|
   | tests/api/test_discount.py::test_expired_code_is_rejected | SC-002 | ok | pass | pass | status 422→200 in apply_code() | failed on status assert | KEEP |
   | tests/api/test_discount.py::test_total_never_negative | SC-003 | ok | **fail** | — | not needed: red on a real bug | total = -5.00 | KEEP (bug) |
   ```

   Decisions: **KEEP**, **MODIFY** (list what), **REJECT** (wrong requirement or layer),
   **DEFER** (blocked on an ambiguity). Add the model id and the date of the run.
7. **Report.** Tests added, bugs found (red tests kept, with reproduction), manual and
   deferred rows, surviving mutations, anything that could not be verified and why.

## Done when

- `lint` and `trace` exit 0; the project's type check passes.
- Every new test has a mutation result or a stated reason in `verification.md`.
- `git status` shows no product file changed and no mutation worktree remains.
