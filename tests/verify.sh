#!/usr/bin/env bash
# Every check that needs no Docker daemon: lint, unit tests, CLI and static checks.
# Container smoke tests are separate: tests/smoke.sh.
set -euo pipefail
ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
tests/lint.sh
python3 -m unittest discover -s tests
tests/test_setup.sh
tests/test_cli.sh
tests/static.sh
echo 'Lint, unit, CLI and static checks passed.'
