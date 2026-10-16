# Ohara operations

## Host preparation

For an agent-led installation, follow [agent-setup.md](agent-setup.md) for
input collection, user-managed credentials, and account setup boundaries.

Support target: Ubuntu 24.04 LTS or Debian 13 with systemd, amd64/arm64. Bootstrap
installs missing Docker Engine/Buildx/Compose from Docker's official apt repository
and distribution Nginx/Certbot. It preserves existing package versions and fails
on conflicting Docker packages. No curl-to-shell installer, Samba, shell-profile
replacement, Wi-Fi configuration, resolver disabling, or bot cron installation.

Install Git and clone this repository first. `sudo scripts/setup` initially copies
`.env.example` to `.env` and exits nonzero so you can edit it. Set the actual LAN
IP, timezone, domain/subdomains, ACME email, storage paths, and file-service UID/GID.
Values are literal and unquoted; shell substitution is rejected. Rerun with
`--dry-run` to inspect preflight and `--non-interactive` to prepare the host.
Dry run does not install packages or create directories. Python itself is installed
if missing during a real bootstrap. No unattended operation waits for a prompt.

Mount disks before setup. Default `/ohara/files` is a dedicated Copyparty share,
not an invitation to expose `/home` or personal photo storage. Setup creates new
application directories but never recursively changes existing ownership. Seerr
needs UID 1000 write access; Copyparty needs RUN_UID/RUN_GID write access; Pi-hole
manages its own `/etc/pihole` contents. Review permissions on existing directories
manually before startup. Configuration and user-supplied credentials live in `local/`.
Do not commit that directory, `.env`, backups, certificate keys, or diagnostics
containing credentials.

Bootstrap installs an HTTP maintenance/ACME site. On a fresh Nginx installation it
disables only the package default site just installed by that invocation. If an
existing site/default listener conflicts, inspect `sudo nginx -t` and resolve it
manually; setup never disables unrelated preexisting sites. Reserved ports are
53 TCP/UDP on LAN_IP, loopback 3000/3002/3923/5055/7878/8081/8096/8888/8989/9696, and host 80/443 for Nginx.

## Checks and local startup

- `scripts/check --static`: parse config, validate digest pins and Compose inventory/
  port bindings without resolving secret env files or requiring a Docker daemon.
- `scripts/check`: also require the local private files and persistent directories.
- `scripts/up`: validate, then start the local Compose project with a bounded wait.
- `scripts/status`: bounded container and HTTP checks, nonzero if a service is down.
  It does not certify media integration, external access, DNS, or user permissions.

Commands locate the checkout themselves and work from another current directory.
Docker access uses the current context/access or noninteractive sudo. If it fails,
run `sudo -v` and retry; do not add a Docker group member merely to bypass a prompt.
Subprocess output that might contain secrets is suppressed. For a failed Nginx
operation run `sudo nginx -t`; for applications inspect logs locally, redact them
before sharing. Do not publish resolved Compose configuration or `docker inspect`.

Use the README's SSH tunnel and open localhost ports. Follow [media setup](media.md) to initialize the Jellyfin/Seerr owner and
connect the acquisition services. Use `admin` plus the user-supplied Copyparty
password; test authenticated upload, download, move, and delete using a disposable
file. Confirm an anonymous client cannot list/download/write the file. Sign into
Pi-hole at `http://localhost:8888/admin/` and test configuration before changing
router DNS. OpenSpeedTest is at localhost:3000 through the tunnel.

## Public DNS and HTTPS

1. Set A records for the apex and configured watch/files/speed/jellyfin subdomains to
   your public IPv4 address. Do not add a wildcard or AAAA record by assumption.
2. Check for CGNAT, double NAT, blocked ISP ports, or a changing public IP. These
   are external prerequisites, not problems setup can solve. DDNS is a later
   provider-specific choice if your address changes.
3. Forward router TCP 80 and 443 to the Ohara LAN IP. Open these host firewall
   ports deliberately while preserving SSH access. Never forward 53, 3000, 3002, 3923,
   5055, 7878, 8081, 8096, 8888, 8989, or 9696. Docker-published ports can bypass UFW; loopback/LAN bindings
   are intentional. IPv6 firewalls require separate review before adding AAAA.
4. Verify the HTTP maintenance response from mobile data. Check ACME challenge
   paths can be fetched externally, including if the router lacks hairpin NAT.
