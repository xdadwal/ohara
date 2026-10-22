#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
python3 "$ROOT_DIR/tests/smoke.py"
exec python3 "$ROOT_DIR/tests/smoke_adguard.py"
