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
3. Leave **Enable** and **Enable real-time sync** disabled for this release.
   See the duplicate-entry incident below before enabling any outgoing sync.
   Each Jellyfin user links their own account.
4. A loaded plugin or readable settings page is not proof of correct external
   sync. Do not use a real account to test duplicate handling.

Accounts start empty. Seerr integration is left unconfigured; watchlist auto-
request and incoming diary import are not enabled by setup. No external account
passwords/tokens are assumed or copied from another service. Additional optional
sync directions, likes/ratings and backfills are owner choices.

No File Transformation dependency is needed for the administrator plugin page.
Its optional non-admin sidebar integration requires that separate plugin; it is
not installed by this task and the read-only web image is not patched for it.

## Operation and recovery

### Duplicate-entry incident (2026-10-25)

The owner reported duplicate diary entries and old watched movies being added
again after linking their account. Both outgoing account switches were disabled
through Jellyfin's configuration API, preserving account tokens and other options;
readback confirmed them disabled and all three tasks idle. The original settings
were saved privately under `local/jellyfin-letterboxd-backups/*-pause-sync/`.
No Letterboxd entries or Jellyfin watch history were deleted or changed.

Source review of upstream v2.2.0 found:

- The daily played-media task queries the full watched movie library on every
  run unless the account date filter is enabled. It was disabled on this account.
- The shared movie logger unconditionally posts a diary entry and relies on an
  assumed server-side duplicate response. There is no persistent per-watch sync
  checkpoint or existing-entry check. Missing last-played dates become today.
- Real-time sync reacts to playback completion and manual watched toggles. It
  uses the same logger without applying the account date filter.

Logs contained repeated success messages for two movie/date pairs. These messages
alone do not prove new remote entries: the logger also reports success for the
API's presumed already-present response. The owner's duplicate report and the
missing guards mean successful installation must not be treated as safe sync.

Keep outgoing sync paused until a reviewed implementation checks existing remote
entries and handles repeated/concurrent submissions safely. A lookback filter
alone does not fix duplicates. Do not restore the pre-pause snapshot wholesale,
because it re-enables outgoing sync. Any remote cleanup requires a reviewed list
of entries and explicit owner approval; preserve originals and legitimate rewatches.

Reviewed source: [scheduled sync](https://github.com/Gizmo091/jellyfin-plugin-letterboxd-sync/blob/v2.2.0/LetterboxdSync/LetterboxdSyncTask.cs),
[shared logger](https://github.com/Gizmo091/jellyfin-plugin-letterboxd-sync/blob/v2.2.0/LetterboxdSync/LetterboxdMovieSync.cs),
[real-time events](https://github.com/Gizmo091/jellyfin-plugin-letterboxd-sync/blob/v2.2.0/LetterboxdSync/RealtimeSyncService.cs).

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
