# Working on Ohara

Ohara provisions a small Linux homeserver. Read README.md, docs/stack.md and docs/operations.md
before changing deployment behavior. The approved migration plan is under
docs/superpowers/plans/. For future service additions, follow
[docs/adding-services.md](docs/adding-services.md), including live Homepage/AdGuard
integration, exact privileged commands and LAN-only owner onboarding where needed.

- Active applications: Seerr (Jellyseerr's successor),
  OpenSpeedTest, Homepage, Jellyfin, Radarr, Sonarr, Prowlarr, Lidarr, Bazarr, Navidrome, and qBittorrent (eleven applications). Nginx and Certbot run on the host. Domain: xdadwal.in.
- Homepage serves HOMEPAGE_HOST (ohara.xdadwal.in on this host) with password login;
  the separate portfolio service serves the apex; no Docker socket. Media widgets
  read application-issued API keys supplied in .env. Selected queue/torrent/DNS
  widgets use narrow runtime aliases for existing Arr keys and qBittorrent/AdGuard
  credentials; no other account passwords are forwarded. See docs/homepage-widgets.md.
  Navidrome's Now Playing widget uses a Subsonic token derived locally from the
  existing NAVIDROME_PASSWORD; never forward that plaintext password to Homepage.
  Immich is implemented as an optional separate Compose project with machine
  learning disabled; owner onboarding is complete and public HTTPS is active.
  Homepage has its link and native statistics widget using the privately supplied
  HOMEPAGE_VAR_IMMICH_API_KEY (server.statistics). The owner verified Google
  login and accepted capacity for the current single-user release. Independent
  backups/restore testing are explicitly deferred by the owner; do not treat
  them as release blockers or claim they are implemented.
  Use scripts/immich and docs/immich.md; preserve its independent
  database/cache and stable /data container path. Google OAuth must remain
  invite-only (autoRegister=false), with Google-only login and password login
  disabled by operator request. Pre-create approved users by exact Google email;
  leave their password fields empty and disable required password change. Use
  scripts/immich oauth and docs/immich-google-oauth.md; actual Google client inputs
  belong only in private .env, never in the versioned JSON or Homepage.
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
  Jellyfin's approved optional Abyss theme includes a persistent read-only web
  overlay and Spotlight; use scripts/jellyfin-theme and docs/jellyfin-theme.md.
  Preserve existing branding and user preferences. Refresh the generated index
  after changing its image pin; do not patch a running container's web files.
  The owner-installed Enhanced plugin is configured with scripts/jellyfin-enhanced
  and docs/jellyfin-enhanced.md; preserve its private integrations and unrelated
  personal preferences. The owner-approved synced profile includes automatic
  next-season requests (all watched required) and Seerr automatic user import.
  Do not add other request automation or directly import/grant users during setup.
  Existing Intro Skipper analysis policies are preserved.
  Optional LetterboxdSync uses scripts/jellyfin-letterboxd and
  docs/jellyfin-letterboxd.md; preserve all accounts and repositories, verify the
  reviewed artifact, and never restart with playback loaded. External account
  linking stays in its HTTPS UI; do not enable imports/requests or assume tokens.
  Lidarr (8686) and Bazarr (6767) stay private, without public admin access.
  LAN-only administration subdomains for these and the other internal services
  are explicitly approved; follow docs/lan-services.md and scripts/lan-proxy.
  A future NAS/multiple-node topology is discussed, not implemented; these services
  run in the current Compose stack, with a future acquisition node intended.
- For existing media accounts, use `scripts/media-setup --storage-only` for storage
  policy, not the first-run owner flow. Follow docs/media.md recovery guidance.
  A completed command or cached Available label is not evidence of a present file:
  verify host/container paths, Radarr/Sonarr records and hardlink inode/device.
  Preserve source torrents during metadata repair; never redownload or delete library
  files to fix metadata. The selected storage policy seeds for 4320 minutes, then
  qBittorrent removes torrents/download files; ratio/inactivity limits are disabled.
  Review imports/hardlinks before applying it; resume stopped torrents deliberately.
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
- Public DNS records are managed at GoDaddy. Optional AdGuard Home is explicitly
  approved for LAN DNS/filtering in the separate compose.adguard.yaml project;
  follow docs/adguard.md and scripts/adguard. DNS binds the verified reserved LAN
  IPv4 with a LAN client allowlist; dashboard 3003 stays loopback. Never publish
  DNS to the Internet or enable AdGuard DHCP. Preserve existing config/accounts.
  Optional Maintainerr is approved as the separate compose.maintainerr.yaml project;
  use scripts/maintainerr and docs/maintainerr.md. It has no login: keep the full
  UI/API LAN-only. Reuse existing private application keys, preserve its state,
  and create no cleanup rules or destructive actions without an owner policy.
  Backend web ports bind to loopback; only host Nginx uses public 80/443.
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
