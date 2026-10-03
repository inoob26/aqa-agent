#!/usr/bin/env bash
# Adds test-case artifacts for the slug `discount-codes` to the fixture project.
# Usage: source artifacts.sh <draft|approved>
set -euo pipefail
status="$1"
approver=""
[ "$status" = approved ] && approver="reviewer@example.com"
dir=.agents/aqa/discount-codes
mkdir -p "$dir"
sed -e "s/STATUS/$status/" -e "s/APPROVER/$approver/" "$SHOP_DIR/coverage.md" > "$dir/coverage.md"

cat > "$dir/scenarios.md" <<'MD'
# Scenarios

- **SC-001** Given a code with percent=10 that expires today and a subtotal of 200.00;
  when the discount is applied today; then the total is 180.00.
- **SC-002** Given a code that expired yesterday; when it is applied today; then it is rejected.
- **SC-003** Given a code with min_subtotal=100.00 and a subtotal of 99.99; when it is
  applied; then it is rejected.
- **SC-004** Given a code with min_subtotal=100.00 and a subtotal of 100.00; when a 10%
  code is applied; then the total is 90.00.
MD

cat > "$dir/oracles.md" <<'MD'
# Oracles

- **SC-001** Return value equals Decimal("180.00").
- **SC-002** `DiscountError` is raised and its message is exactly `expired`.
- **SC-003** `DiscountError` is raised and its message is exactly `below_minimum`.
- **SC-004** Return value equals Decimal("90.00"); no exception.
MD

git add -A
git -c user.name=fixture -c user.email=fixture@example.com commit -q -m "test cases: $status"
