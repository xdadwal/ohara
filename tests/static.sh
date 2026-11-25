#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
# scripts/setup is the only bash entry point; Python is linted by tests/lint.sh.
SHELL_FILES=(scripts/setup tests/*.sh)
for file in "${SHELL_FILES[@]}"; do
  bash -n "$file"
done
if command -v shellcheck >/dev/null 2>&1; then
  shellcheck "${SHELL_FILES[@]}"
else
  echo 'ShellCheck missing; install it or run the CI checks.' >&2
  exit 1
fi
python3 -m compileall -q scripts tests
