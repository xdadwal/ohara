# Ohara

A small, agent-friendly homeserver setup for **xdadwal.in**. Docker Compose runs
applications; Nginx and Certbot on the Linux host provide public HTTPS.

On the current host, the separate portfolio checkout at `/home/akshay/xdadwal.in`
runs as `portfolio.service` on loopback port 8010 and serves the apex. The password
protected dashboard is at **ohara.xdadwal.in** (`HOMEPAGE_HOST` in `.env`). Other
service hostnames are unchanged.
See [replication](docs/replication.md) to reproduce both routes and the selected
media settings on another machine, or to migrate private state safely.

| Service | Purpose | Access |
|---|---|---|
| Homepage | Password-protected service dashboard | `HOMEPAGE_HOST` (`ohara.xdadwal.in` on this host) |
| Jellyfin | Movie and series playback | `tv.xdadwal.in` after activation |
| Radarr + Sonarr | Movie and series acquisition | Private administration |
| Lidarr | Music acquisition | Private administration (8686) |
| Navidrome | Music playback | `NAVIDROME_HOST` (default `music.xdadwal.in`); loopback 4533 |
| Bazarr | Movie and series subtitles | Private administration (6767) |
| Prowlarr | Indexer management and sync | Private administration |
| qBittorrent | Downloads | Private administration |
| Seerr | Media discovery and requests; successor to Jellyseerr | `seerr.xdadwal.in` after activation |
| OpenSpeedTest | Browser-based speed test to this server | `speed.xdadwal.in` after activation |
| Nginx + Certbot | Reverse proxy, certificates, and renewal | Public TCP 80/443 |
| Immich (optional separate project) | Personal photos/videos; machine learning disabled | immich.xdadwal.in; owner setup complete |
| Maintainerr (optional separate project) | Media maintenance; LAN-only administration | maintainerr.xdadwal.in; loopback 6246 |
| AdGuard Home (optional separate project) | LAN DNS, filtering and local domain rewrites | LAN TCP/UDP 53; private dashboard 3003 |

The dashboard runs [Homepage](https://github.com/gethomepage/homepage), with links to
Jellyfin, Navidrome, Seerr, and OpenSpeedTest, plus native media, resource, clock and weather
widgets ([configuration](docs/homepage-widgets.md)). Immich is available as a separate optional project for personal photos/videos,
with machine learning disabled. See [Immich operations](docs/immich.md); Immich is running with public HTTPS and owner setup complete on this host;
backup/restore acceptance remains pending.
Seerr connects to the included media stack. Follow [media setup](docs/media.md) to
initialize accounts/connections and add your chosen indexers. Music flows from Lidarr into the shared music library and Navidrome. Select subtitle languages
and providers explicitly in Bazarr; Seerr requests remain movies and series only.

See [the current stack overview](docs/stack.md) for access, storage and pending work.
The optional [Abyss Jellyfin theme](docs/jellyfin-theme.md) includes persistent
CSS and Spotlight without changing the official image or media storage.
Optional [Maintainerr](docs/maintainerr.md) connects the existing media services
for owner-selected maintenance rules; initial integration creates no cleanup rules.

## Fresh-host quick start

Bootstrap target: **Ubuntu 24.04 LTS or Debian 13**, systemd, amd64/arm64. Reserve
a stable LAN IP and prepare your storage mounts first. Ansible is not required.
Setup also installs [bpytop](https://github.com/aristocratos/bpytop) from the
distribution packages for terminal monitoring. Run `bpytop` locally or over SSH
to view CPU, memory, disk, network and process usage; press `q` to quit.

```sh
git clone https://github.com/xdadwal/ohara.git
cd ohara
sudo ./scripts/setup
# First run creates .env and stops. Edit paths, IDs, domain/email.
# Use an editor; .env is literal KEY=value, not a shell script.
# Create/fill the private .env file described in docs/credentials.md first.
sudo ./scripts/setup --dry-run
sudo ./scripts/setup --non-interactive
./scripts/check
./scripts/up
./scripts/status
```

If Docker requires elevated access, the commands try `sudo -n docker`; refresh
sudo authentication with `sudo -v` first. Users are not added to the Docker group.
Credentials must be supplied in user-created `.env`. Setup never generates or
replaces these values. Follow [credential setup](docs/credentials.md) to copy
the empty example into `.env`, fill it privately, and set permissions before rerunning setup.
For an existing deployment using split credential files, run
`scripts/migrate-credentials` before check/up. It preserves values and archives the
old files privately; see [migration instructions](docs/credentials.md#migrate-the-old-files).

Run `scripts/media-setup --owner-email YOUR_REAL_EMAIL` to initialize media accounts
and connections, then add indexers through private administration ([instructions](docs/media.md)).
Complete service accounts using SSH forwarding before exposing applications:

```sh
ssh -L 5055:127.0.0.1:5055 \
    -L 3000:127.0.0.1:3000 -L 3002:127.0.0.1:3002 user@server
```

Homepage uses its own password login at HOMEPAGE_HOST. Native Jellyfin and Seerr
widgets use supplied application API keys over the Docker network; no Docker socket
is exposed. The Navidrome Now Playing widget uses a token derived locally from
its existing password; see [widget setup](docs/homepage-widgets.md).
See [the Immich follow-up](docs/immich-next.md).

Then follow [public activation and operations](docs/operations.md). Only forward
router TCP ports **80 and 443**. Never forward DNS or backend/admin ports.
GoDaddy DNS-01 wildcard certificates and automated renewal are also supported by
`scripts/tls --dns-provider godaddy`; see the private-token setup and existing
certificate migration in [operations](docs/operations.md#godaddy-dns-validation-and-wildcard-renewal).

## Optional LAN DNS

For LAN DNS and filtering, see [AdGuard Home setup](docs/adguard.md).
It starts independently with `scripts/adguard up`; router/client DNS cutover is
a separate verified step. Existing applications and public DNS are preserved.
For AdGuard and media administration in a browser without SSH tunnels, see
[LAN-only HTTPS service routes](docs/lan-services.md).

## Optional remote SSH

Use the host Tailscale client for private SSH access while public HTTPS and LAN
traffic keep their existing routes. Run `scripts/tailscale --dry-run`, then
`sudo scripts/tailscale --install`; enrollment is a separate browser login.
Follow [Tailscale setup](docs/tailscale.md) for routing flags, SSH access policy
and verification. No additional .env credentials or Compose service are needed.

## For agents and contributors

Start with [AGENTS.md](AGENTS.md), [decisions](docs/decisions.md), and
[the approved implementation plan](docs/superpowers/plans/2026-10-15-ohara-setup.md).

```sh
python3 -m unittest discover -s tests -v
./tests/test_setup.sh
./tests/test_cli.sh
./tests/static.sh       # requires ShellCheck
./tests/smoke.sh        # Docker; isolated disposable project and dummy data
```

`./scripts/check --static` checks configuration/Compose without requiring local
storage or private files. It requires Docker CLI/Compose but no running daemon.
Host provisioning, real DNS/port forwarding, and public HTTPS need their own
verification; local tests cannot establish those outcomes.

MIT licensed. Individual services retain their own licenses.
