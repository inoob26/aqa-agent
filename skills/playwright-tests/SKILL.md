---
name: playwright-tests
description: >-
  Write Playwright UI (end-to-end) tests in TypeScript for the approved ui-layer test cases
  in .agents/aqa/<slug>/. Two modes: playwright-bdd step definitions when the .feature files
  exist, else plain *.spec.ts files. Takes selectors from the component source or a live page
  snapshot (Playwright MCP), reuses page objects and fixtures, tags each test with @TC and @REQ.
  Use when: "write the e2e tests," "automate the ui cases," "Playwright tests for <slug>."
  Not for: deriving the cases — use test-cases first.
  Not for: API-only checks — use api-tests.
  Related: workflow, test-cases, bdd, api-tests, verify.
argument-hint: "<slug | .agents/aqa/<slug>> [TC ids] [--url <base url>]"
license: MIT
metadata:
  author: Nikolay Morgunov
  version: "0.1"
  category: e2e-testing
---

<objective>
Translate the approved ui cases into stable Playwright tests: user-facing locators taken
from the real page, page objects that the suite already uses, setup through the API instead
of the UI, and a traceable tag on every test.
</objective>

Input: $ARGUMENTS

Load the `workflow` skill of this plugin first.

## Steps

1. **Check the gate.**

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/aqa_lint.py" gate .agents/aqa/<slug>
   ```

   A non-zero exit means: stop and ask for the review. Do not edit the status.
2. **Select the cases.** The given TC IDs, or every row with `Layer: ui` and `Automation: auto`
   that has no test yet.
3. **Choose the mode.** `.feature` files with `@ui` and the selected `@TC-` tags → BDD mode
   (`tests/steps/ui/<slug>.steps.ts`). Else plain mode (`tests/e2e/<slug>.spec.ts`). Tell the
   person.
4. **Check the setup.** Without `@playwright/test` (or `playwright-bdd` in BDD mode), ask the
   person, then apply `workflow/references/scaffold.md`, or stop.
5. **Read the existing suite.** Config (projects, `baseURL`, `storageState`, global setup),
   page objects, fixtures, auth setup, data factories, naming. Reuse them.
6. **Ground the selectors.** For each page in the cases, use these sources in this order:
   1. The component source: roles, labels, `data-testid` values, visible texts.
   2. A live page through the Playwright MCP server: `browser_navigate` to the page, then
      `browser_snapshot` for the accessibility tree. Use `--url`, else `baseURL` from the
      config. Log in through the same path as the suite's auth setup.
   3. `npx playwright codegen <url>` — ask the person to run it if no MCP server is available.

   Locator priority: `getByRole` with name → `getByLabel` → `getByPlaceholder` → `getByText`
   → `getByTestId`. Never use CSS chains on generated class names, XPath, or `nth()` without a
   reason. A needed element without a stable locator → row `deferred` with the reason
   "needs data-testid on <element> in <file>". Do not change the component.
7. **Write the tests.**
   - Page objects in `tests/pages/<name>.page.ts` when the suite uses them: locators as
     readonly fields, actions as methods, no assertions inside except a `waitFor` of the page.
   - **Plain mode**: one `test` per TC, a parametrized TC as a `for` loop with one `test` per
     row; `test.step` for each TC step, with the step text from `test-cases.md`.
   - **BDD mode**: implement each `@ui` step text exactly as the feature file has it; reuse
     existing steps; keep state in fixtures.
   - Setup through the API or the fixtures (create a user, seed data, log in with
     `storageState`); use the UI only for the behavior under test.
   - Web-first assertions only: `toBeVisible`, `toHaveText`, `toHaveURL`, `toBeDisabled`.
     No `waitForTimeout`, no `page.$`.
   - Unique data per test, so that tests can run in parallel. Credentials from env vars.
   - Tag every test: `{ tag: ['@TC-NNN', '@REQ-N', '@ui', '@P0'] }`; in BDD mode the tags
     come from the feature file.
8. **Static pass.**

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/aqa_lint.py" lint <test paths>
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/aqa_lint.py" trace .agents/aqa/<slug> <test paths> --layer ui
   npx tsc --noEmit
   ```

   Also run the project's linter on the new files.
9. **Run the new tests once** in the e2e project (in BDD mode run `npx bddgen` first). A failure
   is a defect in the test (fix it; use the trace and the MCP snapshot) or a defect in the
   product (keep the test red, write it in `Notes`). Never change the product. Run a passed
   test 3 times with `--repeat-each=3` to catch flakiness.
10. **Record and hand over.** Put the file in the `Test` column of `coverage.md`. Tell the
    person to run `/aqa-agent:verify <slug>`.

## Done when

- Every selected `auto` ui row has a test, or is `deferred` with a reason.
- `aqa_lint.py lint`, `aqa_lint.py trace --layer ui` and `tsc --noEmit` exit 0.
- The new tests ran; each failure has a classification; no test is flaky in 3 runs.
- No file outside the test tree, the scaffold files (if approved) and `.agents/aqa/<slug>/`
  was modified.
