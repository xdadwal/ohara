#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
for file in scripts/setup scripts/check scripts/up scripts/status scripts/tls scripts/media-setup scripts/tailscale scripts/ohara tests/*.sh; do
  bash -n "$file"
done
if command -v shellcheck >/dev/null 2>&1; then
  shellcheck scripts/setup scripts/check scripts/up scripts/status scripts/tls scripts/media-setup scripts/tailscale scripts/ohara tests/*.sh
else
  echo 'ShellCheck missing; install it or run the CI checks.' >&2
  exit 1
fi
python3 -m compileall -q scripts tests
