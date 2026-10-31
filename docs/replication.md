# Replicate the deployment

Use the merged PRs in **both** repositories, not a copy of private one-off setup
scripts. Ohara provisions the media/dashboard stack and Nginx; the separate
[portfolio repository](https://github.com/xdadwal/xdadwal.in) runs its FastAPI app.

## Fresh installation

1. Prepare a supported Debian 13 or Ubuntu 24.04 system, persistent storage and
   backups. Clone Ohara, copy `.env.example` to `.env`, and set the real paths,
   UID/GID, timezone and certificate email. Set these non-secret routing values:

   ```dotenv
   DOMAIN=xdadwal.in
   HOMEPAGE_HOST=ohara.xdadwal.in
   PORTFOLIO_PORT=8010
   ```

   `PORTFOLIO_PORT=0` disables the optional apex portfolio route. Its nonzero value
   requires a separate dashboard hostname, and reserved application/admin ports
   are rejected. The portfolio process must listen on `127.0.0.1` at that port.

2. Create private credential files following [credentials.md](credentials.md).
   Supply your own values; never commit credentials or copy test fixtures.
   Follow [operations.md](operations.md) for `scripts/setup --dry-run`, actual
   setup, checks, startup and private account setup.

3. Clone/build the portfolio using its `deploy/README.md`. Install its systemd unit,
   changing its user, checkout and virtual-environment paths for the new machine.
   Confirm the portfolio responds at `http://127.0.0.1:8010` before TLS activation.

4. On a **fresh** media deployment, initialize accounts and connections:

   ```sh
   scripts/media-setup --owner-email YOUR_REAL_EMAIL
   ```

   For the selected Jellyfin appearance and Enhanced defaults, follow
   [Abyss setup](jellyfin-theme.md) and [Enhanced setup](jellyfin-enhanced.md).
   Install the reviewed Enhanced plugin version, fill the existing private API
   keys, then run `scripts/jellyfin-theme install` and
   `scripts/jellyfin-enhanced setup`. The Enhanced profile includes owner-selected
   automatic next-season requests and Seerr user import; review those before
   applying it to another server. Intro Skipper analysis is a separate UI task.

   Then explicitly apply the selected indexers and renaming settings:

   ```sh
   scripts/media-setup --profile ohara --profile-only
   ```

   This opt-in profile adds LimeTorrents, Nyaa.si and The Pirate Bay using the
   installed Prowlarr definitions, tests each new indexer before saving it, queues
   application sync, and enables movie/episode renaming without replacing naming
   formats. It does not duplicate/overwrite existing indexers or reset accounts.
   A failed operation may leave earlier steps complete; correct it and rerun.
   Check sync results in both applications. Currently LimeTorrents returns TV
   results but no movie-category results from this server, so only the other two
   synchronize to Radarr. Endpoint availability can differ on another network.

   Enabling indexers lets existing monitored requests run normally. This command
   does not manually submit a title or bypass indexer/category validation.

5. Set public DNS/forwarding for the new host, then use the GoDaddy DNS-01 workflow
   in [operations.md](operations.md#godaddy-dns-validation-and-wildcard-renewal).
   Fresh HTTPS rendering now includes both the dashboard and the optional
   loopback portfolio route. A wildcard A record does not grant permission to
   issue a certificate; supply a private GoDaddy PAT for automated validation.
   Staging certificates never replace production certificates.

6. Verify login, indexer/application tests, a permitted movie and episode request,
   completed download, import, playback over HTTPS and Seerr availability sync.
   [media.md](media.md) explains paths and acceptance. Unit/smoke tests cannot prove
   your real DNS, indexers or media acquisition work.

## Migrate the existing server instead

Make consistent, private backups of `.env`, essential `local/` files, application
state under `/ohara`, media, Nginx configuration and `/etc/letsencrypt`. Restore
with the correct ownership and adjust machine-specific paths. Keep the source
and destination from simultaneously writing the same databases.

The current Jellyfin administrator is `root`, preserved from the original server;
fresh initialization creates `admin`. Do not run initial setup over a restored
account/database expecting it to migrate or rotate credentials. Preserve
`local/media-state.json`; the `--profile-only` command can apply the non-secret
profile without repeating owner/media-server login initialization.
Run `scripts/migrate-credentials` first for legacy split inputs. After preparing
storage with setup, apply `scripts/media-setup --storage-only` and
`scripts/media-setup --quality-only` to restored accounts. See media.md for the
seeding, recycle-bin and bounded 1080p policies; these commands do not initialize
Jellyfin/Seerr owners. Storage setup applies the global four-hour cumulative seeding limit and
then stops torrents while preserving download files. Verify imports and hardlinks first; resume
reviewed stopped torrents manually as described in [media.md](media.md).

Recreate the portfolio service separately. Preserve or deliberately migrate
existing Nginx routes; DNS renewal configuration does not install new routes.
For an exact copy of this server's stable routes, including localhost and the
public-IP test, follow [the tracked Nginx baseline](../configs/nginx/deployed/README.md).
It requires the existing wildcard and local TLS materials at their documented
paths; the generic fresh-host templates intentionally do not assume those files.
Configure and test renewal on the target host. The currently deployed certificate
was issued with manual TXT validation; GoDaddy API renewal has not been activated
on this server and still requires a PAT and a successful live dry run.

Private state is transferred through backups, **never Git**. Historical migration
helpers archived under `~/ohara-backups` are recovery evidence, not fresh setup
dependencies. Keep the old host/data until the target passes acceptance checks.

For optional Maintainerr, follow [maintainerr.md](maintainerr.md) after the main
media stack is ready. Preserve its independent private state, use target-specific
LAN proxy/DNS settings, and connect existing application keys from private `.env`.
No deletion/retention rules are seeded by this repository.

For optional outgoing Letterboxd diary sync, follow
[jellyfin-letterboxd.md](jellyfin-letterboxd.md) and the reviewed artifact profile.
Install the exact plugin with the helper, restart only when playback is idle,
and let each owner link their external account privately in the plugin UI. Do
not seed external tokens, bulk backfills, incoming diary imports or Seerr requests.

## Optional Bambuddy

Use [Bambuddy setup](bambuddy.md) for the independently pinned Compose project,
dedicated storage, LAN proxy, exact DNS rewrite and Homepage Utility card. Confirm
storage on the new host and complete native owner/printer setup privately; do not
copy example printer identities, disable authentication, or start test prints.

## Other host-specific setup

Follow [agent-setup.md](agent-setup.md) for the complete selected-component
checklist: optional AdGuard/LAN admin routes, Immich Google-only invite-only
login, mergerfs mount guards, per-host watchdog identities and optional laptop
lid-close policy. Re-discover hardware/network identities on the target; never
copy this host's disk UUIDs, credentials or certificate/IP assumptions blindly.

## Optional ntfy notifications

Follow [ntfy.md](ntfy.md) and `scripts/ntfy` for the independently pinned server,
local storage outside the media pool, native deny-by-default topic authentication,
HTTPS, Homepage and exact AdGuard rewrite. The owner supplies NTFY_PASSWORD in
private .env. Ask whether the phone is Android or iPhone; enable the ntfy.sh iOS
wake-up relay only with explicit approval. No notification text is forwarded to
that relay. Verify the real supplied account before public proxy activation.
Install the host alert timer with `sudo scripts/ntfy install-alerts` after server
readiness; it reads the actual configured storage UUIDs and preserves the existing
storage watchdog. Run `scripts/ntfy test` and obtain owner confirmation of phone
delivery. Local publish success is not phone delivery or independent outage
detection; same-host monitoring cannot report a complete host/network outage.
Keep credentials out of Homepage, command arguments and logs.

For optional ntfy event monitoring and Seerr new-request notifications, follow
[host and application alerts](alerts.md). Reinstall the host worker after alert
changes and configure Seerr separately; preserve private inputs and alert state.
