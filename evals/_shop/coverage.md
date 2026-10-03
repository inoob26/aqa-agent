---
slug: discount-codes
source: docs/discount-story.md
status: STATUS
approved_by: APPROVER
---

| ID | Requirement | Scenario | Category | Priority | Layer | Oracle | Automation |
|----|-------------|----------|----------|----------|-------|--------|------------|
| SC-001 | REQ-1 | A 10% code on 200.00 gives 180.00 | Happy path | P0 | Unit | Data: total == 180.00 | auto |
| SC-002 | REQ-2 | A code used the day after it expires is rejected | Negative | P0 | Unit | DiscountError with reason `expired` | auto |
| SC-003 | REQ-3 | Subtotal below the code's minimum is rejected | Negative | P0 | Unit | DiscountError with reason `below_minimum` | auto |
| SC-004 | REQ-3 | Subtotal equal to the minimum is accepted | Boundary | P1 | Unit | Data: discounted total returned | auto |
