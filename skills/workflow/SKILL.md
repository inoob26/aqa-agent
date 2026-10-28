---
name: workflow
description: >-
  Shared rules for every aqa-agent command: the artifact folder docs/qa/<slug>/, the
  file formats (requirements.md, test-cases.md, coverage.md, questions.md), the review gate,
  the ID and traceability rules, the test layout, and the lint script.
  Load it before any other aqa-agent skill does work.
  Not for: direct use by a person — run /aqa-agent:test-cases, :bdd, :api-tests,
  :playwright-tests or :verify.
user-invocable: false
license: MIT
metadata:
  author: Nikolay Morgunov
  version: "0.1"
  category: workflow
---

<objective>
One set of rules, so that every command reads and writes the same artifacts, and a script
can trace each test back to a test case and each test case back to a requirement.
</objective>

## Pipeline

```
task / spec / ADR / OpenAPI
        │  /aqa-agent:test-cases
        ▼
docs/qa/<slug>/   status: draft ──(person sets approved)──▶ status: approved
        │                                                          │
        │            ┌─────────────────────────────────────────────┤
        │            ▼                    ▼                        ▼
        │   /aqa-agent:bdd      /aqa-agent:api-tests     /aqa-agent:playwright-tests
        │   tests/features/     tests/api/ or            tests/e2e/ or
        │                       tests/steps/api/         tests/steps/ui/
        │                                                          │
        └──────────────────────────▶ /aqa-agent:verify ◀───────────┘
                                     report.md
```

## Artifact folder

Everything for one feature lives in `docs/qa/<slug>/` in the target project:

| File | Written by | Content |
|---|---|---|
| `requirements.md` | test-cases | `REQ-N` items, each with its source |
| `test-cases.md` | test-cases | front matter with `status`, then `TC-NNN` blocks |
| `coverage.md` | test-cases, then each generator | one row per TC: automation state and test file |
| `questions.md` | test-cases | gaps and conflicts found in the inputs |
| `report.md` | verify | run results and mutation results per TC and REQ |

Templates are in `templates/` next to this file. Copy their structure exactly: the lint
script parses it.

**Slug**: kebab-case, 3–40 characters. Take it from the OpenSpec change name, the Spec Kit
feature folder, the ADR file name, or the main words of the task text. A `--slug <name>`
argument wins.

## IDs

- `REQ-N` — a single, testable statement. Number from 1, never reuse a number.
- `TC-NNN` — three digits minimum (`TC-001`). Never renumber after the first `approved`;
  a removed case keeps its ID and gets `removed` in the `coverage.md` Automation column.
- One TC can cover more than one REQ. Every REQ must have at least one TC.

## Test case fields

Each `### TC-NNN: <title>` block in `test-cases.md` has exactly these fields:

| Field | Values |
|---|---|
| Requirement | `REQ-1` or `REQ-1, REQ-4` |
| Priority | `P0` (blocker, core path) · `P1` (major) · `P2` (minor) · `P3` (cosmetic) |
| Layer | `api` · `ui` · `unit` |
| Technique | one or more of `happy-path`, `EP`, `BVA`, `negative`, `state-transition`, `decision-table`, `pairwise`, `error-guessing` |
| Preconditions | the start state, concrete |
| Test data | exact values, or a table for parametrized cases |
| Steps | numbered list |
| Expected | bullet list of observable oracles (status code, body field, UI text, DB state) |

Choose the **lowest layer** that can observe the oracle: `unit` before `api` before `ui`.
A `ui` case must need the browser (rendering, navigation, client-side validation, a flow
across pages). The plugin does not generate `unit` tests; those rows are for developers.

## coverage.md

One table row per TC:

```
| TC | Requirement | Layer | Priority | Automation | Test | Notes |
```

- **Automation**: `auto` (a command must write a test) · `manual` (a person runs it; say why
  in Notes) · `deferred` (cannot be automated now; the reason in Notes is required) ·
  `removed` (kept for history).
