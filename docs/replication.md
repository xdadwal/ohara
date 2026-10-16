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
Jellyfin/Seerr owners.

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
