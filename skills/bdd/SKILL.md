---
name: bdd
description: >-
  Write Gherkin .feature files for playwright-bdd from approved test cases in
  docs/qa/<slug>/: checks the review gate, reuses the step texts that the suite already
  has, and tags each scenario with @TC, @REQ, layer and priority. Writes no step code;
  api-tests and playwright-tests write the steps later.
  Use when: "write BDD scenarios," "Gherkin from the test cases," "feature files for <slug>."
  Not for: deriving the cases — use test-cases first.
  Not for: step definitions — use api-tests or playwright-tests.
  Related: workflow, test-cases, api-tests, playwright-tests, verify.
argument-hint: "<slug | docs/qa/<slug>> [TC ids]"
license: MIT
metadata:
  author: Nikolay Morgunov
  version: "0.1"
  category: bdd
---

<objective>
Write feature files that a product owner can read and that the existing step library can
run: business language, one scenario per test case, and step texts that match steps the
suite already defines wherever possible.
</objective>

Input: $ARGUMENTS

Load the `workflow` skill of this plugin first.

## Steps

1. **Check the gate.**

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/aqa_lint.py" gate docs/qa/<slug>
   ```

   A non-zero exit means: stop and ask for the review. Do not edit the status.
2. **Select the cases.** Read `test-cases.md` and `coverage.md`. Take the given TC IDs, or
   every `api` and `ui` row that is `auto` or `manual`. Skip `unit`, `deferred` and `removed`.
3. **Read the existing BDD setup.** Find `defineBddConfig` in `playwright.config.ts`, the
   `features` and `steps` globs, existing `.feature` files, and every `Given`/`When`/`Then`
   in the step files. Make a list of the existing step texts and their parameters
   (`{string}`, `{int}`). If no `playwright-bdd` setup exists, tell the person; the files
   are still useful, and the api-tests or playwright-tests command will offer the scaffold.
4. **Write the feature files.** Default path: `tests/features/<slug>/<area>.feature`, one
   file per functional area or per layer. Rules:
   - The `Feature:` text names the capability; a short description line names the slug.
   - Tags on each scenario: `@TC-NNN @REQ-N @api|@ui @P0..P3`; add `@manual` for manual rows.
   - One `Scenario` per TC. Use a `Scenario Outline` with `Examples` for a TC with a test
     data table (EP, BVA, pairwise, decision table). The table columns are the TC columns.
   - `Background` only for preconditions that every scenario in the file shares.
   - Business language: "the user requests a password reset for {string}", not
     "POST /auth/password-reset". Keep the HTTP details for the steps.
   - Reuse an existing step text exactly when the meaning is equal. A new step text must be
     generic enough to reuse, with parameters for values.
   - `Then` steps state the oracle of the TC; one `Then` per `Expected` item, joined with `And`.
5. **Record the result.** In `coverage.md`, put the `.feature` path in the `Test` column of
   each written TC. Add a list `New steps to implement` at the end of the report to the
   person, grouped by layer.
6. **Static pass.**

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/aqa_lint.py" lint tests/features/<slug>
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/aqa_lint.py" trace docs/qa/<slug> tests/features/<slug>
   ```

   If `playwright-bdd` is installed, also run `npx bddgen` and report the missing steps
   (that is expected until the steps exist).

## Done when

- Every selected TC has one scenario with its `@TC` and `@REQ` tags.
- `aqa_lint.py lint` and `aqa_lint.py trace` exit 0.
- The person has the list of new step texts per layer.
- No file outside `tests/features/` and `docs/qa/<slug>/` was modified.
