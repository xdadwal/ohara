# Media requests, downloads, and playback

Ohara includes the complete local stack:

| Application | Internal connection | Private host port | Role |
|---|---|---|---|
| Jellyfin | `http://jellyfin:8096` | 8096 | Playback, libraries, media login |
| Seerr | `http://seerr:5055` | 5055 | Discover and request movies/shows |
| Radarr | `http://radarr:7878` | 7878 | Movie acquisition and import |
| Sonarr | `http://sonarr:8989` | 8989 | Series acquisition and import |
| Prowlarr | `http://prowlarr:9696` | 9696 | Indexer management and sync |
| qBittorrent | `http://qbittorrent:8081` | 8081 | Downloads |

Only Jellyfin (`jellyfin.xdadwal.in`) and Seerr (`seerr.xdadwal.in`) have public
Nginx routes. Every backend host port binds to loopback. No peer, discovery, UPnP,
or DLNA ports are published. Normal outbound torrent connections work; inbound
peer connectivity is not configured. No VPN service or routing policy is assumed.

## Initial setup

Confirm actual media disk capacity, mount, backup destination, and owner email.
The optional `.env` keys `MEDIA_ROOT` and `JELLYFIN_HOST` default to
`DATA_ROOT/media` and `jellyfin.DOMAIN` for older configurations. Use a separate
media mount by setting MEDIA_ROOT explicitly. Its parent must already exist;
setup does not mount disks or recursively change existing ownership.

Create and fill the private input files in [credentials.md](credentials.md),
then run host setup and `scripts/up`. Your supplied media passwords and API keys
are read from `.env` (0600). The initial username is `admin`.
Jellyfin's password is also used for its Seerr media-server login, as required by
that integration; other services have separate passwords. Neither passwords nor
API keys are printed. Keep this recovery file in encrypted backups.

After all local services are ready, run as the checkout owner:

```sh
scripts/media-setup --owner-email your-real-email@example.com
```

The command uses local HTTP APIs to set the Radarr/Sonarr/Prowlarr admin accounts,
create qBittorrent movie/TV categories, configure download clients, root folders,
and Prowlarr application sync. It initializes Jellyfin with remote access enabled
and automatic port mapping disabled, adds Movies and TV Shows libraries, then
creates the Seerr owner using Jellyfin login and connects the default Radarr/Sonarr
servers. The initial request profile is **HD-1080p**, minimum movie availability
**released**, automatic searching enabled, and one copy of each title. Change
profiles deliberately in Seerr after setup. No source/indexer is chosen for you.

A private journal (`local/media-state.json`) records completed account setup.
Reruns preserve configured accounts, existing connections and library choices;
missing named connections are added. Do not remove the journal to rotate passwords.
If existing credentials differ or a default profile is unavailable, the command
stops for manual review. It is for first-run setup, not importing an old stack.
Back up and migrate existing databases deliberately before running it. An API
failure can leave earlier steps complete; fix the failing service and rerun.

Use SSH forwarding for private administration:

```sh
ssh -L 7878:127.0.0.1:7878 -L 8989:127.0.0.1:8989 \
    -L 9696:127.0.0.1:9696 -L 8081:127.0.0.1:8081 \
    -L 8096:127.0.0.1:8096 -L 5055:127.0.0.1:5055 user@server
```

Add your chosen indexers and any required account/API credentials in Prowlarr.
To reproduce this server's explicitly selected public indexers and enabled
renaming, run `scripts/media-setup --profile ohara --profile-only` after account
setup. This preserves existing accounts and naming formats; it does not invoke
the first-run Jellyfin/Seerr login flow. See [replication.md](replication.md) for
the selected indexers, category limitations and migration procedure.
Test each indexer and trigger application sync. Prowlarr sends indexers to both
Radarr and Sonarr; it is not a search provider itself. Do not treat healthy
containers or successful API connections as proof of working acquisition.
Only fetch content you have permission to access.

## Storage and connections

All three acquisition containers share **one `/data` bind mount**, preserving
consistent paths and allowing hardlinks/atomic moves when the filesystem supports
them. Do not create separate library/download bind mounts inside these containers.

