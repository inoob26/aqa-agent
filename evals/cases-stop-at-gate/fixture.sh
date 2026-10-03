#!/usr/bin/env bash
set -euo pipefail
SHOP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../_shop" && pwd)"
source "$SHOP_DIR/build.sh"
