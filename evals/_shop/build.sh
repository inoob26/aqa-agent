#!/usr/bin/env bash
# Builds the fixture project the eval cases run against: a tiny Python shop with one
# seeded bug (a discount above 100% makes the total negative). Sourced by each case's
# fixture.sh; runs in the empty eval workspace.
set -euo pipefail

mkdir -p shop tests docs

cat > pyproject.toml <<'PY'
[project]
name = "shop"
version = "0.1.0"
requires-python = ">=3.11"

[dependency-groups]
dev = ["pytest>=8.0"]

[tool.pytest.ini_options]
testpaths = ["tests"]
PY

: > shop/__init__.py
cat > shop/discount.py <<'PY'
from dataclasses import dataclass
from datetime import date
from decimal import Decimal


class DiscountError(ValueError):
    """Raised with a machine-readable reason: 'expired' or 'below_minimum'."""


@dataclass(frozen=True)
class DiscountCode:
    code: str
    percent: int
    expires_on: date
    min_subtotal: Decimal = Decimal("0")


def apply_discount(subtotal: Decimal, code: DiscountCode, today: date) -> Decimal:
    """Return the order total after applying a percentage discount code."""
    if today > code.expires_on:
        raise DiscountError("expired")
    if subtotal < code.min_subtotal:
        raise DiscountError("below_minimum")
    return (subtotal - subtotal * code.percent / 100).quantize(Decimal("0.01"))
PY

cat > tests/conftest.py <<'PY'
from datetime import date

import pytest


@pytest.fixture
def today() -> date:
    return date(2026, 6, 15)
PY

cat > tests/test_smoke.py <<'PY'
from decimal import Decimal

from shop.discount import DiscountCode, apply_discount


def test_zero_percent_code_keeps_the_total(today):
    code = DiscountCode("NOOP", percent=0, expires_on=today)
    assert apply_discount(Decimal("50.00"), code, today) == Decimal("50.00")
PY

cat > docs/discount-story.md <<'MD'
# SHOP-42: Discount codes at checkout

As a shopper I want to apply a discount code to my order so that I pay less.

## Acceptance criteria

1. A valid code reduces the order total by the code's percentage.
2. An expired code is rejected with the reason `expired` and the total is unchanged.
3. A code with a minimum subtotal is rejected with the reason `below_minimum` when the
   order subtotal is lower than the minimum.
4. The order total is never below zero.

Implementation: `shop/discount.py`, function `apply_discount`.
MD

git init -q
git add -A
git -c user.name=fixture -c user.email=fixture@example.com commit -q -m "shop fixture"
