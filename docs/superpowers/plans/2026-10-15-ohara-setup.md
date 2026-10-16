# Ohara Agent-Friendly Setup Implementation Plan

Pi-hole/LAN DNS provisions in this historical plan were removed on 2026-10-16.
Use current compose.yaml, AGENTS.md and operations.md for deployment.

Credential generation in this historical plan is superseded by the user-managed
input workflow in [credentials.md](../../credentials.md) (2026-10-16).

> **For agentic workers:** Use `superpowers:executing-plans` to implement this plan task by task. Delegation is unnecessary for this small, closely related infrastructure change. This document authorizes no live deployment.

**Goal:** Make Ohara understandable to a new agent and repeatably installable on a fresh Linux machine, with explicit configuration, local validation, and controlled public HTTPS access.

**Architecture:** Docker Compose manages applications; a small Bash interface prepares the host and operates the stack. Host-installed Nginx proxies loopback-bound application ports; host-installed Certbot manages certificates. No Ansible, management UI, automatic container updater, or additional application framework.

**Tech stack:** Ubuntu/Debian with systemd, Docker Engine and Compose plugin, Bash, Python 3 standard library for strict configuration rendering, Nginx, Certbot, ShellCheck, GitHub Actions.

**Design basis:** The requirements and recommendations below consolidate the conversation. Implementation starts after review of this plan. Sources were checked on 2026-10-15; exact container versions must be verified and pinned during implementation, rather than assuming the repository's old tags remain appropriate.

## Global constraints

- Domain: `xdadwal.in`; timezone: `Asia/Kolkata`.
- Keep Pi-hole, Copyparty, OpenSpeedTest; add Nginx and the current successor to Jellyseerr, proposed as Seerr.
- Remove Jellyfin, Radarr, Prowlarr, qBittorrent, Uptime Kuma, Tailscale, Chesskit, standalone Redis, and Homer from the active configuration.
- Homepage (gethomepage/homepage) serves the HTTPS apex with password login. HTTP bootstrap remains maintenance-only before activation.
- Immich will share the Ohara machine in an independent Compose project; do not deploy it until hardware, storage and backup details are confirmed.
- Initial bootstrap support: Ubuntu 24.04 LTS and Debian 13, amd64/arm64, systemd. Additional distributions/releases require explicit testing and documented support.
- Do not change host network interfaces, router settings, SSH policy, existing resolver settings, or unrelated Nginx sites automatically.
- No destructive data cleanup, volume deletion, recursive ownership changes across existing storage, or Git history rewriting.
- Commit feature work, push its feature branch, and open a PR, as instructed by the user. Preserve unrelated untracked `.DS_Store` files.

## Current findings and upstream changes

The existing repository has separate Compose files, personal paths, a setup script that installs through `get.docker.com`, and shell-profile replacement. There is no shared operation interface or CI. Redis has an incorrect configuration mount; old deployment definitions will be retired rather than repaired. The current cron entry belongs to an external bot and must not be installed as part of Ohara.

