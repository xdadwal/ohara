# Working on Ohara

Ohara provisions a small Linux homeserver. Read README.md, docs/stack.md and docs/operations.md
before changing deployment behavior. The approved migration plan is under
docs/superpowers/plans/.

- Active applications: Seerr (Jellyseerr's successor),
  OpenSpeedTest, Homepage, Jellyfin, Radarr, Sonarr, Prowlarr, Lidarr, Bazarr, Navidrome, and qBittorrent (eleven applications). Nginx and Certbot run on the host. Domain: xdadwal.in.
- Homepage serves HOMEPAGE_HOST (ohara.xdadwal.in on this host) with password login;
  the separate portfolio service serves the apex; no Docker socket. Media widgets
  read application-issued API keys supplied in .env. See docs/homepage-widgets.md.
  Navidrome's Now Playing widget uses a Subsonic token derived locally from the
  existing NAVIDROME_PASSWORD; never forward that plaintext password to Homepage.
  Immich will share this machine in its own Compose project; deployment is pending
  storage/hardware/backup details. See docs/immich-next.md.
  Media services are explicitly approved; follow docs/media.md. Do not introduce
  additional infrastructure or assume indexer/source credentials.
- Use independent per-service credentials in the single private `.env`; a shared
  authentication service is explicitly deferred. Read `.env` as documented in
  docs/credentials.md. Never invent or generate passwords, API keys or session
  secrets. If files/values are missing, ask the user to fill the private files;
  never request values in chat. Preserve inputs and keep values out of logs/Git.
  Migrate legacy split files with `scripts/migrate-credentials` before setup/up;
  never source `.env` or pass the whole file to containers. Media setup preserves
  account state; changing input values alone does not rotate existing passwords.
- When tasked with initial setup, follow docs/agent-setup.md: inspect the target
  machine and existing configuration first, then ask only for missing facts or
  choices that cannot be safely inferred. Do not assume example IPs/emails are real.
  Continue independent checks while waiting; do not guess required answers.
- `compose.yaml`, `.env.example`, and `versions.env` define deployment;
  `.env` and `local/` are private. Never print secrets or resolved Compose config.
- Use `scripts/ohara doctor --json` for read-only maintainer diagnostics; warnings
  and skipped checks are unverified, not success. See docs/maintainer.md. Optional
  terminal tools use `scripts/ohara tools --dry-run` / explicit `--install`; do not
  rewrite dotfiles or launch unattended interactive monitors.
- Commands resolve their own repository path. Use `scripts/setup --help`,
  `scripts/check`, `scripts/up`, `scripts/status`, `scripts/media-setup --help`, and `scripts/tls --help`.
- Setup prepares a supported Linux host; `up` starts local services; TLS activation
  is a separate explicit step after owner/account setup. Do not deploy to a live
  host merely because a code change was requested.
- For media setup, confirm the real owner email and mounted media storage; run
  scripts/media-setup after local startup. Ask for chosen indexers and required
  external account/API credentials; never invent them. Credentials are in
  .env; preserve the setup journal. Verify permitted movie/TV
  acquisition, import, playback and availability sync before declaring it ready.
  Lidarr handles music acquisition directly and Navidrome handles music playback;
  Seerr has no music request flow. Fresh Jellyfin setup seeds only Movies/TV Shows.
  Preserve any existing Jellyfin Music library; the operator may hide/remove its
  library definition manually without deleting music files. Navidrome uses the
  supplied NAVIDROME_PASSWORD and supported first-run/login APIs, never a reset.
  NAVIDROME_HOST defaults to music.xdadwal.in; verify target DNS before activation. Ask for Bazarr
  subtitle languages/providers and any provider credentials; never assume them.
  Preserve existing Bazarr configuration and manually verify its connections.
  Lidarr (8686) and Bazarr (6767) stay private, without public admin subdomains.
  A future NAS/multiple-node topology is discussed, not implemented; these services
  run in the current Compose stack, with a future acquisition node intended.
- For existing media accounts, use `scripts/media-setup --storage-only` for storage
  policy, not the first-run owner flow. Follow docs/media.md recovery guidance.
  A completed command or cached Available label is not evidence of a present file:
  verify host/container paths, Radarr/Sonarr records and hardlink inode/device.
  Preserve source torrents; never redownload or delete library files to fix metadata.
  Disable managed Arr completed-download cleanup before applying qBittorrent
  seeding limits, because reaching a limit can immediately trigger source deletion.
- Use `scripts/media-setup --quality-only` for the bounded HD-1080p policy on
  existing accounts. Size definitions affect all profiles; preserve existing
  files and do not search/redownload to enforce future acquisition preferences.
- Optional remote SSH uses the host Tailscale client; see docs/tailscale.md and
  scripts/tailscale --help. Install only on an authorized target; enrollment
  requires the owner browser login, never generated auth keys. Use ordinary
  OpenSSH and preserve existing SSH keys. Do not enable Tailscale SSH, DNS
  acceptance, subnet routing, exit nodes, Serve or Funnel. Review existing
  client roles before changing preferences; restrict tailnet network policy to
  the intended SSH users/devices and port. No public SSH port forward.
- Public DNS records are managed at GoDaddy. No local DNS/filtering service is
  included. Backend web ports bind to loopback; only host Nginx uses public 80/443.
  Do not modify router/client DNS or delete retired DNS data during repo changes.
- `configs/nginx/deployed/` tracks the stable xdadwal.in host baseline, including
  localhost and public-IP routes. Keep it aligned with deliberate live changes;
  do not deploy host-specific certificate/IP assumptions to arbitrary fresh hosts.
- Preserve configuration, volumes, existing files/ownership, unrelated Nginx sites,
  SSH access, networking, and host DNS. No recursive chown or destructive cleanup.
- Never execute dotenv contents. Add configuration validation before consumption.
- Verify with `python3 -m unittest discover -s tests -v`, `tests/test_setup.sh`,
  `tests/test_cli.sh`, and `tests/static.sh`. Docker smoke tests: `tests/smoke.sh`.
- Report static checks, disposable runtime checks, real Linux provisioning, and
  public reachability separately. One does not establish the others.
- Commit feature work, push its feature branch, and open a PR unless opted out.
  Never merge or rewrite Git history without authorization.
