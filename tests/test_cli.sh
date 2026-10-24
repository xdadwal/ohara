#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
TASK_TMP="$(mktemp -d)"
trap 'rm -rf "$TASK_TMP"' EXIT
cp -R "$ROOT_DIR/scripts" "$TASK_TMP/scripts"
cp "$ROOT_DIR/.env.example" "$TASK_TMP/.env.example"
for command in setup check up status tls media-setup tailscale adguard immich; do
  (cd /; "$TASK_TMP/scripts/$command" --help >/dev/null)
done
(cd /; "$TASK_TMP/scripts/maintainerr" --help >/dev/null)
(cd /; "$TASK_TMP/scripts/lan-proxy" --help >/dev/null)
(cd /; "$TASK_TMP/scripts/jellyfin-theme" --help >/dev/null)
(cd /; "$TASK_TMP/scripts/jellyfin-enhanced" --help >/dev/null)
(cd /; "$TASK_TMP/scripts/jellyfin-letterboxd" --help >/dev/null)
(cd /; "$TASK_TMP/scripts/immich-proxy" --help >/dev/null)
(cd /; "$TASK_TMP/scripts/migrate-credentials" --help >/dev/null)
if "$TASK_TMP/scripts/tls" --configure-renewal >"$TASK_TMP/out" 2>&1; then exit 1; fi
if "$TASK_TMP/scripts/tls" --staging --dns-provider godaddy >"$TASK_TMP/out" 2>&1; then exit 1; fi
if "$TASK_TMP/scripts/media-setup" --profile-only >"$TASK_TMP/out" 2>&1; then exit 1; fi
if "$TASK_TMP/scripts/media-setup" --storage-only --owner-email smoke@example.com >"$TASK_TMP/out" 2>&1; then exit 1; fi
if "$TASK_TMP/scripts/media-setup" --storage-only --profile ohara >"$TASK_TMP/out" 2>&1; then exit 1; fi
if "$TASK_TMP/scripts/setup" --dry-run >"$TASK_TMP/out" 2>&1; then
  echo 'Expected dry-run to reject missing config' >&2; exit 1
fi
test ! -e "$TASK_TMP/.env"
if "$TASK_TMP/scripts/setup" --non-interactive >"$TASK_TMP/out" 2>&1; then
  echo 'Expected first setup to stop for configuration' >&2; exit 1
fi
test -f "$TASK_TMP/.env"
printf '\n# operator edit\n' >> "$TASK_TMP/.env"
cp "$TASK_TMP/.env" "$TASK_TMP/saved"
"$TASK_TMP/scripts/setup" --dry-run >"$TASK_TMP/out" 2>&1 || true
cmp "$TASK_TMP/.env" "$TASK_TMP/saved"
if "$TASK_TMP/scripts/check" --unknown >"$TASK_TMP/out" 2>&1; then exit 1; fi
echo 'CLI help, path independence, noninteractive initialization, and preservation checks passed.'
