# Jellyfin LetterboxdSync

The selected plugin is **Gizmo091/LetterboxdSync 2.2.0.0**, not Jellyscribe or a
watchlist-only integration. The reference blog's `main/manifest.json` URL returns
404. The upstream repository uses `master`; the reviewed manifest is recorded in
`configs/jellyfin/letterboxd-sync.json` with release/archive and assembly SHA-256
hashes and source commit. The upstream minimum ABI is 10.11.9.0; this artifact was
loaded successfully on the exact official Jellyfin 12.2 image used here.

## Installation and verification

Use the existing administrator API key in private `.env`
(`HOMEPAGE_VAR_JELLYFIN_API_KEY`):

```sh
scripts/jellyfin-letterboxd install
# When no playback session is active:
scripts/jellyfin-letterboxd install --restart
scripts/jellyfin-letterboxd check
```

The helper verifies the reviewed public release, preserves all existing plugin
repositories, adds only the correct upstream repository and installs the exact
version through Jellyfin's package API. It verifies the installed DLL before
activation. Different installed versions/states are rejected for review, never
replaced automatically. Repository/plugin snapshots are private under
`local/jellyfin-letterboxd-backups/`. Jellyfin's existing plugin-update policy is
not changed; review new releases and this profile before using the helper after
an update. This is not a new Compose service, domain, Homepage card or DNS record.

`--restart` refuses to interrupt any session with media loaded. When permitted,
it recreates only Jellyfin using the existing pinned image, persistent config,
media mounts and read-only Abyss overlay. A plugin already queued by the owner
(such as an Intro Skipper update) may also activate during this restart. No other
service is restarted. The helper never submits sync/import/request tasks.

## Owner account linking

Open https://tv.xdadwal.in and use **Dashboard → Plugins → LetterboxdSync**.
The direct admin configuration page is:
`/web/index.html#/configurationpage?name=configLetterboxd`.

1. Select the intended Jellyfin user.
2. Enter that user's Letterboxd **username**, rather than their email address,
   and password directly in the HTTPS plugin UI. Do not send credentials in chat
   or add another user's credentials to the repository. The application exchanges
   credentials with Letterboxd for a refresh token; its current authentication
   implementation clears the password after successful authentication.
3. Choose the date-filter/lookback before enabling the account: upstream defaults
   can sync the full watched history. Enable only the desired outgoing diary sync
   and save. Each Jellyfin user links their own account.
4. Verify one deliberate watch in Letterboxd after the owner enables syncing.
   A loaded plugin or readable settings page is not proof of external sync.

Accounts start empty. Seerr integration is left unconfigured; watchlist auto-
request and incoming diary import are not enabled by setup. No external account
passwords/tokens are assumed or copied from another service. Additional optional
sync directions, likes/ratings and backfills are owner choices.

No File Transformation dependency is needed for the administrator plugin page.
Its optional non-admin sidebar integration requires that separate plugin; it is
not installed by this task and the read-only web image is not patched for it.

## Operation and recovery

The plugin offers real-time playback sync plus three scheduled tasks: outgoing
played-media sync, Letterboxd diary import and watchlist sync. These only act on
configured accounts/options. Account/token state belongs to persistent Jellyfin
configuration; preserve it and all application state during upgrades or removal.
Do not mark real movies played just to test deployment.

To disable/remove, use Dashboard → Plugins for LetterboxdSync only, then restart
when playback permits. Leave other repositories/plugins and media untouched.
The helper does not reset accounts or delete configuration on failure. Keep
private snapshots/token-bearing state with the existing application-state backup
policy; no independent backup/restore test is claimed here.

Validation distinguishes artifact integrity, disposable Jellyfin loading and
configuration/task availability, live activation, UI account linking and actual
Letterboxd posting. The install does not claim the final two before owner linking.

References: [upstream setup](https://github.com/Gizmo091/jellyfin-plugin-letterboxd-sync),
[reference guide](https://jellywatch.app/blog/jellyfin-letterboxd-sync-plugin-guide-2026).