```text
MEDIA_ROOT/
  downloads/incomplete/
  downloads/complete/movies/
  downloads/complete/tv/
  library/movies/
  library/tv/
  recycle-bin/movies/
  recycle-bin/tv/
```

Radarr root: `/data/library/movies`; Sonarr root: `/data/library/tv`.
Both use qBittorrent hostname `qbittorrent`, port **8081**, user-supplied password,
and category `movies` or `tv`. The listening and published Web UI ports both use 8081 for qBittorrent Host validation. Prowlarr
uses `http://radarr:7878` and `http://sonarr:8989` with their user-supplied API keys.
Seerr uses container names and ports from the table, with both defaults enabled.
If updating an existing Homepage deployment, remove any retired Copyparty link
and add the Jellyfin entry from
`configs/homepage/services.yaml` to your existing `${DATA_ROOT}/homepage/services.yaml`;
setup preserves that file and your customizations.

Jellyfin reads the library **read-only** at `/media/movies` and `/media/tv`;
its cache/transcodes use DATA_ROOT/jellyfin-cache, so reserve enough disk space
for transcoding.
Hardware transcoding needs a separate GPU/device permission configuration;
software transcoding is the initial default.

### Storage policy and existing installations

Initial media setup enables automatic torrent management for **new** torrents,
creates movie/TV categories with their matching completed-download paths, enables
Radarr/Sonarr hardlinks, and configures a seven-day recycle bin when none exists.
Custom recycle paths/retention are preserved. Recycle bins are outside Jellyfin's
library and are a recovery window, not a backup; explicit permanent deletion and
files removed outside Radarr/Sonarr can bypass them.

The selected qBittorrent policy stops seeding after completion (ratio and seeding
time limits zero, action Stop). It retains the torrent and downloaded files for
import/recovery. Storage setup applies the global default; existing per-torrent
share-limit overrides require separate review. This does not prevent uploading
pieces while a torrent is downloading.
The managed Radarr/Sonarr download clients disable completed-download removal so
reaching the seeding limit does not automatically delete the stopped torrent/source.

After updating an existing installation, run host setup to prepare the new
directories, then `scripts/media-setup --storage-only`. This skips owner/account
initialization and preserves credentials, torrents, naming formats and other
preferences. Existing category paths that differ from the expected paths require
manual review because changing them could relocate active torrents. Existing
manually managed torrents are not moved by this command. To migrate one, verify
its category and source first, then enable automatic management for that specific
torrent in qBittorrent and verify its new path, completion and library hardlink.

### Missing movie recovery and acceptance

The October 2026 Oppenheimer incident imported successfully, then Radarr logged
deletion of the movie and its library directory. qBittorrent retained the source;
Jellyfin and Seerr still advertised cached availability. The download's generic
completed path was a separate automatic-management setting issue, not the cause
of deletion. Logs established deletion but did not establish who initiated it.

Before repair, back up application settings and use supported application backups.
Check the actual file on the host and its mapped container path, download status,
movie record and import/deletion history. Re-add a missing movie using the same
TMDB identity/root/profile with automatic searching disabled. Use Radarr manual
import from the existing source with **Copy** and hardlinks enabled; preserve the
torrent and avoid another download. A DownloadedMoviesScan can complete without
importing: inspect the resulting movie file and manual-import decisions. For the
manual-import API, movieId without downloadId examines the library directory;
provide the correct downloadId when inspecting a download instead.

Verify both files exist, have the same device/inode and link count at least two;
confirm Radarr hasFile and its movie-file record. Refresh Jellyfin, wait for its
library scan, then run Seerr's Radarr and full Jellyfin scans. Confirm TMDB identity,
mapped path, availability and actual authenticated media reads. Browser playback
is a separate acceptance step; metadata counts alone do not establish playback.

Jellyfin has its own login. Create ordinary non-admin viewing accounts after setup;
use them for routine playback and requests. Seerr authenticates Jellyfin users,
so a separate shared login service is not needed. Review Seerr user permissions
and approval requirements before inviting anyone. Movie/show metadata needs
working internet access to upstream metadata services.

