---
name: aqa-workflow
description: >-
  The operating rules of the aqa (test automation) agent: the mandatory order of work
  (context → scope → test cases → review gate → code → verification), where the artifacts
  live (.agents/aqa/<slug>/), the traceability format, how to choose language and test
  layer, how to prove a test can fail without changing the product, and the hard
  prohibitions. Load this FIRST for any request to derive test cases or write automated
  tests from a task description (PRD, user story, ticket, diff, OpenAPI spec, bug report).
  Use when: "write tests for this feature," "test cases from this ticket," "cover this
  diff," "regression test for this bug," or when acting as the aqa agent.
  Related: aqa-cases, aqa-generate, aqa-verify, qa-project-context, ai-test-generation.
license: MIT
metadata:
  author: initk.tech
  version: "1.0"
  category: foundation
---

<objective>
An agent handed a task description and a blank file writes forty happy-path tests against
endpoints it guessed. This skill is the contract that prevents it: test cases exist as
reviewed files before any test code does, every test traces back to a requirement, and
every test is shown to fail when the behavior it covers is broken.
</objective>

## Order of work

The order is mandatory. Each step has an entry skill; the deep how-to lives in the skill
named in the last column.

| # | Step | Entry | Output | Depth |
|---|------|-------|--------|-------|
| 1 | Context | `qa-project-context` | `.agents/qa-project-context.md` | — |
| 2 | Scope (sprint/release only) | `test-planning` | test plan | — |
| 3 | Test cases | `aqa-cases` | `requirements.md`, `risks.md`, `coverage.md`, `scenarios.md`, `oracles.md` | `ai-test-generation` |
| 4 | **Review gate** | human | `coverage.md` → `status: approved` | — |
| 5 | Code | `aqa-generate` | test files with traceability | `unit-testing`, `python-test-automation`, `playwright-automation`, `api-testing` |
| 6 | Verification | `aqa-verify` | `verification.md` | `test-reliability` for flaky results |

1. **Context.** Read `.agents/qa-project-context.md` in the target project. If it is missing,
   offer to create it and carry on with what the repository itself shows (manifests, existing
   tests, CI config).
2. **Scope.** A single feature, ticket, diff or bug goes straight to step 3.
3. **Test cases.** Requirements, risks and the coverage matrix are written to files first.
4. **Review gate.** Stop after the coverage matrix and ask the human to review it. Do not
   write test code while `coverage.md` says `status: draft`. Only the human's explicit
   approval flips it to `approved` — the agent never approves its own matrix. Open
   ambiguities from `requirements.md` are resolved here, not silently guessed.
5. **Code.** A mechanical translation of approved scenarios and oracles into the project's
   framework.
6. **Verification.** Static checks, a real run, and a mutation check per test.

When the user explicitly waives the gate ("no review, just write the tests"), record that in
`coverage.md` as `status: approved` with `approved_by: user (gate waived)` and continue.

Waiving the gate skips the pause, not the files. A one-test request — a regression test for
a bug report — still gets its slug directory with `requirements.md` and a `coverage.md`
holding the reported case and its nearest boundary and negative neighbours, written
**before** the test. A test whose `SC-` id points at no matrix is untraceable.

## Artifact contract

All intermediates live in the **target project** under `.agents/aqa/<slug>/`, where `<slug>`
is the ticket id (`PROJ-123`) or a kebab-case feature name (`checkout-discounts`). They are
committed with the tests: they are the reviewable source the tests were derived from, and
the next run resumes from them instead of starting over.

| File | Content |
|------|---------|
| `requirements.md` | Source reference, entities, business rules, `REQ-N` (stated), `IMP-N` (inferred — each flagged for confirmation), open ambiguities |
| `risks.md` | Risk table, invariants `INV-N`, edge cases derived from risks |
| `coverage.md` | Front matter + the coverage matrix (below) |
| `scenarios.md` | One Given/When/Then per `SC-NNN`, with test data |
| `oracles.md` | Per `SC-NNN`: what is asserted and how (UI, data, negative, side effect) |
| `verification.md` | Per test: static checks, run result, mutation check, review decision |

`coverage.md` format — the front matter and the `ID` column are parsed by `aqa_lint.py`:

```markdown
---
slug: checkout-discounts
source: docs/prd/checkout.md
status: draft            # draft | approved
approved_by:
---

| ID | Requirement | Scenario | Category | Priority | Layer | Oracle | Automation |
|----|-------------|----------|----------|----------|-------|--------|------------|
| SC-001 | REQ-1 | Valid code reduces the total | Happy path | P0 | API | Data: total = sum − discount | auto |
| SC-002 | REQ-1 | Expired code is rejected | Negative | P0 | API | 422 + error code, total unchanged | auto |
| SC-003 | INV-1 | Total never goes below zero | Invariant | P0 | Unit | Data: total >= 0 | auto |
| SC-004 | REQ-2 | Screen reader announces the discount | Accessibility | P2 | E2E | Live region text | manual |
```

`Automation` is `auto`, `manual` (a human runs it) or `deferred` (blocked — say on what).
Before asking for review, check the matrix: every requirement has at least one happy and
one negative row, every invariant and every risk has a row, no two rows test the same thing.

If a slug directory already exists, read it and continue from the first missing or
out-of-date artifact. Do not regenerate approved artifacts unless the source changed.

## Traceability

Every automated test names its scenario and requirement where a reader and a script can
find them — in the docstring (Python) or the comment directly above the test (TypeScript):

