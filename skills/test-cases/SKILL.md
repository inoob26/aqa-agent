---
name: test-cases
description: >-
  Derive requirements and test cases from a task text, an OpenSpec or Spec Kit spec, an ADR,
  an OpenAPI file, or any mix of them. Writes docs/qa/<slug>/ (requirements.md,
  test-cases.md, coverage.md, questions.md) with status draft for a person to review.
  Applies EP, BVA, negative paths, state transitions, decision tables and pairwise.
  Use when: "write test cases for…," "what must we test for this spec/ADR/endpoint,"
  "test design for openspec change X," before any test code exists.
  Not for: test code — use bdd, api-tests or playwright-tests after the review.
  Related: workflow, bdd, api-tests, playwright-tests, verify.
argument-hint: "<task text | path…> [--slug <name>]"
license: MIT
metadata:
  author: Nikolay Morgunov
  version: "0.1"
  category: test-design
---

<objective>
Turn the inputs into a small set of numbered, testable requirements and a set of test cases
that a reviewer can approve in one pass: every case traces to a requirement, every oracle is
concrete, and every gap is a written question, not a silent guess.
</objective>

Input: $ARGUMENTS

Load the `workflow` skill of this plugin first. Read `references/inputs.md` for the input
formats and `references/techniques.md` for the design techniques.

## Steps

1. **Classify the inputs.** Each argument is a path (file or folder) or free text. For a
   folder, detect the type: `openspec/changes/<id>/` → OpenSpec change; `specs/<NNN-name>/`
   with `spec.md` → Spec Kit; `docs/adr/` or a file with `Status` + `Decision` → ADR;
   a YAML or JSON file with `openapi:` or `swagger:` → OpenAPI. The remaining text is a task.
   If an argument is neither an existing path nor clear text, ask the person.
2. **Fix the slug and the folder.** Derive the slug (rules in `workflow`). If
   `docs/qa/<slug>/test-cases.md` exists, read it and ask the person: regenerate (the
   status goes back to `draft`, existing TC IDs stay), add cases only, or stop.
3. **Read the sources and the project.** Read every input in full. Then look for the code
   and docs that the inputs name: routes or controllers, UI components, models, an OpenAPI
   file that the spec does not name. Note what exists and what does not.
4. **Write `requirements.md`.** One `REQ-N` per testable statement, with the source ID and
   section. Merge duplicates across sources. Put each conflict and each gap in
   `questions.md` with `Q-N`.
5. **Design the cases.** For each REQ, apply the techniques that fit: happy path, EP, BVA,
   negative and error paths, state transitions, decision tables, pairwise. Choose the lowest
   layer that observes the oracle. Make every `Expected` item observable: a status code, a
   body field, a visible text, a URL, a stored state. Use exact test data.
6. **Write `test-cases.md`** from the template, with `status: draft` and the summary table.
   Group the cases under `## <REQ title>` headings if there are more than 15 cases.
7. **Write `coverage.md`.** One row per TC with `auto`, `manual` or `deferred` and a reason
   for the last two. Leave `Test` empty. Fill the requirement coverage table.
8. **Check the structure.**

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/aqa_lint.py" cases docs/qa/<slug>
   ```

   Fix every error before you continue.
9. **Report to the person**: the number of REQs, the TCs per layer and priority, the number
   of `deferred` rows, and the open questions in a short list. Ask the person to answer the
   questions, review the cases, and set `status: approved` in `test-cases.md`.

## Quality bar

- No TC without a REQ; no REQ without a TC.
- One cause of failure per negative TC.
- No vague oracle such as "works correctly", "shows an error", "is fast". Write the exact
  code, text, or limit, or write a question.
- No case for behavior that no source states. Put it in `questions.md`.
- No more cases than the risk needs: merge partitions, use one parametrized case for a BVA set.

## Done when

- The four files exist in `docs/qa/<slug>/` and `aqa_lint.py cases` exits 0.
- `status` is `draft`.
- Every gap and conflict is in `questions.md`, and each dependent TC is `deferred` with the `Q-N`.
- No file outside `docs/qa/<slug>/` was modified.
