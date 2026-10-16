# Deployment decisions

- Use Compose for applications and a small bootstrap for supported Linux hosts.
  Ansible would add machinery before there is recurring multi-host provisioning.
- Use host Nginx/Certbot with loopback backends: simple TLS renewal and no Docker
  socket exposure. UFW alone does not isolate published Docker ports.
- Adopt Seerr, the maintained successor to Jellyseerr and Overseerr, for a fresh
  installation. Upstream release announcement: https://docs.seerr.dev/blog/seerr-release/.
- Keep Copyparty and OpenSpeedTest; Pi-hole was subsequently removed. Remove the previous media download
  stack, monitoring, Tailscale, Chesskit, Homer, and standalone Redis definitions.
- Proposed names: seerr.xdadwal.in, files.xdadwal.in, speed.xdadwal.in.
  Configure in .env before issuance. The HTTPS apex runs Homepage with password
  authentication and a proxy rate limit on password attempts.
- Homepage was selected on 2026-10-15: gethomepage/homepage v2.5.0, pinned by
  digest, non-root, loopback port 3002. Start with service links, no Docker socket
  or API keys. Seed config only when absent and preserve operator edits.
- Immich will run on the same machine, as confirmed by the user, in a separate
  Compose project. Hostname is confirmed as immich.xdadwal.in. Storage, hardware capacity and
  backup destination remain to be configured. See immich-next.md.
- Seerr uses the included Jellyfin, Radarr and Sonarr. Prowlarr and qBittorrent
  provide indexer sync and downloads; chosen indexers and a permitted end-to-end
  request must still be verified before reporting fulfillment as ready.
- Bootstrap targets Ubuntu 24.04 and Debian 13, amd64/arm64 with systemd.
  This support target is distinct from evidence of installation on actual VMs;
  current verification and remaining deployment checks are in operations.md.

- Shared authentication (Authelia/Authentik) is deferred by user choice. Use
  user-managed per-service credentials from private input files. Initial setup
  agents collect only missing machine/account inputs using docs/agent-setup.md;
  reading credentials and provisioning application accounts are distinct steps.

## Media stack restored (2026-10-15)

The user explicitly approved the services needed to fulfill Seerr requests.
Jellyfin, Radarr, Sonarr, Prowlarr and qBittorrent are included locally; this
supersedes the earlier decision to remove media/download services. Jellyfin
uses jellyfin.xdadwal.in, while Seerr stays at seerr.xdadwal.in. Acquisition
UIs remain loopback-only. No indexer accounts, VPN, GPU or inbound peer ports
are assumed. Shared storage supports consistent paths and hardlinks.

## User-managed credentials (2026-10-16)

The user superseded automatic credential generation. All login passwords, the
three acquisition API keys, and Homepage's signing secret must come from
user-created private files. Setup validates and reads them; it never substitutes
generated defaults or recreates a missing file. See credentials.md. Normal
password-hash salts and application-issued tokens remain application internals.

## Pi-hole removed (2026-10-16)

The user does not need LAN DNS/filtering. Public domain records remain at GoDaddy.
Remove Pi-hole, its image, storage preparation, DNS-port checks, admin binding and
credential requirement. Retired LAN_IP and PIHOLE_PASSWORD input fields are ignored
for upgrades; existing containers/files and router/client resolver settings are
not changed by a repository update. See operations.md for deployed-host cutover.

## Copyparty removed (2026-10-16)

The user no longer needs file sharing. Remove Copyparty, its files hostname route,
image, mounts, credential requirement and setup artifacts. Keep eight application
containers and two user-created credential input files. Retired FILES_ROOT and
FILES_HOST inputs are ignored; existing data/config is preserved. See stack.md
for the current inventory and operations.md for deployed-host migration.

- On 2026-10-16, the user selected native Jellyfin/Seerr, resource, clock and
  weather widgets. These supersede the initial links-only/no-API-key dashboard.
  Use application-issued keys supplied privately, Open-Meteo browser location,
  and built-in container/storage readings; do not add a monitoring service.
  Preserve existing dashboard edits; see homepage-widgets.md.

- Resource widgets were simplified to CPU, RAM, uptime and one filesystem usage/total
  entry. OpenSpeedTest is a link-only card; its iframe and extra media monitoring
  mount were removed. Jellyfin, Seerr, clock and weather are retained.
