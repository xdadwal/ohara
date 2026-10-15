# Deployment decisions

- Use Compose for applications and a small bootstrap for supported Linux hosts.
  Ansible would add machinery before there is recurring multi-host provisioning.
- Use host Nginx/Certbot with loopback backends: simple TLS renewal and no Docker
  socket exposure. UFW alone does not isolate published Docker ports.
- Adopt Seerr, the maintained successor to Jellyseerr and Overseerr, for a fresh
  installation. Upstream release announcement: https://docs.seerr.dev/blog/seerr-release/.
- Keep Pi-hole, Copyparty, and OpenSpeedTest. Remove the previous media download
  stack, monitoring, Tailscale, Chesskit, Homer, and standalone Redis definitions.
- Proposed names: requests.xdadwal.in, files.xdadwal.in, speed.xdadwal.in.
  Configure in .env before issuance. Apex remains a maintenance response.
- Homepage selection is open. Immich is a separate follow-up: confirm which
  machine, storage, backup destination, and hostname before deploying it.
- Seerr requires media-server setup; automatic fulfillment also needs external
  Radarr/Sonarr. None are supplied here; do not report fulfillment as ready.
- Bootstrap targets Ubuntu 24.04 and Debian 13, amd64/arm64 with systemd.
  This support target is distinct from evidence of installation on actual VMs;
  current verification and remaining deployment checks are in operations.md.
