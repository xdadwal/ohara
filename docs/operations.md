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
`.env.example` to `.env` and exits nonzero so you can edit it. Set the timezone, domain/subdomains, ACME email, storage paths, and file-service UID/GID.
Values are literal and unquoted; shell substitution is rejected. Rerun with
`--dry-run` to inspect preflight and `--non-interactive` to prepare the host.
Dry run does not install packages or create directories. Python itself is installed
if missing during a real bootstrap. No unattended operation waits for a prompt.

Mount disks before setup. DATA_ROOT holds application state; MEDIA_ROOT holds
media downloads and libraries. Setup creates new application directories but
never recursively changes existing ownership. Seerr needs UID 1000 write access;
other media services and Homepage need RUN_UID/RUN_GID access. Review existing
permissions manually. User credential inputs live in .env. Keep secrets, .env, backups and private diagnostics out of Git.

Bootstrap installs an HTTP maintenance/ACME site. On a fresh Nginx installation it
disables only the package default site just installed by that invocation. If an
existing site/default listener conflicts, inspect `sudo nginx -t` and resolve it
manually; setup never disables unrelated preexisting sites. Reserved ports are
loopback 3000/3002/5055/7878/8081/8096/8989/9696, and host 80/443 for Nginx.

## Optional remote SSH

See [Tailscale](tailscale.md) for the separate host client installer, owner browser
enrollment, ordinary OpenSSH, and SSH-only tailnet network policy. Setup/up never
install or enroll it automatically. Public HTTPS remains on the existing network.

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
connect the acquisition services. OpenSpeedTest is at localhost:3000 through the
tunnel. Verify Homepage password login at its HTTPS hostname before invitations.

## Public DNS and HTTPS

Current host routing: `xdadwal.in` serves the separate FastAPI portfolio
(`portfolio.service`, `127.0.0.1:8010`); `ohara.xdadwal.in` serves Homepage.
Set `HOMEPAGE_HOST=ohara.xdadwal.in` in `.env` to preserve its allowed hostname,
external authentication URL and status checks across container recreation.
Omitting the optional setting retains the original apex dashboard behavior.
Use DNS mode below for certificate operations on this deployment: it preserves
the separate apex route, private ACLs and existing wildcard lineage. HTTP mode
rejects a separate dashboard hostname rather than replacing the portfolio route.
Portfolio code/CSS updates and service restart instructions are in the portfolio
checkout's `deploy/README.md`. Nginx routes live in `/etc/nginx/conf.d/ohara.conf`;
historical copies are archived under `~/ohara-backups`. For a fresh setup with the
same routing, set `PORTFOLIO_PORT=8010` and use [replication.md](replication.md).
The exact stable host configuration, including localhost redirects and the
public-IP probe, is tracked under [configs/nginx/deployed](../configs/nginx/deployed/README.md).
These are reviewed host-specific baselines; generic setup does not automatically
install their local-certificate or static-IP assumptions. Reusable templates match
the shared IPv6 and Jellyfin settings. Compare both deployed files after a change
and update the baseline deliberately; rerunning setup preserves existing HTTPS.

1. In GoDaddy, set A records for the apex and configured dashboard/seerr/speed/jellyfin/Navidrome names to
   your public IPv4 address. Do not add a wildcard or AAAA record by assumption.
2. Check for CGNAT, double NAT, blocked ISP ports, or a changing public IP. These
   are external prerequisites, not problems setup can solve. DDNS is a later
   provider-specific choice if your address changes.
3. Forward router TCP 80 and 443 to the Ohara LAN IP. Open these host firewall
   ports deliberately while preserving SSH access. Never forward backend ports
   3000, 3002, 4533, 5055, 6767, 7878, 8081, 8096, 8686, 8989, or 9696. Docker-published ports can bypass UFW; loopback bindings
   are intentional. IPv6 firewalls require separate review before adding AAAA.
4. Verify the HTTP maintenance response from mobile data. Check ACME challenge
   paths can be fetched externally, including if the router lacks hairpin NAT.
5. With local account/authentication checks complete, test certificate issuance:
   `sudo scripts/tls --staging --agree-tos`. Staging uses separate certificate
   directories and never enables public application routes.
