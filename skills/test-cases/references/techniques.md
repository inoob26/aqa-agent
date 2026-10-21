# Test design techniques

Apply each technique where it fits; do not force all of them on every REQ. Put the names
of the applied techniques in the `Technique` field.

## Equivalence partitions (EP)

1. For each input, list the valid partitions and the invalid partitions.
2. One TC per valid partition is enough; valid partitions can share one TC.
3. One TC per invalid partition, **one invalid input per TC**, so that a failure has one cause.

Example: `quantity` integer 1–99 → valid {1–99}; invalid {≤0}, {≥100}, {not an integer}, {missing}.

## Boundary value analysis (BVA)

For each ordered range use min−1, min, max, max+1 (two-value BVA). Add min+1 and max−1
for P0 rules (three-value BVA). Put the values in one parametrized TC with a `Test data`
table. Apply BVA to lengths, counts, dates, amounts, page sizes and rate limits.

## Negative and error paths

Check each item for each operation in scope:

- Required field missing; field `null`; wrong type; empty string; whitespace only.
- Unknown field when `additionalProperties: false`.
- Auth: no credentials (401), expired token (401), valid user without permission (403),
  access to another user's resource (403 or 404 — the spec must say which).
- Not found (404); conflict or duplicate (409); precondition failed (412 or 422).
- Rate limit (429) if a limit is documented.
- The error body format (code, message, field) as the spec or ADR defines it.
- UI: inline validation text, the disabled submit button, the error banner, the focus on the
  first invalid field, no data loss after an error.

Do not create TCs for undocumented server failures (500); add a question if the spec is silent.

## State transitions

1. Draw the states and the allowed events from the spec (or `data-model.md`).
2. One TC for each **allowed** transition (0-switch coverage).
3. One TC for each **forbidden** transition that a client can try (for example: refund a draft).
4. For P0 flows, one TC for each pair of transitions in sequence (1-switch) when the order matters.

Write the state table in the TC `Test data` field:

| from | event | to / result |
|---|---|---|
| draft | submit | pending |
| paid | submit | 409 INVALID_STATE |

## Decision tables

Use them when an outcome depends on 2–4 boolean conditions. List all combinations,
merge columns with the same outcome, and make one TC per remaining column.

| Condition / Rule | R1 | R2 | R3 |
|---|---|---|---|
| user is admin | Y | N | N |
| resource is owned | – | Y | N |
| **Result** | allow | allow | 403 |

## Pairwise

Use it when 4 or more parameters each have 2 or more values and the full product is too
large (more than about 20 rows). Generate an all-pairs set by hand or with a tool the project
has; put the rows in the `Test data` table and keep every constraint (invalid pairs out).
Always add the combinations that a REQ names explicitly.

## Priority guide

| Priority | Use for |
|---|---|
| P0 | the main success path of a core flow, security and auth rules, data loss, money |
| P1 | main negative paths, boundaries of business limits, allowed state transitions |
| P2 | rare inputs, forbidden transitions with low risk, secondary UI messages |
| P3 | cosmetic text, layout details |

## Automation guide (coverage.md)

- `auto`: the oracle is observable through the API or the DOM, and the setup data can be made
  through an API, a seed script, or a fixture in the suite.
- `manual`: visual judgement, a real email or SMS inbox without a test API, hardware, or a
  one-time check. Give the reason.
- `deferred`: blocked by an open question, a missing `data-testid`, a missing seed endpoint,
  or an environment that does not exist yet. Give the reason and the question ID.
