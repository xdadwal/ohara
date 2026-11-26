# Commands and library

Every file directly in `scripts/` is a command. Each resolves the repository
from its own path, so it runs from any working directory; `--help` describes its
arguments. The guides in [`docs/`](../docs/README.md) say when to run them.

## Commands

| Command | Purpose | Guide |
|---|---|---|
| `setup` | Prepare a supported host: packages, storage, Nginx bootstrap. Bash, because it may have to install Python first | [operations](../docs/operations.md) |
| `check`, `up`, `status` | Validate, start and report the eleven-application main stack | [operations](../docs/operations.md) |
| `tls` | Explicit HTTPS activation and renewal setup | [operations](../docs/operations.md#public-dns-and-https) |
| `media-setup` | Media accounts, connections, storage and quality policy | [media](../docs/media.md) |
| `media-pool` | Guarded startup for services that need the mergerfs pool | [storage-pool](../docs/storage-pool.md) |
| `storage-watchdog` | Install or run the disk reconnect watchdog | [storage-pool](../docs/storage-pool.md) |
| `migrate-credentials` | One-time move of legacy credential files into `.env` | [credentials](../docs/credentials.md#migrate-the-old-files) |
| `jellyfin-theme`, `jellyfin-enhanced`, `jellyfin-letterboxd` | Optional Jellyfin theme and plugins | [theme](../docs/jellyfin-theme.md), [enhanced](../docs/jellyfin-enhanced.md), [letterboxd](../docs/jellyfin-letterboxd.md) |
| `lan-proxy` | LAN-only administration routes on this host | [lan-services](../docs/lan-services.md) |
| `adguard` | Optional LAN DNS project | [adguard](../docs/adguard.md) |
| `immich`, `immich-proxy` | Optional photo project and its HTTPS route | [immich](../docs/immich.md) |
| `bambuddy`, `bambuddy-proxy` | Optional printer management and its HTTPS route | [bambuddy](../docs/bambuddy.md) |
| `orcaslicer` | Optional headless slicer behind Bambuddy | [orcaslicer](../docs/orcaslicer.md) |
| `ntfy`, `ntfy-proxy` | Optional notifications, alert timer and HTTPS route | [ntfy](../docs/ntfy.md), [alerts](../docs/alerts.md) |
| `maintainerr` | Optional LAN-only media maintenance | [maintainerr](../docs/maintainerr.md) |
| `tailscale` | Optional host client for remote SSH | [tailscale](../docs/tailscale.md) |

## How a command is built

```python
#!/usr/bin/env python3
"""One line: what it does and what it never does."""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/lib'))
import cli
import config
import example  # the scripts/lib module that holds the logic


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    ...
    args = parser.parse_args()  # before reading .env, so --help always works
    c = config.load(ROOT / '.env')
    example.do_something(c, ROOT)


if __name__ == '__main__':
    cli.run(main, 'Ohara example')  # prints "Ohara example: <message>", exits 1
```

- An entry point parses arguments and dispatches. Logic goes in a `scripts/lib`
  module, which is what the tests import.
- Raise `ValueError` for a refused or invalid request and `RuntimeError` for a
  failed operation. `cli.run` reports them without a traceback. Messages must not
  contain secrets, child-process output or resolved Compose configuration.
- New library functions take the loaded configuration `c` and the repository
  `root` in that order. A few older ones differ (`immich_oauth.render(root, c)`);
  check the signature before calling.

## Library (`scripts/lib`)

Modules import each other by bare name (`import config`).

| Area | Modules |
|---|---|
| Shared plumbing | `cli` (entry-point error handling), `config` (strict `.env` settings, image pins, `HOST_KEYS`), `credentials` (private values: `load`, `read_env`), `runtime` (subprocess, main-stack and project Compose runners, service table), `host` (packages, directories, preflight), `bootstrap` (behind `scripts/setup`) |
| Nginx and TLS | `proxy` (main routes, HTTP-01), `dns_tls` and `dns_godaddy` (DNS-01), `nginx_site` (install one site file with rollback), `lan_proxy`, `immich_proxy`, `bambuddy_proxy`, `ntfy_proxy` |
| Main stack | `media`, `media_profile`, `media_quality`, `navidrome`, `bazarr`, `media_pool`, `homepage_services` (edit the live Homepage `services.yaml`), `credential_migration` |
| Jellyfin add-ons | `jellyfin_theme`, `jellyfin_enhanced`, `jellyfin_letterboxd` |
| Optional projects | `adguard`, `immich`, `immich_oauth`, `bambuddy`, `orcaslicer`, `ntfy`, `maintainerr`, `tailscale` |
| Installed workers | `alerts`, `storage_watchdog`, `dns_godaddy` |

Reuse before writing something new:

- Compose for a separate project: `runtime.project_compose` (with
  `runtime.project_prefix` and `runtime.starts_containers`).
- Image pins: `config.pinned_images`.
- A few named keys from `.env`: `credentials.read_env`.
- A LAN DNS name for a service: `adguard.ensure_rewrite`.
- A Homepage card or widget: `homepage_services`.
- One Nginx site file with validation and rollback: `nginx_site`.

### Installed workers must stay standalone

`alerts.py`, `storage_watchdog.py` and `dns_godaddy.py` are copied to
`/usr/local/lib/ohara` and run there without the rest of the library. At module
level they may import only the standard library; their install functions import
siblings lazily.

`storage_watchdog.py` is also excluded from the formatter (`ruff.toml`):
`scripts/storage-watchdog install` refuses to rerun when the installed copy
differs from the repository copy, so do not change the file unless the worker
itself has to change. After changing `alerts.py`, rerun
`sudo scripts/ntfy install-alerts` on a host that has it installed.
