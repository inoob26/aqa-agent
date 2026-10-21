---
slug: <slug>
status: draft
approved_by:
approved_at:
generated_at: <YYYY-MM-DD>
sources: S1, S2, S3, S4
---

# Test cases: <slug>

## Summary

| Layer | P0 | P1 | P2 | P3 |
|---|---|---|---|---|
| api | 0 | 0 | 0 | 0 |
| ui | 0 | 0 | 0 | 0 |
| unit | 0 | 0 | 0 | 0 |

## Cases

### TC-001: <short title in the present tense>
- Requirement: REQ-1, REQ-3
- Priority: P0
- Layer: api
- Technique: happy-path
- Preconditions: User "reset.user@example.test" exists and is active.
- Test data: email = "reset.user@example.test"
- Steps:
  1. Send POST /auth/password-reset with body {"email": "reset.user@example.test"}.
- Expected:
  - The status is 202.
  - The body matches schema PasswordResetAccepted.

### TC-002: <boundary case>
- Requirement: REQ-2, REQ-3
- Priority: P1
- Layer: api
- Technique: BVA, negative
- Preconditions: None.
- Test data:
  | email length | valid |
  |---|---|
  | 254 | yes |
  | 255 | no |
- Steps:
  1. Send POST /auth/password-reset with an email of the given length.
- Expected:
  - Valid length: the status is 202.
  - Invalid length: the status is 400 and error.code is "EMAIL_TOO_LONG".
