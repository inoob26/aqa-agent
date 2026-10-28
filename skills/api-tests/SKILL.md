---
name: api-tests
description: >-
  Write Playwright API tests in TypeScript (APIRequestContext) for the approved api-layer
  test cases in docs/qa/<slug>/. Two modes: playwright-bdd step definitions when the
  .feature files exist, else plain *.spec.ts files. Grounds every path, field and status
  code in the OpenAPI file or the router, reuses fixtures, tags every test with @TC and @REQ.
  Use when: "write the API tests," "automate the api cases," "implement TC-001..TC-010."
  Not for: deriving the cases — use test-cases first.
  Not for: browser tests — use playwright-tests.
  Related: workflow, test-cases, bdd, playwright-tests, verify.
argument-hint: "<slug | docs/qa/<slug>> [TC ids] [--openapi <path>]"
license: MIT
metadata:
  author: Nikolay Morgunov
  version: "0.1"
  category: api-testing
---

<objective>
Translate the approved api cases into Playwright API tests that look like the team wrote
them — same fixtures, same naming, same layout — with every request and every oracle taken
from the API contract, and every test traceable to its case.
</objective>

Input: $ARGUMENTS

Load the `workflow` skill of this plugin first.

## Steps

1. **Check the gate.**

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/aqa_lint.py" gate docs/qa/<slug>
   ```

   A non-zero exit means: stop and ask for the review. Do not edit the status.
2. **Select the cases.** The given TC IDs, or every row with `Layer: api` and `Automation: auto`
   that has no test yet.
3. **Choose the mode.** Look for `.feature` files with `@api` and the selected `@TC-` tags.
   Found → BDD mode (step definitions). Not found → plain mode (`*.spec.ts`). Tell the person.
4. **Check the setup.** Without `@playwright/test` (or without `playwright-bdd` in BDD mode),
   ask the person, then apply `workflow/references/scaffold.md`, or stop.
5. **Find the contract.** Use `--openapi`, else the sources in `requirements.md`, else search
   the project (`openapi.y*ml`, `swagger.json`, `contracts/`). Without a contract, read the
   router and the request validators. For each case, note: method, path, path and query
   parameters, body schema, auth scheme, response codes, response schema.
6. **Read the existing suite.** `playwright.config.ts` (projects, `baseURL`,
   `extraHTTPHeaders`), fixtures (`test.extend`), auth helpers and `storageState`, API client
   wrappers, data factories, cleanup patterns, naming, tags. Reuse them. A new helper is
   justified only when nothing existing fits.
7. **Write the tests.**
   - **Plain mode**: `tests/api/<slug>.spec.ts` (or the project path). One
     `test.describe` per REQ or area. One `test` per TC; a TC with a data table becomes a
     `for` loop over the rows with one `test` per row, each with the TC tag.
   - **BDD mode**: `tests/steps/api/<slug>.steps.ts` with `Given/When/Then` from
     `createBdd(test)` in the project fixture file. Implement every step text exactly as the
     feature uses it; reuse existing steps. Keep the response in a fixture or in the world
     object, not in a module variable.
   - Use the `request` fixture or the project API client. Paths relative to `baseURL`.
   - Assert the status first, then the body: `expect(res.status()).toBe(202)`, then fields
     with `toMatchObject` / `toEqual`. If the project has a schema validator (Ajv, Zod), check
     the body against the OpenAPI schema; do not add a validator without approval.
   - Create the test data through the API or the project factories in the test or in a
     fixture; delete it after. Use unique values (`crypto.randomUUID()`), so that tests can
     run in parallel.
   - Read credentials and tokens from env vars or the auth fixture.
   - Tag every test: `{ tag: ['@TC-NNN', '@REQ-N', '@api', '@P1'] }`; in BDD mode the tags
     come from the feature file.
8. **Mark what you cannot ground.** An endpoint or field that is not in the contract or the
   code, or a missing way to create the data → set the row to `deferred` in `coverage.md`
   with the reason. Do not invent it.
9. **Static pass.**

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/aqa_lint.py" lint <test paths>
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/aqa_lint.py" trace docs/qa/<slug> <test paths> --layer api
   npx tsc --noEmit
   ```

   Also run the project's linter (`eslint`) on the new files if it has one.
10. **Run the new tests once.** `npx playwright test <files> --project=<api project>`, or in
    BDD mode `npx bddgen && npx playwright test --grep "@TC-001|@TC-002"`. A failure is a
    defect in the test (fix it) or a defect in the product (keep the test red, write the
    defect in the `Notes` column). Never change the product.
11. **Record and hand over.** Put the test file in the `Test` column of `coverage.md`.
    Tell the person to run `/aqa-agent:verify <slug>`.

## Done when

- Every selected `auto` api row has a test, or is `deferred` with a reason.
- `aqa_lint.py lint`, `aqa_lint.py trace --layer api` and `tsc --noEmit` exit 0.
- The new tests ran once; each failure has a classification in `coverage.md`.
- No file outside the test tree, the scaffold files (if approved) and `docs/qa/<slug>/`
  was modified.
