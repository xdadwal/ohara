# Jellyfin Enhanced quality-of-life setup

The owner installed Jellyfin Enhanced **12.13.0.0** and Intro Skipper **12.0.5.0**.
Enhanced is active on Jellyfin 12 and its request-time middleware already injects
one script alongside the persistent Abyss/Spotlight overlay. A writable web image,
File Transformation, Plugin Pages and Custom Tabs are not required for this setup.

The reviewed non-secret profile is `configs/jellyfin/enhanced-qol.json`.
After installing the matching plugin through Jellyfin's plugin dashboard:

```sh
scripts/jellyfin-enhanced setup
scripts/jellyfin-enhanced check
```

No sudo command or additional container/service is needed. Setup uses the
existing administrator API key from private `.env`, plus
HOMEPAGE_VAR_SEERR_API_KEY, SONARR_API_KEY and RADARR_API_KEY. Connection tests run
through Jellyfin, so they verify Docker service addresses from the actual plugin.
Existing secret values stay out of Git/output/browser configuration. The plugin
stores necessary integration keys in its existing private server configuration;
`.env` remains the editable source for these keys. No credentials are generated.

## Configured features

- Watch progress, file sizes, quality badges, long-press playback speed and the
  manual Remove from Continue Watching control, with remaining-time progress. Only
  these thirteen personal fields change for current users; other saved choices stay.
- Native Home tabs for Recommendations and Requests; Bookmarks and Calendar are
  disabled, matching the owner's latest dashboard settings. Existing Plugin Pages or
  Custom Tabs navigation is retained rather than enabling conflicting native tabs.
- Server-side Seerr at `http://seerr:5055`, Sonarr at `http://sonarr:8989` and
  Radarr at `http://radarr:7878`, with HTTPS browser mappings under DOMAIN.
  Existing additional instances/mappings are preserved. Conflicting Seerr or
  disabled matching Arr connections are rejected for operator review.
- Administrator-only Arr/Bazarr links to the existing LAN-only admin hostnames.
  Bazarr is a browser link, not a plugin API integration. External clients retain
  the existing Nginx restrictions on these admin services.
- Seerr issue reporting/indicators and debounced recently-added availability sync.
  Existing account linkage/permissions/quotas remain Seerr's responsibility;
  setup checks linkage without issuing an import call or modifying permissions.
  The owner-enabled automatic Seerr user-import setting is retained in the profile;
  subsequent plugin activity can import users according to Seerr policy.
- Calendar library-access filtering and request-owned download filtering; download
  history is restricted to administrators.
- The pinned Abyss Enhanced stylesheet is served locally as `/web/ui/abyss-je.css`
  and imported after core Abyss when the theme is active. Upstream labels this
  stylesheet for Enhanced 11.3; it uses shared panel selectors, so review its look
  in the installed 12.13 client. Theme selectors and existing branding are retained.

The latest owner-selected server defaults also enable intro/outro auto-skip,
unwatched-only random selection, awards, rating/genre tags, hiding tags on hover,
Letterboxd links, advanced Seerr controls, Recommendations and series-overview
spoiler stripping. Player ratings are disabled. Rating source order is
Letterboxd/TMDB/Rotten Tomatoes/IMDb; this does not enable MDBList fetching or
supply a missing key.

Automatic next-season requests and the requirement that all episodes be watched
are enabled, matching the live owner settings. Movie auto-requests, watchlist sync,
tag/metadata synchronization, analytics, subtitle language/providers, Intro
Skipper analysis policies and unrelated settings are preserved. Enhanced auto-skip
needs detected media segments; it does not generate timestamps or start analysis.
Features requiring extra external keys, such as TMDB/Elsewhere,
MDBList and DoesTheDogDie, remain governed by existing inputs; none are invented.

## Verify and use

Hard-refresh https://tv.xdadwal.in after saving. Press **?** outside a text field
to open the Enhanced panel, or use the avatar menu in the Modern layout. Selected
personal QoL settings can be changed there; opening Recommendations and
Requests verifies the actual client experience. No media requests or downloads
are submitted by setup/testing.

`check` validates plugin/host version compatibility, integration connectivity,
public-key redaction and Seerr account linkage. A global server API key has no
user-bound identity: the plugin's Calendar endpoint needs a real user session
when library filtering is enabled. Do not disable filtering to make an API-key
probe pass. User-scoped pages and playback behavior need a logged-in browser
check; successful connection tests alone do not prove acquisition or playback.

## Backups and rollback

Each setup snapshots server configuration, branding and all current users'
Enhanced preference documents privately under `local/jellyfin-enhanced-backups/`.
Existing bookmarks, hidden-content and spoiler-state files are not replaced.
Failed application attempts restore touched settings where possible and identify
the backup on rollback failure. Concurrent administrator config changes detected
before application abort without overwriting them.

To deliberately restore a selected snapshot (including its saved integration
keys and user preferences):

```sh
scripts/jellyfin-enhanced restore --backup TIMESTAMP_DIRECTORY_NAME
```

Review the snapshot date first: restoration replaces those saved settings and can
undo changes made after that snapshot. The generated theme files remain in place;
no libraries, media, plugins or account passwords are deleted/reset. Keep these
backups private and include them with application-state backups.

References: [upstream setup](https://n00bcodr.github.io/Jellyfin-Enhanced/getting-started/),
[API](https://n00bcodr.github.io/Jellyfin-Enhanced/advanced/api/) and
[*arr settings](https://n00bcodr.github.io/Jellyfin-Enhanced/arr/arr-settings/).

## Sync scope

The checked-in profile records reviewed non-secret choices changed since the initial
Enhanced setup. Integration URLs are derived from the target configuration and keys
come from private `.env`; instance JSON, API keys, user IDs, per-user navigation
history, bookmarks and cached state are not exported. Existing users keep personal
overrides outside the thirteen selected fields. New users receive plugin server defaults.
Run the setup command explicitly after plugin installation; ordinary `scripts/up`
does not reapply preferences or enable request automation.

## Rating tags for existing accounts

Server defaults are starting values, not a forced policy. Enhanced saves personal
preferences on first use; changing the admin default later leaves those values
intact. The setup profile therefore selectively sets RatingTagsEnabled and its six
movie/series/season/episode/Continue Watching/Next Up scope switches for current
accounts as well as server defaults. The thirteen managed fields include the
previous six QoL choices; all other personal preferences are preserved. Clients
must refresh to reload their saved settings. Users can subsequently customize them.

In the UI, personal UI Settings controls rating tags. The administrator's Overview
→ Quick Actions → Overwrite everyone's personal settings is a broader reset that
also replaces unrelated preferences; it is not used by this setup. Server defaults
alone and clearing tag caches do not fix a saved personal false value.

Badges require community/critic rating metadata. A movie or season without ratings
can have no badge even with every scope enabled. MDBList fetching is independent
and remains disabled without an owner-supplied key. These are Enhanced web overlays;
experimental Native Poster Tags are separate and are not enabled by this fix.
