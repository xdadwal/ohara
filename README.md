# Ohara

A small, agent-friendly homeserver setup for **xdadwal.in**. Docker Compose runs
applications; Nginx and Certbot on the Linux host provide public HTTPS.

| Service | Purpose | Access |
|---|---|---|
| Homepage | Password-protected service dashboard | `xdadwal.in` after activation |
| Jellyfin | Movie and series playback | `jellyfin.xdadwal.in` after activation |
| Radarr + Sonarr | Movie and series acquisition | Private administration |
| Prowlarr | Indexer management and sync | Private administration |
| qBittorrent | Downloads | Private administration |
| Seerr | Media discovery and requests; successor to Jellyseerr | `watch.xdadwal.in` after activation |
| Copyparty | Authenticated file browsing, uploads, and downloads | `files.xdadwal.in` after activation |
| OpenSpeedTest | Browser-based speed test to this server | `speed.xdadwal.in` after activation |
| Nginx + Certbot | Reverse proxy, certificates, and renewal | Public TCP 80/443 |

The apex runs [Homepage](https://github.com/gethomepage/homepage), with links to
Jellyfin, Seerr, Copyparty, and OpenSpeedTest. Immich is a follow-up for personal photos/videos;
it will share the Ohara machine, with storage and backup paths still to be confirmed.
Seerr connects to the included media stack. Follow [media setup](docs/media.md) to
initialize accounts/connections and add your chosen indexers.

## Fresh-host quick start

Bootstrap target: **Ubuntu 24.04 LTS or Debian 13**, systemd, amd64/arm64. Reserve
a stable LAN IP and prepare your storage mounts first. Ansible is not required.

```sh
git clone https://github.com/xdadwal/ohara.git
cd ohara
sudo ./scripts/setup
# First run creates .env and stops. Edit paths, IDs, domain/email.
# Use an editor; .env is literal KEY=value, not a shell script.
# Create/fill the three private files described in docs/credentials.md first.
sudo ./scripts/setup --dry-run
sudo ./scripts/setup --non-interactive
./scripts/check
./scripts/up
./scripts/status
```

If Docker requires elevated access, the commands try `sudo -n docker`; refresh
sudo authentication with `sudo -v` first. Users are not added to the Docker group.
Credentials must be supplied in user-created `local/credentials`,
`local/homepage.env`, and `local/media-credentials`. Setup never generates or
replaces these values. Follow [credential setup](docs/credentials.md) to copy
empty templates, fill them privately, and set permissions before rerunning setup.

Run `scripts/media-setup --owner-email YOUR_REAL_EMAIL` to initialize media accounts
and connections, then add indexers through private administration ([instructions](docs/media.md)).
Complete service accounts using SSH forwarding before exposing applications:

```sh
ssh -L 5055:127.0.0.1:5055 -L 3923:127.0.0.1:3923 \
    -L 3000:127.0.0.1:3000 -L 3002:127.0.0.1:3002 user@server
```

Homepage uses its own password login at the HTTPS apex; it has no Docker socket
access or private service widgets. See [the Immich follow-up](docs/immich-next.md).

Then follow [public activation and operations](docs/operations.md). Only forward
router TCP ports **80 and 443**. Keep backend/admin ports private.

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