5. With local account/authentication checks complete, test certificate issuance:
   `sudo scripts/tls --staging --agree-tos`. Staging uses separate certificate
   directories and never enables public application routes.
6. Activate: `sudo scripts/tls --activate --accounts-ready --agree-tos`.
   `--accounts-ready` is an explicit operator attestation, not an automatic test
   of account configuration. This accepts Let's Encrypt's subscriber agreement.
7. Verify trusted HTTPS and hostname matching on all five names externally,
   login/logout, denied anonymous file access, a large upload/download, and a
   complete speed test. The HTTPS apex should show Homepage password login;
   confirm service links appear after login and private APIs reject anonymous access. Rejecting an unknown hostname is intentional.

HTTP-01 needs public TCP 80, including for renewals; it cannot issue wildcard
certificates. Certbot uses host webroot `/var/lib/ohara/acme`, lineage
`/etc/letsencrypt/live/ohara`, the distribution `certbot.timer`, and an installed
absolute-path deploy hook. Configuration updates test Nginx before reloading;
failed config/reload restores the previous managed file. A failed certificate
request never replaces the active Nginx config. Do not delete working certificates.

Verify `systemctl list-timers certbot.timer`, then
`sudo certbot renew --cert-name ohara --dry-run --run-deploy-hooks`. Activation
runs this renewal test too. If it fails after activation, HTTPS may be working but
renewal is not verified: inspect the timer/logs and fix it. Certificate renewal
itself is not reversed when a later configuration check fails. Changing domains
requires updating DNS/.env and rerunning issuance deliberately; setup preserves
an already active HTTPS config.

## LAN DNS and port conflicts

Pi-hole listens only on LAN_IP:53 and has no public administration route. If port
53 is occupied, inspect `sudo ss -lntup`, the LAN address assignment, and
`resolvectl status`. A systemd-resolved stub bound only to 127.0.0.53 can coexist
with a LAN-only binding; a wildcard DNS listener may conflict. Do not blindly
disable systemd-resolved or replace `/etc/resolv.conf`. Plan any resolver change
manually and keep a working upstream DNS path while installing/recovering Ohara.
Never make Docker installation depend on a not-yet-started Pi-hole.

After Pi-hole works, point router DHCP DNS to its reserved LAN address. Optionally
add local DNS records mapping the public service hostnames to the LAN IP when
hairpin NAT is unavailable; public records continue to point at the public IP.
Test TCP and UDP DNS from a second LAN client, including a blocked-domain case.
Changing router/client DNS is a manual deployment step, not done by this repo.

## Migration from the previous repository

Before shutdown, inventory old containers, mounts, named volumes, paths, and image
versions locally; back up configuration and application state without publishing
secrets. The old stack included Jellyfin, Radarr, Prowlarr, qBittorrent, Kuma,
Tailscale, Chesskit, Homer, and standalone Redis. Jellyfin, Radarr, Prowlarr and qBittorrent now have fresh definitions in this stack;
other removed definitions remain retired;
no host containers, files, or volumes are deleted by this code change.

Use a maintenance window to stop only the inventoried old services that conflict.
Do not use `docker system prune`, `down -v`, or blanket container removal. Retained
services also have new bindings/config paths, so migrate their state explicitly
rather than running two copies over the same database. Restore copied state to
new paths if needed, review ownership, then run the local startup/account checks.
Activate DNS/HTTPS next and change router DNS last. Retain the previous checkout,
config copies, and backup until restore and public behavior are verified.

Credentials formerly committed in this repository must be treated as exposed:
rotate the old Copyparty/Pi-hole passwords, Wi-Fi password, and any real Tailscale
key through their owning systems. Removing tracked files does not remove Git
history or revoke a credential. This change does not rewrite history or rotate
external credentials automatically.

## Backups, upgrades, and recovery

Back up media libraries and Jellyfin/Radarr/Sonarr/Prowlarr/qBittorrent state,
`local/media-credentials` and `local/media-state.json` (see [media.md](media.md)).
Back up `.env`, `local/`, Copyparty files and state, Pi-hole data, Seerr config/
SQLite database, Homepage configuration and local/homepage.env, managed Nginx config, and `/etc/letsencrypt` (including renewal
config and deploy hook). Encrypt backups and keep an off-host copy; credentials
and certificate private keys are sensitive. Stop database writers for consistent
filesystem backups or follow each service's supported backup/export procedure.
Record the deployment commit and image digests with each backup.

