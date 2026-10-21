# Requirements: <slug>

## Sources

| ID | Type | Location | Note |
|---|---|---|---|
| S1 | task | prompt text | "<quoted task text>" |
| S2 | openspec | openspec/changes/<change>/specs/<cap>/spec.md | |
| S3 | adr | docs/adr/0007-<title>.md | status: accepted |
| S4 | openapi | api/openapi.yaml | version 1.4.0 |

## Requirements

### REQ-1: <one testable statement>
- Source: S2 "Requirement: <name>" / Scenario "<name>"
- Kind: functional
- Notes:

### REQ-2: <one testable statement>
- Source: S4 POST /auth/password-reset, responses 202, 400, 429
- Kind: functional
- Notes:

### REQ-3: <constraint from the ADR>
- Source: S3 "Decision", item 2
- Kind: constraint
- Notes: Applies to REQ-1 and REQ-2.