6. Activate: `sudo scripts/tls --activate --accounts-ready --agree-tos`.
   `--accounts-ready` is an explicit operator attestation, not an automatic test
   of account configuration. Verify Homepage, Jellyfin, Seerr and Navidrome
   account readiness through private access first, including successful Navidrome login.
   This accepts Let's Encrypt's subscriber agreement.
7. Verify trusted HTTPS and hostname matching on all configured names externally,
   login/logout, Jellyfin and Navidrome playback, and a complete speed test. The configured Homepage hostname should show its password login;
   confirm service links appear after login and private APIs reject anonymous access. Rejecting an unknown hostname is intentional.

### GoDaddy DNS validation and wildcard renewal

Use DNS-01 when port 80 is unavailable or a wildcard certificate is required.
The scripts support GoDaddy-managed authoritative DNS through the v3 API and a
Personal Access Token (PAT). Create a PAT in the GoDaddy developer dashboard with
the `domains.dns:update` capability; the legacy key/secret pair is not supported.
The account must have DNS API access. Keep the token out of chat, Git and command
arguments. Save a JSON file under ignored `local/`, for example
`local/godaddy-dns.json`, with mode **0600**:

```json
{"domain": "xdadwal.in", "token": "YOUR_PERSONAL_ACCESS_TOKEN"}
```

The zone must match `DOMAIN`; all configured service names must be direct
subdomains of that zone. For a new deployment, after local account setup:

```sh
sudo scripts/tls --staging --dns-provider godaddy \
  --dns-credentials /absolute/path/to/local/godaddy-dns.json --agree-tos
sudo scripts/tls --activate --dns-provider godaddy \
  --dns-credentials /absolute/path/to/local/godaddy-dns.json \
  --accounts-ready --agree-tos
```

For an **existing manually issued `ohara-wildcard` certificate**, use:

```sh
sudo scripts/tls --configure-renewal --dns-provider godaddy \
  --dns-credentials /absolute/path/to/local/godaddy-dns.json --agree-tos
```

This tests staging validation using Certbot `reconfigure` before saving renewal
options, then runs `renew --dry-run --run-deploy-hooks`. Existing Nginx routes,
private administration ACLs and the production certificate remain in place during
renewal configuration. Fresh activation preserves existing domain routes and ACLs;
a fresh HTTP bootstrap receives the standard public HTTPS routes. Wildcard DNS
does not automatically publish new applications or private administration.

Hooks and credentials are installed root-only at
`/usr/local/lib/ohara/dns_godaddy.py` and `/etc/ohara/dns-godaddy.json`.
Renewals do not depend on the checkout path. Production lineage is
`/etc/letsencrypt/live/ohara-wildcard`; `certbot.timer` performs renewal and the
deploy hook validates/reloads Nginx. Staging uses separate hook, credentials,
journal and certificate directories, so a staging test cannot replace production
credentials. Rerun configuration after rotating the PAT, and monitor its expiry.

The hook adds individual TXT records at `_acme-challenge`, preserves existing
values (including simultaneous apex/wildcard challenges), and deletes only record
IDs it created. It waits at least one hour plus a safety margin to expire DNS
caches, then requires two consecutive successful checks through both Google and
Cloudflare DNS-over-HTTPS. Initial configuration and dry runs can each take more
than an hour; leave the command running. Existing challenge TTLs above 3600 cause
an error: lower those TTLs and wait out the prior TTL before retrying. Providers,
network failures, or stale journals may require inspection; failures do not prove
renewal works. Inspect `/var/log/letsencrypt/letsencrypt.log` privately and the
root-only journal `/var/lib/ohara/acme-dns` before retrying after interruption.
Do not delete unrelated TXT records to resolve an error.

Code tests mock GoDaddy and ACME. Only a successful live staging validation and
renewal dry run establish that the supplied account/token can renew unattended.
Until that succeeds, the existing manual certificate still requires manual renewal.

