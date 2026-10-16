# Working on Ohara

Ohara provisions a small Linux homeserver. Read README.md, docs/stack.md and docs/operations.md
before changing deployment behavior. The approved migration plan is under
docs/superpowers/plans/.

- Active applications: Seerr (Jellyseerr's successor),
  OpenSpeedTest, Homepage, Jellyfin, Radarr, Sonarr, Prowlarr, and qBittorrent. Nginx and Certbot run on the host. Domain: xdadwal.in.
- Homepage serves HOMEPAGE_HOST (ohara.xdadwal.in on this host) with password login;
  the separate portfolio service serves the apex; no Docker socket. Media widgets
  read application-issued API keys supplied in local/homepage.env. See docs/homepage-widgets.md.
  Immich will share this machine in its own Compose project; deployment is pending
  storage/hardware/backup details. See docs/immich-next.md.
  Media services are explicitly approved; follow docs/media.md. Do not introduce
  additional infrastructure or assume indexer/source credentials.
- Use independent per-service credentials; a shared authentication service is
  explicitly deferred. Read user-created credential files as documented in
  docs/credentials.md. Never invent or generate passwords, API keys or session
  secrets. If files/values are missing, ask the user to fill the private files;
  never request values in chat. Preserve inputs and keep values out of logs/Git.
- When tasked with initial setup, follow docs/agent-setup.md: inspect the target
  machine and existing configuration first, then ask only for missing facts or
  choices that cannot be safely inferred. Do not assume example IPs/emails are real.
  Continue independent checks while waiting; do not guess required answers.
- `compose.yaml`, `.env.example`, and `versions.env` define deployment;
  `.env` and `local/` are private. Never print secrets or resolved Compose config.
- Commands resolve their own repository path. Use `scripts/setup --help`,
  `scripts/check`, `scripts/up`, `scripts/status`, `scripts/media-setup --help`, and `scripts/tls --help`.
- Setup prepares a supported Linux host; `up` starts local services; TLS activation
  is a separate explicit step after owner/account setup. Do not deploy to a live
  host merely because a code change was requested.
- For media setup, confirm the real owner email and mounted media storage; run
  scripts/media-setup after local startup. Ask for chosen indexers and required
  external account/API credentials; never invent them. Credentials are in
  local/media-credentials; preserve the setup journal. Verify permitted movie/TV
  acquisition, import, playback and availability sync before declaring it ready.
- For existing media accounts, use `scripts/media-setup --storage-only` for storage
  policy, not the first-run owner flow. Follow docs/media.md recovery guidance.
  A completed command or cached Available label is not evidence of a present file:
  verify host/container paths, Radarr/Sonarr records and hardlink inode/device.
  Preserve source torrents; never redownload or delete library files to fix metadata.
- Public DNS records are managed at GoDaddy. No local DNS/filtering service is
  included. Backend web ports bind to loopback; only host Nginx uses public 80/443.
  Do not modify router/client DNS or delete retired DNS data during repo changes.
- Preserve configuration, volumes, existing files/ownership, unrelated Nginx sites,
  SSH access, networking, and host DNS. No recursive chown or destructive cleanup.
- Never execute dotenv contents. Add configuration validation before consumption.
- Verify with `python3 -m unittest discover -s tests -v`, `tests/test_setup.sh`,
  `tests/test_cli.sh`, and `tests/static.sh`. Docker smoke tests: `tests/smoke.sh`.
- Report static checks, disposable runtime checks, real Linux provisioning, and
  public reachability separately. One does not establish the others.
- Commit feature work, push its feature branch, and open a PR unless opted out.
  Never merge or rewrite Git history without authorization.
