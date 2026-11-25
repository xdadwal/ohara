#!/usr/bin/env bash
# Lint and format-check Python with the pinned ruff (ruff.toml, requirements-dev.txt).
# Pass --fix to apply safe fixes and reformat instead of only checking.
set -euo pipefail
ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
if [[ -x .venv/bin/ruff ]]; then
  RUFF=.venv/bin/ruff
elif command -v ruff >/dev/null 2>&1; then
  RUFF=ruff
else
  echo 'ruff missing; run: python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt' >&2
  exit 1
fi
if [[ "${1:-}" == --fix ]]; then
  "$RUFF" check --fix .
  "$RUFF" format .
else
  "$RUFF" check .
  "$RUFF" format --check .
fi
