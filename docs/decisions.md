# Deployment decisions

- Use Compose for applications and a small bootstrap for supported Linux hosts.
  Ansible would add machinery before there is recurring multi-host provisioning.
- Use host Nginx/Certbot with loopback backends: simple TLS renewal and no Docker
  socket exposure. UFW alone does not isolate published Docker ports.
- Adopt Seerr, the maintained successor to Jellyseerr and Overseerr, for a fresh
  installation. Upstream release announcement: https://docs.seerr.dev/blog/seerr-release/.
- Keep Pi-hole, Copyparty, and OpenSpeedTest. Remove the previous media download
  stack, monitoring, Tailscale, Chesskit, Homer, and standalone Redis definitions.
- Proposed names: watch.xdadwal.in, files.xdadwal.in, speed.xdadwal.in.
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
  agent-generated unique per-service credentials. Initial setup agents collect
  only missing machine/account inputs using docs/agent-setup.md; generated
  credentials and application account provisioning are distinct steps.

## Media stack restored (2026-10-15)

The user explicitly approved the services needed to fulfill Seerr requests.
Jellyfin, Radarr, Sonarr, Prowlarr and qBittorrent are included locally; this
supersedes the earlier decision to remove media/download services. Jellyfin
uses jellyfin.xdadwal.in, while Seerr stays at watch.xdadwal.in. Acquisition
UIs remain loopback-only. No indexer accounts, VPN, GPU or inbound peer ports
are assumed. Shared storage supports consistent paths and hardlinks.