Jellyseerr and Overseerr unified as **Seerr** in February 2026. Propose the official Seerr image for this fresh installation; it needs `init: true` and writable configuration for UID 1000. Its application setup and external media connections remain separate from starting the container. Sources: [release announcement](https://docs.seerr.dev/blog/seerr-release/), [Docker installation](https://docs.seerr.dev/getting-started/docker/), [service integration](https://docs.seerr.dev/using-seerr/settings/services/).

Install Docker from its official apt repository with the Compose plugin. Detect existing installations; do not automatically remove conflicting packages. Docker-published ports can bypass UFW, so protect backends through explicit loopback bindings rather than assuming UFW covers them. Sources: [Ubuntu installation](https://docs.docker.com/engine/install/ubuntu/), [Debian installation](https://docs.docker.com/engine/install/debian/), [firewall behavior](https://docs.docker.com/engine/network/packet-filtering-firewalls/).

Use Pi-hole v6 configuration conventions. Publish TCP/UDP 53 only on the configured LAN address; publish its web interface only on loopback. Detect DNS port conflicts without disabling systemd-resolved automatically. Source: [Pi-hole Docker documentation](https://docs.pi-hole.net/docker/).

Copyparty requires service-specific upload and client-IP handling, with authenticated access replacing the repository's anonymous root share. OpenSpeedTest requires at least 35 MB request bodies through a reverse proxy. Sources: [Copyparty upstream guide](https://github.com/9001/copyparty#reverse-proxy), [OpenSpeedTest container guide](https://github.com/openspeedtest/Docker-Image).

## Proposed deployment boundary

| Endpoint | Destination | Access |
|---|---|---|
| `xdadwal.in` | Homepage, `127.0.0.1:3002` | HTTPS with password login once activated |
| `watch.xdadwal.in` | Seerr, `127.0.0.1:5055` | Public after owner setup |
| `files.xdadwal.in` | Copyparty, `127.0.0.1:3923` | Public with application login |
| `speed.xdadwal.in` | OpenSpeedTest, `127.0.0.1:3000` | Public after explicit activation |
| LAN DNS | Pi-hole, `${LAN_IP}:53` TCP/UDP | LAN only; never router-forwarded |
| Pi-hole administration | `127.0.0.1:8888`, via SSH forwarding | Private; no public hostname route |
| Photos | Future Immich project on this host | Storage/backup details pending |

Hostnames above are proposed defaults, configurable before activation. Public DNS is managed at the domain's DNS provider; Pi-hole supplies local resolution. Router forwarding covers TCP 80/443 only. Check CGNAT/double NAT and ISP port restrictions before promising reachability. IPv6 exposure requires its own firewall/reachability check; do not publish AAAA records until that path is verified. A changing public IP requires a separate provider-specific DDNS decision.

Seerr is a request manager, not playback or acquisition. Do not silently restore removed media services. Record whether an external media server and Radarr/Sonarr exist; report request fulfillment as unavailable until configured.

## Files and command contracts

```text
AGENTS.md                         agent entry point and operational boundaries
README.md                         service inventory and fresh-host quick start
compose.yaml                      retained application services only
.env.example                      documented non-secret configuration schema
versions.env                      reviewed image tags/digests, committed
configs/copyparty/config.example   authenticated file-sharing template
configs/nginx/*.template           HTTP bootstrap and HTTPS virtual hosts
scripts/setup                     host preparation, no application deployment
scripts/check                     non-mutating static validation
scripts/up                        start local application stack
scripts/status                    bounded runtime checks and exit status
scripts/tls                       certificate acquisition and HTTPS activation
scripts/lib/common.sh             shared paths and Docker invocation
scripts/render-config.py           strict parser and staged rendering
tests/test_configuration.py        standard-library unittest configuration tests
tests/test_setup.sh                isolated bootstrap command fixtures
.github/workflows/check.yml        static and disposable runtime validation
docs/operations.md                 install, public activation, backup, recovery
docs/decisions.md                  short rationale and unresolved choices
```

Configuration fields: `DOMAIN`, `LAN_IP`, `TZ`, `DATA_ROOT`, `FILES_ROOT`, `RUN_UID`, `RUN_GID`, `ACME_EMAIL`, `REQUESTS_HOST`, `FILES_HOST`, `SPEED_HOST`. Default data root `/ohara`; never make an existing personal directory public by inference. Store local secrets/config under an ignored `local/` directory with restrictive permissions. Do not treat `.env` as executable shell code or accept arbitrary executable values. Image references live only in `versions.env`.

Commands resolve paths from the repository location, work from any current directory, accept `--help`, return nonzero on failure, avoid secret output, and have bounded network requests. Elevated operations use root or sudo only where required; Docker commands use existing access or sudo without adding users to the Docker group automatically. Unattended setup uses explicit `--non-interactive` and fails on missing required inputs instead of prompting indefinitely.

## Review focus

1. Rerunning setup preserves edited config, existing data, unrelated Nginx sites, and ownership.
2. Invalid configuration, missing mounts, or occupied ports produce useful failures before deployment changes.
3. Certificate acquisition/renewal failure leaves the last working Nginx configuration active.
4. Public requests cannot reach Pi-hole admin, anonymous personal files, or unfinished owner setup.
5. Existing Docker installations and unavailable external media servers are reported accurately without destructive remediation or false readiness.

## Task 1: Establish the agent entry point and configuration contract

**Files:** Create `AGENTS.md`, `.env.example`, `versions.env`, `docs/decisions.md`, `scripts/render-config.py`, `tests/test_configuration.py`; update `.gitignore` and `README.md`.

**Produces:** One documented configuration schema; strict parser/rendering used by later commands.

- [ ] Write `AGENTS.md` with service inventory, authoritative files, command contracts, secret handling, no destructive cleanup, and distinction between local/CI/live verification. Keep it concise; reference operations documentation for detail.
- [ ] Define parsing as literal `KEY=value`, with comments/blank lines allowed. Reject duplicate/unknown keys, invalid hostnames/IPs, newline injection, and unsafe paths. Never `source` user configuration or interpolate it into shell commands.
- [ ] Add focused tests using `python3 -m unittest discover -s tests -v`. Include malicious values containing command substitution, changed config preservation, and secret-free failure messages. Check a temporary sentinel file is never created by malicious input.
- [ ] Add ignored paths for `.env`, `local/`, rendered configuration, logs, and `.DS_Store`; remove tracked credential-bearing examples in Task 5 without displaying their contents.
- [ ] Record proposed subdomains, unsupported external integrations, selected homepage, and separate Immich project scope in `docs/decisions.md`.
- [ ] Commit the configuration and agent-documentation deliverable.

## Task 2: Replace the fragmented application stack

**Files:** Create `compose.yaml`; modify `versions.env`, Copyparty configuration, `scripts/check`, `scripts/up`, `scripts/status`, `scripts/lib/common.sh`, and configuration tests.

**Consumes:** Task 1 schema. **Produces:** Local-only application startup with predictable persistent paths.

- [ ] Verify official stable releases and architecture manifests, record source URLs, and pin image digests in `versions.env`. Do not use floating `latest` tags for deployment.
- [ ] Define Seerr with `init: true`, UID-compatible config storage, loopback port 5055, restart policy, and bounded log retention. Use its default SQLite deployment; do not introduce PostgreSQL for it.
- [ ] Define Copyparty with loopback port 3923, explicit file root, authenticated permissions, supported hashed credential configuration, and a narrowly trusted proxy header. Keep credentials in ignored local config. Disable anonymous read/write.
- [ ] Define OpenSpeedTest on loopback port 3000, and Pi-hole DNS on `${LAN_IP}:53` TCP/UDP with administration on loopback port 8888. Apply current v6 settings and persistent storage; omit unneeded DHCP/NTP capabilities.
- [ ] Implement `check` without starting containers or installing dependencies. Use `docker compose --env-file versions.env --env-file .env config --quiet`, then inspect normalized JSON internally to assert service inventory and exact port bindings; never print secret-bearing normalized configuration.
- [ ] Make `up` validate first and start the local stack only. Give `status` finite timeouts and distinct output for container running, HTTP reachable, and owner/integration configuration pending.
- [ ] Test missing secrets, unwritable/new storage, invalid addresses, and exact retained-service/port inventory. Run disposable-container smoke checks without private data.
- [ ] Commit the local-stack deliverable.

## Task 3: Implement repeatable fresh-host bootstrap

**Files:** Replace `scripts/setup.sh` with `scripts/setup`; add `tests/test_setup.sh`; update common helpers and operations docs.

**Consumes:** Task 1 configuration, Task 2 paths. **Produces:** Prepared host without public activation.

- [ ] Preflight `/etc/os-release`, systemd, architecture, sudo/root, required storage mounts, DNS availability, and occupied ports 53/80/443. Separate read-only inspection from package changes with `--dry-run`.
- [ ] Install missing prerequisite packages and use the official Docker apt repository with repository-scoped signing keys. Install Engine, Buildx, and Compose plugin only when needed; verify daemon and Compose access. Existing incompatible installations fail with diagnosis rather than automatic removal or upgrade.
- [ ] Install distribution Nginx, Certbot, and required certificate packages; report selected versions. Do not replace unrelated virtual hosts or package sources.
- [ ] Create new service directories with deliberate ownership; never recursively chown existing data. Preserve existing `.env` and local credentials. Generate missing credentials into mode-0600 files without logging them; point the operator to the file path.
- [ ] Do not install Samba, change shell startup files, change Wi-Fi configuration, or install the legacy bot cron job.
- [ ] Use stubbed command tests for fresh host, already-prepared host, partial failure, unsupported OS, missing sudo, and Docker conflicts. Verify a second run makes no unnecessary mutations.
- [ ] Run installation twice on disposable Ubuntu 24.04 and Debian 13 systemd VMs. Container tests alone do not establish host provisioning behavior. Verify architecture availability separately; label untested hardware accurately.
- [ ] Commit the bootstrap deliverable.

## Task 4: Add Nginx and staged public HTTPS activation

**Files:** Add Nginx templates and `scripts/tls`; update rendering, check/setup scripts, tests, and operations docs.

**Consumes:** Local healthy stack and validated hostnames. **Produces:** Reviewed HTTP bootstrap and renewable HTTPS configuration.

- [ ] Stage an Ohara-only HTTP site serving the ACME webroot and maintenance response. Keep application upstreams private during initial setup. Existing port/site conflicts require manual resolution without disabling unrelated services.
- [ ] Render HTTPS sites for requests/files/speed only after owner/authentication setup has been completed locally and explicitly recorded by the operator. Reject unknown Host names. Do not add a public Pi-hole route.
- [ ] Include Host, protocol, and real-client-IP forwarding; strip/overwrite spoofable client headers. Configure service-specific upload limits, streaming behavior, and timeouts using upstream guidance. OpenSpeedTest gets at least 35 MB bodies with no compression/buffering that distorts measurements; Copyparty gets streaming uploads and deliberate large-file limits.
- [ ] Implement `scripts/tls --staging` for ACME test issuance and production issuance as an explicit later operation. Require email, named domains, and noninteractive agreement flags; HTTP-01 needs public port 80. Do not request wildcard certificates through HTTP-01.
- [ ] Use webroot issuance so Certbot does not rewrite managed templates. Test candidate config with `nginx -t`, install atomically, and reload only on success. On failure preserve the previous active config. Never reference missing certificate files in the active bootstrap config.
- [ ] Enable the installed renewal timer and a deploy hook that validates and reloads Nginx. Verify with `certbot renew --dry-run`. Use absolute installed paths so later repository moves do not break renewal.
- [ ] Test missing certificates, invalid templates, unavailable upstreams, upload sizes, unauthorized file reads/writes, forged forwarded headers, and renewal-hook failure. Validate HTTP redirect and certificate trust from an external network after actual DNS/router activation.
- [ ] Commit the proxy/TLS deliverable.

Sources: [Nginx proxy directives](https://nginx.org/en/docs/http/ngx_http_proxy_module.html), [ACME challenge types](https://letsencrypt.org/docs/challenge-types/), [Certbot renewal](https://eff-certbot.readthedocs.io/en/stable/using.html#renewing-certificates).

## Task 5: Retire obsolete definitions and document migration/recovery

**Files:** Remove obsolete service Compose files, Chesskit build files, Homer assets/config, `compose/env.bkp`, personal interface configuration, shell profile templates, legacy cron file, old Nginx domain config, and unused Redis config. Update `README.md`, `docs/operations.md`, and `.gitignore`.

- [ ] Document old container/data inventory and backup locations before any shutdown. Preserve all host data and volumes; deleting tracked deployment definitions must not delete persisted storage.
- [ ] Remove credentials from tracked active files and examples. Document rotation of previously committed service credentials, Wi-Fi password, and any real Tailscale key. Removing files does not remove credentials from Git history; do not rewrite history without separate authorization.
- [ ] Document controlled cutover: back up old state; stop named old services only during deployment; start/verify new local services; configure owner/accounts; update DNS and router; issue certificates; activate public routes; test externally; then update LAN clients to Pi-hole.
- [ ] Document Pi-hole port-53 diagnosis and a deliberate resolver migration procedure; do not disable the host resolver automatically. Preserve a working DNS path during bootstrap and recovery.
- [ ] Document manual encrypted/off-host backup coverage for Copyparty data/config, Pi-hole data, Seerr config/database, local secrets, and TLS state. Stop database-writing services or use supported consistent backup mechanisms. Include restoration to a temporary location and validation before replacing live data.
- [ ] Document rollback as config/image restoration plus application data restoration when an upgrade performed a schema migration. Old image tags alone do not guarantee rollback compatibility.
- [ ] Search tracked files for obsolete domains, personal interface settings, and removed-service references; retain only intentional historical migration documentation. Review diffs without printing credentials.
- [ ] Commit the migration/documentation deliverable.

## Task 6: Add CI and verify the complete operator flow

**Files:** Create `.github/workflows/check.yml`; finalize tests and documentation.

- [ ] Run Bash syntax checks, ShellCheck, Python unit tests, and Compose validation using disposable dummy secrets. Pin reviewed CI actions to immutable revisions.
- [ ] Run disposable image/entrypoint checks and HTTP/proxy smoke tests. Do not require production DNS, certificates, router access, or private data in CI. Never publish resolved secret-bearing Compose output as an artifact.
- [ ] Exercise missing configuration, repeated setup, failed package installation, failed certificate issuance, partial container startup, and noninteractive invocation with finite timeouts.
- [ ] Document a clean-machine walkthrough and verify every advertised command. Public readiness requires external TLS, login, denied unauthenticated file access, upload/download, speed-test execution, LAN DNS, and a check that backend/admin ports are unreachable externally.
- [ ] Review the entire branch for service inventory, public access, data preservation, and instruction accuracy. Commit, push, open a PR with evidence and limitations, and report CI/mergeability. Do not claim live deployment from local checks.

## Separate follow-up: Immich

Immich deployment is excluded from this implementation so photo storage decisions do not block the Ohara foundation. Before that work, confirm hardware, actual host placement, disk paths/capacity, backup destination, and public hostname. Use the official release-matched Compose files, retain its required database/cache services, and pin a tested release. Keep PostgreSQL on local suitable storage. Use a dedicated subdomain and the upstream large-upload/WebSocket proxy configuration; do not install under a URL subpath. Back up both original media and database and prove a restore before treating it as the primary photo archive.

Sources: [recommended Compose installation](https://docs.immich.app/install/docker-compose/), [requirements](https://docs.immich.app/install/requirements/), [reverse proxy](https://docs.immich.app/administration/reverse-proxy/).

## Completion criteria

An unfamiliar agent can identify the desired services, configure a fresh supported host, run non-mutating checks, start the local stack, and explain the separate public-activation steps using repository documentation alone. Repeated setup preserves user configuration/data. No removed services are deployed. Backend web ports and DNS administration are not public. HTTPS renewal is verified when a real deployment environment exists. Homepage authentication is verified; external media integrations remain unconfigured unless tested.

## Approved scope update: 2026-10-15

The user selected gethomepage/homepage after the initial implementation. Add its
pinned container on loopback port 3002, seed operator-editable YAML configuration,
and route the HTTPS apex to it. Enable password authentication with private
generated credentials and rate-limit login attempts in Nginx. Do not mount the
Docker socket or configure API-key widgets. Preserve all existing configuration.
The user confirmed Immich will share this machine. The earlier separate-host
treatment was an assumption. Confirm hardware capacity, storage and backups
before implementing its own Compose project.
