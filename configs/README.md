# Configuration templates and baselines

Everything here is non-secret. Private values live only in the root `.env`
([credentials](../docs/credentials.md)). Three kinds of file sit side by side,
and they are edited differently:

- **Seed**: copied to the host once, then owned by the owner. Changing the seed
  does not change an existing installation.
- **Rendered**: read by a command every time it runs, with settings substituted.
- **Installed copy**: tracked so the repository can be compared with what is
  installed on the host. Change it together with the installed file.

| Path | Kind | Used by | Guide |
|---|---|---|---|
| `homepage/` | Seed for `DATA_ROOT/homepage` | `scripts/setup`; service commands merge their own cards later | [homepage-widgets](../docs/homepage-widgets.md) |
| `immich/immich.json` | Rendered into Immich's configuration file | `scripts/immich` | [immich](../docs/immich.md), [immich-google-oauth](../docs/immich-google-oauth.md) |
| `jellyfin/abyss/` | Pinned theme assets, copied to `DATA_ROOT/jellyfin-theme` | `scripts/jellyfin-theme` | [jellyfin-theme](../docs/jellyfin-theme.md) |
| `jellyfin/enhanced-qol.json` | Reviewed plugin profile, applied through the API | `scripts/jellyfin-enhanced` | [jellyfin-enhanced](../docs/jellyfin-enhanced.md) |
| `jellyfin/letterboxd-sync.json` | Reviewed plugin release and checksum | `scripts/jellyfin-letterboxd` | [jellyfin-letterboxd](../docs/jellyfin-letterboxd.md) |
| `media/ohara.json` | Indexer and renaming profile, applied through the APIs | `scripts/media-setup --profile ohara` | [media](../docs/media.md) |
| `nginx/*.template`, `nginx/proxy-headers.conf` | Rendered into `/etc/nginx/conf.d` | `scripts/setup`, `scripts/tls`, `scripts/immich-proxy`, `scripts/ntfy-proxy` | [operations](../docs/operations.md) |
| `nginx/deployed/` | Installed copy of this host's `/etc/nginx/conf.d` | `scripts/lan-proxy`, `scripts/bambuddy-proxy`; see its [README](nginx/deployed/README.md) | [lan-services](../docs/lan-services.md) |
| `systemd/` | Installed copy of the alert and storage-watchdog units | `scripts/ntfy install-alerts`, `scripts/storage-watchdog install` | [alerts](../docs/alerts.md), [storage-pool](../docs/storage-pool.md) |
| `storage/watchdog.example.json` | Example only; holds this host's disk identities | copied to ignored `local/` and edited per host | [storage-pool](../docs/storage-pool.md) |
| `ssh/90-ohara-keys-only.conf` | Optional sshd policy, installed by hand | owner, after every device has a key | [agent-setup](../docs/agent-setup.md#optional-host-hardening) |
| `logind/90-ohara-lid.conf` | Optional lid-close policy, installed by hand | owner | [agent-setup](../docs/agent-setup.md#optional-laptop-lid-close-policy) |
| `openwrt/setup.sh` | Runs on the owner's separate OpenWrt device (BusyBox `sh`) | owner, over SSH | [network](../docs/network.md) |

Host-specific values (`xdadwal.in`, LAN addresses, disk UUIDs) appear in
`nginx/deployed/`, `storage/` and `openwrt/`. Never apply those to another host
without discovering that host's own values first.
