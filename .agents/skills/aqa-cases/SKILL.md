---
name: aqa-cases
description: >-
  Derive test cases from a task description and stop for review: writes requirements,
  risks, the coverage matrix, scenarios and oracles to .agents/aqa/<slug>/ and produces no
  test code. Input is a file path, pasted text, a ticket reference, a diff range or an
  OpenAPI file.
  Use when: "test cases for this ticket," "coverage matrix for this story," "what should we
  test here," "don't write code yet," or as the first step before aqa-generate.
  Not for: writing the test code — use aqa-generate after the matrix is approved.
  Not for: a sprint or release plan — use test-planning.
  Related: aqa-workflow, ai-test-generation, aqa-generate, qa-project-context.
argument-hint: "<file | ticket | diff range | OpenAPI path> [slug]"
license: MIT
metadata:
  author: initk.tech
  version: "1.0"
  category: workflow
---

<objective>
Turn one task description into reviewable test cases on disk. The deliverable is the
coverage matrix a human can approve or correct in five minutes — not test code.
</objective>

Rules and file formats are in `aqa-workflow`; the extraction and scenario techniques are in
`ai-test-generation` (Steps 1–5). Load both before starting.

## Steps

1. **Resolve the input.** Read it from where it lives instead of asking the user to paste it:

   | Input | How to read it |
   |-------|----------------|
   | File (PRD, story, OpenAPI) | Read the file |
   | GitHub issue or PR | `gh issue view <n> --comments` / `gh pr view <n>` and `gh pr diff <n>` |
   | Diff | `git diff <base>...HEAD` (default base: the repository's main branch) |
   | Jira / Linear ticket | The tracker's MCP server if one is connected; otherwise ask for the text |
   | Bug report | The report text plus the code path it names |

2. **Pick the slug** — the ticket id or a kebab-case feature name — and open
   `.agents/aqa/<slug>/`. If it exists, continue from the first missing artifact.
3. **Read the project.** `.agents/qa-project-context.md`, then the code the task touches:
   routes, handlers, models, existing tests and fixtures. Requirements are extracted from
   the task; *what exists* is read from the code.
4. **Write `requirements.md`.** `REQ-N` for what the source states, `IMP-N` for what you
   inferred, and a list of open ambiguities phrased as questions.
5. **Write `risks.md`.** Risks, invariants (`INV-N`), edge cases.
6. **Write `coverage.md`** in the format from `aqa-workflow`, with `status: draft`. Choose
   the layer per row: the lowest one that can hold the case.
7. **Write `scenarios.md`, then `oracles.md`** — in that order, as separate passes.
8. **Self-check the matrix:** happy + negative per requirement, a row per invariant and per
   risk, no duplicates, no row whose oracle is "works correctly".
9. **Stop and report.** Show the matrix, the open ambiguities and the count by layer and
   priority. Ask for approval or corrections. Do not write test code.

## Done when

- The five files exist under `.agents/aqa/<slug>/` and `coverage.md` has `status: draft`.
- Every ambiguity is listed as a question for the human, none was silently decided.
- The reply ends with the request to review the matrix — and no test file was created.
