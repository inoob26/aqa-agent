# How to read each input type

Record every input in the `## Sources` table of `requirements.md` with an ID (`S1`, `S2`…).
Every `REQ-N` names its source ID and the exact section.

## Task (free text)

- Split the text into single statements. One statement with "and" is often two REQs.
- A task text is usually incomplete. Each missing rule (limits, roles, errors, empty states)
  goes to `questions.md`; do not fill it with a guess.
- Look in the project for the code or docs that the task names (routes, components, models)
  and add them as extra sources when they confirm a rule.

## OpenSpec

Layout:

```
openspec/specs/<capability>/spec.md              # the current behavior
openspec/changes/<change-id>/proposal.md         # why and what
openspec/changes/<change-id>/design.md           # optional technical decisions
openspec/changes/<change-id>/tasks.md
openspec/changes/<change-id>/specs/<capability>/spec.md   # the delta
```

- In a delta, read `## ADDED Requirements`, `## MODIFIED Requirements`,
  `## REMOVED Requirements`, `## RENAMED Requirements`.
- Each `### Requirement: <name>` (SHALL / MUST text) becomes one or more REQs.
- Each `#### Scenario: <name>` with `- **WHEN**` / `- **THEN**` is a ready oracle: keep it as
  at least one TC, and add the negative and boundary cases that the scenario does not list.
- For a MODIFIED requirement, also read the old text in `openspec/specs/` and add a
  regression TC for the old behavior that must not change.
- For a REMOVED requirement, add a TC that proves the old behavior is gone, if it is observable.
- The slug is the `<change-id>`.

## Spec Kit

Layout: `specs/<NNN-feature>/spec.md`, plus optional `plan.md`, `data-model.md`,
`research.md`, `quickstart.md`, `contracts/` (often OpenAPI), `tasks.md`.

- `FR-NNN: System MUST …` lines → REQs. Keep the FR ID in the Source column.
- `SC-NNN` success criteria → REQs of kind `non-functional` when they are measurable.
- `User Story N (Priority: P1)` → the story priority is a start value for TC priority.
- `Acceptance Scenarios` (Given/When/Then) → TCs as they are written.
- `Edge Cases` → negative and boundary TCs.
- `[NEEDS CLARIFICATION: …]` → copy each one to `questions.md`.
- `data-model.md` → field limits, required fields, state fields (input for BVA and state
  transitions). `contracts/` → read as OpenAPI.
- The slug is `<NNN-feature>` without the number.

## ADR (Nygard or MADR format)

- Read `Status` first. `superseded` or `deprecated` → do not use; record it in Sources with
  a note. `proposed` → use, and add a question that asks if it is final.
- `Decision` and `Consequences` give constraints: protocols, limits, timeouts, retry rules,
  auth, data retention, error formats. Each testable constraint is a REQ of kind `constraint`.
- `Context` and rejected options are not requirements.
- An ADR seldom gives the full behavior; link its REQs to the functional REQs that they
  constrain (Notes field).

## OpenAPI (3.x, or Swagger 2.0)

For each operation in scope (`paths.<path>.<method>`):

- `responses` → one REQ for each documented status code with its meaning.
- `requestBody` and `parameters` schemas → EP and BVA inputs: `required`, `type`, `enum`,
  `minLength`/`maxLength`, `minimum`/`maximum`, `exclusiveMinimum`, `pattern`, `format`,
  `nullable`, `additionalProperties: false`.
- `security` and `securitySchemes` → auth TCs: no token (401), wrong scope or role (403).
- Response schemas → oracles: the body must match the schema of the documented status.
- Undocumented behavior that a client needs (for example, a missing 404 for an unknown ID)
  → `questions.md`.
- Use the `operationId` in the Source column.

## Many inputs at once

- Process all inputs before you write REQs. Merge equal statements into one REQ with all
  sources listed.
- A conflict between sources (for example, the ADR says 5 per minute, OpenAPI says 10) goes
  to `questions.md`. The TCs that depend on it get `deferred` with the question ID.
- Precedence when the person gives no rule: an accepted ADR and an approved spec win over a
  task text; OpenAPI wins for wire details (paths, codes, field names).
