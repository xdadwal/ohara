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
  manual Remove from Continue Watching control. Only these five personal fields
  change for current users; subtitles, shortcuts, auto-skip and other choices stay.
- Native Home tabs for Bookmarks, Calendar and Requests. Existing Plugin Pages or
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
  setup checks linkage but does not import accounts or grant permissions.
- Calendar library-access filtering and request-owned download filtering; download
  history is restricted to administrators.
- The pinned Abyss Enhanced stylesheet is served locally as `/web/ui/abyss-je.css`
  and imported after core Abyss when the theme is active. Upstream labels this
  stylesheet for Enhanced 11.3; it uses shared panel selectors, so review its look
  in the installed 12.13 client. Theme selectors and existing branding are retained.

Automatic requests, watchlist sync, tag/metadata synchronization, analytics,
subtitle language/providers, Intro Skipper policies and unrelated plugin settings
are not changed. Features requiring extra external keys, such as TMDB/Elsewhere,
MDBList and DoesTheDogDie, remain governed by existing inputs; none are invented.

## Verify and use

Hard-refresh https://tv.xdadwal.in after saving. Press **?** outside a text field
to open the Enhanced panel, or use the avatar menu in the Modern layout. Selected
personal QoL settings can be changed there; opening Bookmarks, Calendar and
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