```python
def test_expired_code_is_rejected(api: httpx.Client, cart: Cart) -> None:
    """Scenario: SC-002 — Expired code is rejected. Requirement: REQ-1."""
```

```typescript
// Scenario: SC-002 — Expired code is rejected. Requirement: REQ-1.
test('expired code is rejected', async ({ request, cart }) => {
```

One parametrized test may carry several ids (`Scenario: SC-005, SC-006`). A test with no
`SC-` id, an id missing from `coverage.md`, and an `auto` row with no test are all defects;
`aqa_lint.py trace` reports each of them.

## Choosing the language and the layer

| Signal in the target project | Test language |
|------------------------------|---------------|
| `pyproject.toml`, `conftest.py`, `requirements.txt` | Python |
| `package.json`, `tsconfig.json`, `playwright.config.ts` | TypeScript |
| Stated by the user or in `qa-project-context.md` | As stated |
| Python backend + JS frontend | Unit and API tests in Python, E2E in TypeScript |

Ask when there is no signal. Never mix two languages in the same test layer.

Push each case to the **lowest layer that can hold it**: a business rule is a unit test
(`unit-testing`), a contract between services is an API test, and only a journey that needs
a real browser is E2E. The `Layer` column of the matrix records the decision.

## Proving a test can fail

A test that has never been red proves nothing. For each automated test, break the behavior
it covers and confirm the test fails **for the reason the oracle names** (not on an import
error or a timeout). The product is never left changed:

1. **Local product code — mutate in a throwaway worktree.**
   `git worktree add --detach "$TMPDIR/aqa-mut" HEAD`, copy the new tests in, apply a
   minimal mutation there (flip a status code, drop a response field, invert a condition),
   run only the affected test, then `git worktree remove --force`. The working tree the
   user sees is never touched.
2. **No worktree possible** (uncommitted state the test depends on, heavy build): the working
   tree must be clean for the mutated file; mutate, run, then `git checkout -- <file>` and
   confirm `git status` shows no change in product files before doing anything else.
3. **Product not local** (remote test environment, third-party API): mutate at the boundary
   instead — intercept the response (`page.route`, `respx`) and return the broken shape, or
   seed data that violates the rule. State in `verification.md` that the check ran against a
   stub.
4. **Bug-report regression test.** The test is expected to be red now. Red on the reported
   behavior is the mutation check; record it and leave the test red.

Mutations are never committed, never left in the working tree, and never applied to a
shared or production environment. A mutation that the test survives means the oracle is too
weak — fix the test, not the mutation.

## Principles

1. **Test cases are separate from test code.** The matrix and the oracles survive a change
   of framework; the code does not.
2. **Negative and boundary cases are mandatory.** Bugs live at boundaries, in authorization
   denials and in malformed input.
3. **Contracts over spot-checks.** A Pydantic model (Python) or a Zod schema (TS) catches a
   changed type, a dropped field and an unexpected new one. `assert "id" in data` catches
   none of the three.
4. **Nothing is invented.** Every endpoint, selector, fixture and import in a test exists in
   the codebase, the spec, or the running app. Look it up (grep, the OpenAPI file, a browser
   snapshot through the Playwright MCP server) — do not guess a `data-testid`.
5. **Isolation.** Every test passes standalone and under `-n auto` / `fullyParallel`. A
   difference between those two runs is shared state, not "flakiness".
6. **Test code is production code.** Types, linting and review apply to it the same way.

## Hard prohibitions

`aqa_lint.py lint` enforces the first four mechanically.

- **No fixed waits.** `time.sleep`, `wait_for_timeout`, `waitForTimeout`. Playwright
  auto-waits; a background job gets a poll with an explicit deadline. The one legitimate
  sleep — the interval inside such a polling helper — carries `# aqa: allow-sleep <reason>`
  on the same line.
- **No retries to hide flakiness.** `--reruns`, `@pytest.mark.flaky`, `retries: N`. Fix the
  isolation, the locator, or the product. `test-reliability` uses retries as a *detection*
  signal inside a quarantine project; that line carries
  `aqa: allow-retries <ticket>` and nothing outside quarantine does.
- **No secrets in test code or logs.** Environment variables and CI secrets only.
- **No focused tests, no assertions that cannot fail.** `.only`, `assert True`,
  `expect(response).toBeTruthy()`. A test body with no assertion is the same defect.
- **The product is not changed to make a test pass.** A red test on a real bug is the
  deliverable: report the bug, keep the test.
- **No destructive tests against production.** The environment check lives in a fixture,
  not in a comment.

## Skills outside this bundle

The vendored skills mention siblings from their upstream library that are not shipped here
(`risk-based-testing`, `test-strategy`, `release-readiness`, `ai-qa-review`,
`visual-testing`, `contract-testing`, `accessibility-testing`, `ci-cd-integration`, and
others). If a skill sends you to a name that is not installed, do not stop and do not
invent its content: say that the topic is outside this bundle and continue with the skills
that are present.

## Done when

- `.agents/aqa/<slug>/` holds all six artifacts and `coverage.md` is `approved`.
- `aqa_lint.py lint` and `aqa_lint.py trace` exit 0 for the new tests.
- Each test has a recorded mutation check in `verification.md`, or a stated reason it could
  not be run.
- The suite was run once in full and once in parallel; results are in `verification.md`.
- The final message lists: tests added, bugs found (red tests kept), manual and deferred
  rows, and unresolved ambiguities.
