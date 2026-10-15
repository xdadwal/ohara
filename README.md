# Ohara

A small, agent-friendly homeserver setup for **xdadwal.in**. Docker Compose runs
applications; Nginx and Certbot on the Linux host provide public HTTPS.

| Service | Purpose | Access |
|---|---|---|
| Homepage | Password-protected service dashboard | `xdadwal.in` after activation |
| Seerr | Media discovery and requests; successor to Jellyseerr | `requests.xdadwal.in` after activation |
| Copyparty | Authenticated file browsing, uploads, and downloads | `files.xdadwal.in` after activation |
| OpenSpeedTest | Browser-based speed test to this server | `speed.xdadwal.in` after activation |
| Pi-hole | LAN DNS and ad blocking | LAN DNS; private administration |
| Nginx + Certbot | Reverse proxy, certificates, and renewal | Public TCP 80/443 |

The apex runs [Homepage](https://github.com/gethomepage/homepage), with links to
Seerr, Copyparty, and OpenSpeedTest. Immich is a follow-up for personal photos/videos;
it will share the Ohara machine, with storage and backup paths still to be confirmed.
Seerr does not stream or download media: connect an external media server, and external Radarr/Sonarr if desired.

## Fresh-host quick start

Bootstrap target: **Ubuntu 24.04 LTS or Debian 13**, systemd, amd64/arm64. Reserve
a stable LAN IP and prepare your storage mounts first. Ansible is not required.

```sh
git clone https://github.com/xdadwal/ohara.git
cd ohara
sudo ./scripts/setup
# First run creates .env and stops. Edit LAN_IP, paths, IDs, domain/email.
# Use an editor; .env is literal KEY=value, not a shell script.
sudo ./scripts/setup --dry-run
sudo ./scripts/setup --non-interactive
./scripts/check
./scripts/up
./scripts/status
```

If Docker requires elevated access, the commands try `sudo -n docker`; refresh
sudo authentication with `sudo -v` first. Users are not added to the Docker group.
Service credentials are written to `local/credentials`; Homepage credentials are
in `local/homepage.env`. Both files have restrictive permissions and are never
printed by setup. Use `sudo` to read the file if you ran setup as root.

Complete service accounts using SSH forwarding before exposing applications:

```sh
ssh -L 5055:127.0.0.1:5055 -L 3923:127.0.0.1:3923 \
    -L 3000:127.0.0.1:3000 -L 3002:127.0.0.1:3002 -L 8888:127.0.0.1:8888 user@server
```

Homepage uses its own password login at the HTTPS apex; it has no Docker socket
access or private service widgets. See [the Immich follow-up](docs/immich-next.md).

Then follow [public activation and operations](docs/operations.md). Only forward
router TCP ports **80 and 443**. Never forward DNS or backend/admin ports.

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
