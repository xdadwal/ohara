#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
python3 "$ROOT_DIR/tests/smoke.py"
python3 "$ROOT_DIR/tests/smoke_bambuddy_widget.py"
python3 "$ROOT_DIR/tests/smoke_adguard.py"
python3 "$ROOT_DIR/tests/smoke_maintainerr.py"
exec python3 "$ROOT_DIR/tests/smoke_lan_proxy.py"