References: [GoDaddy DNS API](https://developer.godaddy.com/en/docs/references/rest/domains/v3/list-dns-records),
[PAT permissions](https://developer.godaddy.com/en/docs/api-users/auth),
[Certbot renewal configuration](https://eff-certbot.readthedocs.io/en/stable/using.html#modifying-the-renewal-configuration-of-existing-certificates).

### Default HTTP validation

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

## DNS and migration from a deployed Pi-hole

Public domain records are managed at GoDaddy. Ohara no longer includes a local DNS
server, DNS filtering, or DHCP service. The host and LAN clients use their existing
router/ISP or explicitly configured resolver. LAN_IP is no longer required in .env;
older LAN_IP lines are accepted and ignored. Port 53 and admin port 8888 are no
longer published or checked by Ohara.

If Pi-hole was actually deployed and clients/router DHCP still use its address,
configure a working replacement DNS resolver first, renew client leases and verify
lookups from another LAN device. Public GoDaddy records alone do not change the
DNS resolver your clients use. If Pi-hole was never deployed, no cutover is needed.

Removing its Compose definition does not stop an already-running container. During
authorized deployment, identify only the old Ohara Pi-hole instance:

```sh
docker ps --filter label=com.docker.compose.project=ohara \
  --filter label=com.docker.compose.service=pihole --format '{{.ID}} {{.Names}}'
```

After verifying resolver cutover, stop that identified container deliberately.
Keep DATA_ROOT/pihole and local/pihole.env as recoverable retired state unless the
user requests deletion. Do not use blanket pruning or stop unrelated containers.
Setup/up do not rewrite router DNS, delete old files, or remove orphan containers.

## Retired Copyparty and files hostname

Copyparty, port 3923 and files.xdadwal.in application routing are removed. FILES_ROOT
and FILES_HOST in older .env files are accepted and ignored. local/credentials is
no longer required or read. Existing shares, DATA_ROOT/copyparty, local/copyparty.conf
and old credential files are preserved; no automatic data cleanup occurs.

During authorized deployment, identify any old Copyparty container using the Ohara
project/service labels and stop only that container. Rerun explicit TLS activation
to replace an older managed files route; setup preserves working HTTPS configs.
Homepage's existing services.yaml is also preserved: remove the retired link there
manually so customizations are not overwritten.

A certificate issued before removal may still cover files.xdadwal.in. Activation
preserves prior certificate names for rollback and keeps HTTP ACME challenge handling
for those names, while removing their HTTPS application routes. Keep their DNS
records resolving to the server until a deliberate certificate-name retirement is
completed. Fresh deployments request only the configured active names. Do not delete a
working certificate or change renewal metadata casually.

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
Activate public DNS/HTTPS next. Follow the retired DNS cutover steps above if applicable. Retain the previous checkout,
config copies, and backup until restore and public behavior are verified.

Credentials formerly committed in this repository must be treated as exposed:
rotate the old Copyparty/Pi-hole passwords, Wi-Fi password, and any real Tailscale
key through their owning systems. Removing tracked files does not remove Git
history or revoke a credential. This change does not rewrite history or rotate
external credentials automatically.

## Backups, upgrades, and recovery

Back up media libraries and Jellyfin/Navidrome/Radarr/Sonarr/Lidarr/Bazarr/Prowlarr/qBittorrent state,
`.env` and `local/media-state.json` (see [media.md](media.md)).
Back up `.env`, `local/`, Seerr config/
SQLite database, Homepage configuration, managed Nginx config, and `/etc/letsencrypt` (including renewal
config and deploy hook). Encrypt backups and keep an off-host copy; credentials
and certificate private keys are sensitive. Stop database writers for consistent
filesystem backups or follow each service's supported backup/export procedure.
Record the deployment commit and image digests with each backup.

Restore first to an isolated temporary location. Verify file checksums, ownership,
application login, DNS settings, and representative file reads before replacing
live data. Do not expose restored services publicly while testing. Have a fallback
network/DNS path available during recovery. Only an actual restore demonstrates
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
Keep its database and personal photo storage isolated from other services. Use a dedicated subdomain with the documented large-upload/WebSocket
proxy configuration. Back up media plus database and prove restoration before
relying on it for your personal archive.

## Upstream references

- https://docs.docker.com/engine/install/ubuntu/
- https://docs.docker.com/engine/install/debian/
- https://docs.docker.com/engine/network/packet-filtering-firewalls/
- https://docs.seerr.dev/getting-started/docker/
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
in user-created `.env` (mode 0600), with `HOMEPAGE_AUTH_ENABLED=true`.
See [credentials.md](credentials.md) for empty templates and validation.
After activation, sign in at `https://<HOMEPAGE_HOST>` with that password. Authentication
cookies are secure; use the configured HTTPS hostname for login, not a raw IP or
an HTTP tunnel. Local health is `http://127.0.0.1:3002/api/healthcheck`.

Nginx limits password callback attempts to five per minute per client IP, with a
burst of five. Homepage's allowed host is HOMEPAGE_HOST. It runs without
root privileges or Docker socket access. Native Jellyfin/Seerr widgets use
application-issued API keys supplied privately; see [widget setup](homepage-widgets.md).
Links do not grant access to the applications: each service retains its own login.

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

## Homepage speed-test link

The OpenSpeedTest service card links to the configured SPEED_HOST over HTTPS.
Open it and press Start to measure this browser's connection to Ohara, including
the network path and proxy. It does not display server-to-internet speed history.
No extra container, API key or credential is required.

Setup preserves existing Homepage configuration. On an existing installation,
remove only the OpenSpeedTest widget block from DATA_ROOT/homepage/services.yaml,
retaining its href, icon and description. Refresh Homepage; use scripts/up if a
restart is needed. Preserve other dashboard customizations.

See [Homepage widget configuration](homepage-widgets.md) and
[OpenSpeedTest](https://github.com/openspeedtest/Speed-Test).

## Music and subtitles operations

Lidarr (loopback 8686) and Bazarr (loopback 6767) use private SSH forwarding;
no public admin subdomains are configured. Navidrome provides music playback on
loopback 4533 and configurable NAVIDROME_HOST; music.xdadwal.in is the default; verify public DNS before HTTPS activation. Append missing Lidarr/Bazarr
credential entries and NAVIDROME_PASSWORD to the private root `.env`, preserving
every existing value; see [credentials.md](credentials.md).

After setup, verify Prowlarr → Lidarr sync, the qBittorrent `music` category,
Lidarr root `/data/library/music`, and Navidrome music scan/playback. Navidrome
reads MEDIA_ROOT/library/music read-only at `/music` and keeps writable state in
DATA_ROOT/navidrome at `/data`. Verify its admin login with the supplied password;
media-setup uses supported first-run/login APIs and never resets an existing
account. Fresh Jellyfin setup adds Movies/TV Shows only. Preserve existing Music
libraries; manually hide/remove only the library definition if desired, keeping
all music files. No additional Navidrome API key is required. Seerr
continues to request movies and series only. Verify Bazarr Radarr/Sonarr
connections and shared `/data/library` paths; it needs write access beside media
for subtitle files. Existing Bazarr configuration is preserved and requires
manual connection verification. The operator must select subtitle languages and
providers and privately supply any required provider credentials.

The discussed final NAS/multiple-node topology is not implemented. These services
run in the current Compose stack; a future acquisition node is their intended
home. This change does not provision multiple nodes, shared auth or local DNS.

Navidrome HTTPS and its managed HTTP redirect suppress URL-bearing Nginx logs
because Subsonic URLs can contain credentials. Diagnose music upstream problems
with scripts/status, Navidrome service logs and connectivity checks rather than
request-URL logging. The public music route uses a five-second connection timeout;
streaming reads retain the longer playback timeout.

## Jellyfin hostname cutover

JELLYFIN_HOST defaults to tv.xdadwal.in. Existing private .env files are preserved,
so update that value explicitly before redeploying. Add/update the GoDaddy record
for tv.xdadwal.in to the intended public IP. Existing browser links derive from
JELLYFIN_HOST; an edited Homepage file with a literal old URL needs a manual update.

For an existing HTTPS deployment, back up Nginx configuration and change the
Jellyfin HTTPS server_name and managed HTTP host list to the new hostname,
preserving unrelated routes and ACLs. Test nginx -t before reloading. A wildcard
certificate for *.xdadwal.in covers tv.xdadwal.in; an HTTP-01 certificate with
explicit names needs deliberate expansion through scripts/tls before serving the
new route. DNS-TLS migration deliberately rejects missing/unmatched service routes
rather than silently replacing an existing custom site. Verify staging and the
production certificate before cutover. Keep the old configuration for rollback.

Recreate Jellyfin to update its published URL. Existing Seerr configuration is
preserved on reruns: update its Jellyfin external URL to https://tv.xdadwal.in
through Settings, while keeping the internal Docker URL unchanged. Update saved
server URLs in Jellyfin clients. No private credential values or live DNS/Nginx
settings are changed by this repository edit.