## Bounded 1080p downloads

Initial setup configures the HD-1080p profile used by Seerr in Radarr and Sonarr.
Existing installations can apply it with `scripts/media-setup --quality-only`.
It allows HDTV-1080p, WEB-DL, WEBRip and encoded Blu-ray 1080p, preserving the
existing source ordering and custom-format scores. Remux, raw/disc, 4K, 720p and
lower resolutions are disabled in this profile. Automatic upgrades are disabled
to avoid repeated downloads. No search, title reassignment, or file replacement
is triggered; existing large files are retained.

| Service | Minimum | Preferred | Maximum | Example maximum |
|---|---:|---:|---:|---|
| Radarr movies | 8 MB/min | 30 MB/min | 60 MB/min | ~7 GiB for 120 minutes |
| Sonarr episodes | 5 MB/min | 20 MB/min | 40 MB/min | ~1.8 GiB for 45 minutes |

These are Ohara's storage-conscious defaults, not a guarantee of visual quality.
Size definitions apply globally to these four qualities, including titles using
other profiles. Quality exclusions apply only to HD-1080p. Seerr's configured
default must continue selecting that profile; users choosing another profile can
change the exclusions. Limits scale with runtime; season packs and runtime
estimation can affect episode size calculations. Preferred size is a selection
hint, not a fixed download size or a guarantee of the smallest release.

Filtering happens in Radarr/Sonarr after indexer results arrive, so Prowlarr sync
cannot overwrite it. Both H.264 and HEVC remain eligible to preserve availability;
this policy does not guarantee direct play on every Jellyfin client. See the
[Radarr quality documentation](https://wiki.servarr.com/radarr/settings#quality)
and [Sonarr quality documentation](https://wiki.servarr.com/sonarr/settings#quality).

## Public activation and acceptance

Add a DNS A record for `jellyfin.xdadwal.in`, then rerun explicit TLS activation
so its certificate includes the new name. Only forward TCP 80/443. Before enabling
public routes, verify Jellyfin owner login and Seerr setup through the tunnel.
In Jellyfin Dashboard → Networking, set Known Proxies to the actual Docker bridge
gateway used by host Nginx (inspect the Ohara network locally). Trust that single
proxy address, not arbitrary networks, so forwarded client IPs work correctly.
Confirm external server URL in Seerr is `https://jellyfin.xdadwal.in`.

Verify a permitted test request travels Seerr → Radarr/Sonarr → qBittorrent,
completes, imports to the matching library, appears after a Jellyfin scan, and plays
through HTTPS. Check both a movie and a series episode. Check library availability
sync in Seerr. Indexer credentials and real download/playback acceptance remain
operator steps; no automatic external download is performed by repository tests.

Back up all application config directories, `.env`,
`local/media-state.json`, and media you cannot replace. Stop database writers or
use supported exports for consistent backups. Media images run directly as RUN_UID/RUN_GID using supported non-root operation,
so their initialization does not recursively change existing ownership. Ohara's
host setup also preserves existing directories. Review write access before startup.

References: [Seerr services](https://docs.seerr.dev/using-seerr/settings/services/),
[Jellyfin containers](https://jellyfin.org/docs/general/installation/container/),
[Radarr](https://docs.linuxserver.io/images/docker-radarr/),
[Sonarr](https://docs.linuxserver.io/images/docker-sonarr/),
[Prowlarr](https://docs.linuxserver.io/images/docker-prowlarr/),
[qBittorrent](https://docs.linuxserver.io/images/docker-qbittorrent/).

Storage API references: [qBittorrent Web API](https://github.com/qbittorrent/qBittorrent/wiki/WebUI-API-%28qBittorrent-5.0%29),
[Radarr manual import controller](https://github.com/Radarr/Radarr/blob/develop/src/Radarr.Api.V3/ManualImport/ManualImportController.cs),
[Seerr settings and scan jobs](https://github.com/seerr-team/seerr/blob/develop/server/routes/settings/index.ts).