Restore first to an isolated temporary location. Verify file checksums, ownership,
application login, DNS settings, and representative file reads before replacing
live data. Do not expose restored services publicly while testing. Have a fallback
LAN resolver available if Pi-hole is stopped. Only an actual restore demonstrates
backup usefulness; a successful archive command alone does not.

Upgrade through a PR changing reviewed `versions.env` digests. Check upstream
release/migration notes and manifests, take a consistent backup, then restart
with `scripts/up` in a maintenance window. Verify local and external behavior.
Rollback may require restoring the previous data snapshot as well as configuration
and image references if an application upgraded its database schema. Do not promise
that an old image can read a migrated database.

## Verification scope

CI checks configuration, mocked provisioning behaviors, CLI failure paths, and
isolated container/proxy smoke behavior with dummy data. These do not establish
host package installation, disk mount correctness, real ACME renewal, router
forwarding, CGNAT status, or public reachability. Before first production use,
run bootstrap twice on a disposable supported systemd VM and verify preservation,
then follow the real-host acceptance steps above. amd64/arm64 manifests are pinned;
architecture availability is not the same as tested performance on your hardware.

## Immich follow-up

See [immich-next.md](immich-next.md) for the scope and pending choices. Confirm host placement, hardware, storage capacity, backup location and photo
hostname first. Use the official release-matched Compose deployment, including
its required database/cache services; keep PostgreSQL on suitable local storage.
Do not share its database or expose its photo directory through Copyparty by
inference. Use a dedicated subdomain with the documented large-upload/WebSocket
proxy configuration. Back up media plus database and prove restoration before
relying on it for your personal archive.

## Upstream references

- https://docs.docker.com/engine/install/ubuntu/
- https://docs.docker.com/engine/install/debian/
- https://docs.docker.com/engine/network/packet-filtering-firewalls/
- https://docs.seerr.dev/getting-started/docker/
- https://docs.pi-hole.net/docker/
- https://github.com/9001/copyparty#reverse-proxy
- https://github.com/openspeedtest/Docker-Image
- https://letsencrypt.org/docs/challenge-types/
- https://eff-certbot.readthedocs.io/en/stable/using.html#renewing-certificates
- https://docs.immich.app/install/docker-compose/

See [verification.md](verification.md) for evidence collected during implementation.
During a hostname change, ACME challenge routes are temporarily added for new
names while existing HTTPS stays active; issuance failure restores the prior
config. The certificate retains prior names for rollback safety, so keep their
DNS/challenge paths working during the transition. Retiring old certificate names
entirely requires a separately planned cutover rather than automatic removal.

## Homepage

Homepage serves the HTTPS apex. Supply its password and cookie-signing secret
in user-created `local/homepage.env` (mode 0600), with `HOMEPAGE_AUTH_ENABLED=true`.
See [credentials.md](credentials.md) for empty templates and validation.
After activation, sign in at `https://xdadwal.in` with that password. Authentication
cookies are secure; use the configured HTTPS hostname for login, not a raw IP or
an HTTP tunnel. Local health is `http://127.0.0.1:3002/api/healthcheck`.

Nginx limits password callback attempts to five per minute per client IP, with a
burst of five. Homepage's allowed host is the configured apex. It runs without
root privileges, without Docker socket access, and without service API keys.
Links do not grant access to the applications: each service retains its own login.
Pi-hole administration is intentionally absent from the publicly served dashboard.

Edit `${DATA_ROOT}/homepage/*.yaml` to customize links, settings, and widgets.
Setup seeds files from `configs/homepage` only when absent and preserves edits;
restart Homepage after changes using `scripts/up`. Service hostnames are supplied
through environment variables, so changing `.env` does not require rewriting
links. Setup does not overwrite an existing authentication file or silently rotate
passwords. Keep it with your encrypted backups. If it is missing, setup fails; restore your file from a private backup.

After updating an existing checkout to include Homepage, rerun setup before up.
Supply the private auth input first; setup creates its configuration directory
without generating or changing service credentials. Rerun explicit HTTPS activation to replace an older
apex maintenance route. The HTTP bootstrap remains maintenance-only until then.

Upstream: https://gethomepage.dev/installation/ and
https://gethomepage.dev/installation/docker/.