- **Test**: the file that contains the test, relative to the project root; empty until a
  generator writes it. A BDD scenario and its spec can share one row: put the `.feature` path.
- Requirement, Layer and Priority must match `test-cases.md`.

## Review gate

`test-cases.md` front matter holds `status: draft | approved`. Only a person changes it to
`approved` (and fills `approved_by`, `approved_at`). A command never edits `status`, except
that `/aqa-agent:test-cases` writes `draft` when it creates or regenerates the file.

Every generator starts with:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/aqa_lint.py" gate docs/qa/<slug>
```

A non-zero exit means: stop, show the message, ask for the review.

**Lint script location.** If `CLAUDE_PLUGIN_ROOT` is empty in the shell, the script is
`../../scripts/aqa_lint.py` relative to this `SKILL.md`. This is the case in pi, which does
not set `CLAUDE_PLUGIN_ROOT`. In pi, the commands are `/skill:test-cases`, `/skill:bdd`,
`/skill:api-tests`, `/skill:playwright-tests` and `/skill:verify`. Commands of the script:

| Command | Checks |
|---|---|
| `gate <dir>` | `status: approved` |
| `cases <dir>` | structure, fields, values, REQ and TC links, coverage rows |
| `trace <dir> <paths…> [--layer api\|ui]` | every `auto` row of the layer has a tagged test; every tag in the code is a known TC; each test also names its REQ |
| `lint <paths…>` | forbidden patterns in specs, steps and features |
| `report <dir> --results <json> [--mutations <json>]` | writes `report.md` from a Playwright JSON report |

In BDD mode, give `trace` the `.feature` files and the step files: the tags are in the features.

## Traceability in code

Every test carries its TC and REQ IDs as Playwright tags, so `--grep @TC-001` selects it
and the JSON report names it.

```ts
test('TC-004 rejects an expired reset token', {
  tag: ['@TC-004', '@REQ-2', '@api', '@P1'],
}, async ({ request }) => { /* ... */ });
```

```gherkin
@TC-004 @REQ-2 @api @P1
Scenario: Expired reset token is rejected
```

A parametrized test that covers several TCs carries all their tags.

## Test layout

Use the layout that the project has. Read `playwright.config.ts` (`testDir`, `projects`,
`defineBddConfig`) and the existing test folders first. If the project has no tests, use:

```
tests/
  features/<slug>/*.feature    # bdd
  steps/api/<slug>.steps.ts    # api-tests, BDD mode
  steps/ui/<slug>.steps.ts     # playwright-tests, BDD mode
  api/<slug>.spec.ts           # api-tests, plain mode
  e2e/<slug>.spec.ts           # playwright-tests, plain mode
  pages/*.page.ts              # page objects
  fixtures/*.ts                # test.extend fixtures, auth, data factories
```

**Two modes for the generators.** If `.feature` files with the slug's `@TC-` tags for the
layer exist, write playwright-bdd step definitions for them (BDD mode). If not, write plain
`*.spec.ts` files from `test-cases.md` (plain mode). Tell the person which mode you use.

**No Playwright setup.** If the project has no `@playwright/test` (or no `playwright-bdd`
for BDD mode), ask the person. On "yes", apply `references/scaffold.md`. On "no", stop.

## Hard rules

- Ground every endpoint, field, selector and fixture in a real source: the OpenAPI file, the
  router, the component source, a live page snapshot, or the existing suite. Never invent one.
  If a source is missing, mark the row `deferred` and say what is missing.
- Never change product code. A test that fails because of a product defect stays red;
  record the defect in `coverage.md` Notes.
- Never add a dependency without the person's approval.
- Only write in the test tree, `playwright.config.ts` (scaffold only), and `docs/qa/<slug>/`.
- No `waitForTimeout`, no `.only`, no hard-coded secrets: read credentials from env vars.
- Web-first assertions only (`await expect(locator).toBeVisible()`), no manual polling.
