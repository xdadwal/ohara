# Homepage widgets

Fresh installations seed media, queue, torrent and DNS widgets, plus clock,
weather and resource widgets. Missing optional services/credentials can leave
those optional widgets disconnected until their setup is completed.
OpenSpeedTest is a link-only card opening an on-demand browser-to-Ohara test. No new services are added.
Existing files under DATA_ROOT/homepage are deliberately preserved by setup.

AdGuard and media administration cards use LAN-only HTTPS subdomains under
HOMEPAGE_VAR_DOMAIN (supplied from DOMAIN). On this host, install the reviewed
[LAN Nginx routes](lan-services.md) and local DNS rewrites before using them.
Backends remain on loopback; SSH forwarding is still an alternative. Selected administration cards now have native widgets using the narrowly
allowlisted credentials below. Other administration links remain link-only.

## Connect media widgets

Navidrome has a native **Now Playing** widget. It shows active tracks and their
artist/album/user, or "Nothing streaming" when idle. It does not provide library
counts or configurable fields.

The template connects privately to `http://navidrome:4533` as `admin` using
Subsonic token authentication. Project commands derive
`HOMEPAGE_VAR_NAVIDROME_TOKEN` locally as MD5 of the existing `NAVIDROME_PASSWORD`
plus the fixed non-secret salt `ohara-homepage`. The password remains only in
the unified private `.env`; it is not passed into Homepage. No additional secret
input or credential file is needed. Use scripts/up after changing the actual
Navidrome password and synchronizing `.env`, to refresh the derived token.

On an existing dashboard, merge only the Navidrome widget block from
`configs/homepage/services.yaml` into its existing service card. Preserve the
other cards/widgets. Recreate Homepage with scripts/up to load the token.
Verify login and its `getNowPlaying` widget API; an idle response is successful.
See [Homepage's Navidrome widget](https://gethomepage.dev/widgets/services/navidrome/).

Complete media setup first, then copy the actual application-issued keys into
.env using a private editor. Keep mode 0600; never send keys in chat,
commit them, invent replacements, or use the Jellyfin account password as an API key.

- Jellyfin: Dashboard > Advanced > API Keys. Add
  HOMEPAGE_VAR_JELLYFIN_API_KEY with the application's key.
- Seerr: Settings > General > API Key. Add HOMEPAGE_VAR_SEERR_API_KEY with that key.

The commented entries in .env.example show the names.
They are optional during bootstrap because the applications must be initialized
first. Missing keys leave the corresponding widgets disconnected; links and
Homepage login still work. After adding keys, run scripts/check and scripts/up
so Compose recreates Homepage with the updated environment. Do not print resolved
Compose output. Widget API calls use internal Docker addresses; no extra public
ports or Docker socket are needed.

Jellyfin shows movie/series/episode counts and Now Playing, with usernames and
playback controls hidden. Its version 2 widget matches the pinned Jellyfin 12.2.
Seerr shows pending requests, processing requests and issues. Everyone with access
to the dashboard can see these widgets' information.

## Clock and weather

The clock uses the browser's local timezone. Open-Meteo uses metric units and a
15-minute cache, without an API key or another container. By default it requests
browser location permission over HTTPS. For a fixed location or if permission is
denied, edit DATA_ROOT/homepage/widgets.yaml and add latitude, longitude, timezone
and an optional label beneath openmeteo. Do not guess an operator's location.
Weather requires outbound access to Open-Meteo.

## Resources and storage

The resource strip shows CPU, RAM, uptime and one disk entry, polling every
10 seconds. CPU/RAM/uptime readings are provided from Homepage's container
context; this is not a complete host monitoring system.

The disk entry measures `/media-storage`, a read-only container bind of
`MEDIA_ROOT`. On this host it reports the mergerfs pool at `/ohara/mnt`, rather
than Homepage's configuration filesystem on the internal SSD. It shows total
filesystem capacity and used space, not just media file sizes. The internal branch
shares capacity with the operating system. With `MEDIA_POOL_MOUNT` set, Homepage
also joins the pool-dependent startup unit; no Docker socket is exposed.

## Temperature readings

The Resources widget enables `cputemp: true`. On the current host, Homepage's
existing systeminformation dependency reads the CPU sensors without any extra
bind mount, device access, capabilities or Docker socket. The authenticated
`/api/widgets/resources?type=cputemp` response returned real CPU/core values
(52 degrees Celsius at verification). Availability is hardware-dependent; do not
substitute a fabricated reading when a new host has no supported sensors.

The host also exposes an NVMe temperature sensor. Individual drive temperatures
are not supplied by the native Resources disk-capacity widget. USB drive sensors
need SMART passthrough checks and a separate monitoring integration before they
can be displayed. Read-only diagnostics using Debian smartmontools 7.4-3 returned 34 degrees Celsius
for the Samsung NVMe and 44 for the WD HDD. The Crucial USB query was slow and
terminated without a usable reading; passthrough support is unverified. Do not
periodically retry this adapter until its behavior is understood. The diagnostics
used a privately unpacked Debian package, not an installed monitoring daemon.
No persistent drive collector is installed by this change.

## Existing installations

Back up DATA_ROOT/homepage/services.yaml and widgets.yaml. Merge the selected
widget sections from configs/homepage into those files, preserving custom links,
weather location and other edits. Set the Resources disk target to `/media-storage`
when applying this storage update; preserve the other widget settings. Do not
overwrite them automatically. Update the
checkout/Compose definition and recreate Homepage with scripts/up, then refresh
Homepage. Remove the OpenSpeedTest widget block while retaining its href, and
replace the two resource sections with the single section in the seed file.
The retired /monitor/media Compose mount is removed when Homepage is recreated.
Verify login, native widget values and filesystem capacity. Allow browser
geolocation or configure coordinates and verify weather. Local container tests
do not verify browser permission prompts, visual layout or host-wide telemetry.

## MySpeed and bandwidth direction

MySpeed runs tests from its host using Ookla, LibreSpeed or Cloudflare clients.
Its development branch supports a custom LibreSpeed endpoint, so a third-party
server is not mandatory. This measures MySpeed-host-to-endpoint bandwidth, not
visitor-browser-to-Ohara bandwidth. Running it on Ohara against Ohara itself would
not measure the visitor's network. A remote peer running MySpeed could target an
Ohara-hosted LibreSpeed server, but that would require software on the peer and a
LibreSpeed deployment. This capability was inspected in development source and
is not a claim about every released MySpeed image.

Keep OpenSpeedTest for the current browser-to-server requirement. LibreSpeed is
an alternative if changing the interactive test's appearance later.

Sources checked 2026-10-16:
- https://gethomepage.dev/widgets/services/jellyfin/
- https://gethomepage.dev/widgets/services/seerr/
- https://gethomepage.dev/widgets/info/resources/
- https://gethomepage.dev/widgets/info/openmeteo/
- https://github.com/gnmyt/MySpeed/blob/development/server/util/speedtest.js

## Immich link

The Images & Videos section in the seed contains a plain link to
`https://immich.{{HOMEPAGE_VAR_DOMAIN}}`. It needs no API key or shared Docker
network. On an existing dashboard, merge only this section after the optional
Immich instance and HTTPS route are verified. Preserve the rest of services.yaml,
including embedded widget credentials; do not print or replace the entire file.
The current host has this live link, added selectively with a private backup;
Homepage password login and the authenticated service-card response were verified.
Immich currently serves LAN-only owner onboarding.

### Immich statistics widget

The seed and current live card use the native Immich widget version 2 with photo
count, video count and total storage usage; the user count is hidden. Create an application-issued API key in Immich Account Settings > API
Keys with only server.statistics permission, then place it privately in .env as
HOMEPAGE_VAR_IMMICH_API_KEY. This optional key is allowlisted only to Homepage;
it is never injected into Immich, database or media container environments. Never put the
actual key in services.yaml or Git.

After a valid key is supplied, merge only the widget block beneath the existing
Immich card, preserving the rest of the live dashboard. Use the seed's HTTPS
URL https://immich.{{HOMEPAGE_VAR_DOMAIN}}, version 2 and the environment-variable
key placeholder. Homepage reaches the host Nginx route with trusted TLS; no
shared Docker network, host ports or backend exposure are added. Recreate only
Homepage to load the allowlisted key, then verify its authenticated widget API.
The current host has this widget live. The operator supplied the API key privately;
only Homepage was recreated. Its authenticated native statistics proxy succeeds,
existing dashboard groups remain, and browser-facing service/statistics responses
were checked for absence of the actual key.

## Queue, torrent and DNS widgets

The dashboard uses five groups selected by the owner:

- **Media** (first section): Jellyfin and Navidrome.
- **Arr:** Seerr, Radarr, Sonarr, Lidarr, Maintainerr, Prowlarr and Bazarr.
- **Utility:** qBittorrent and optional Bambuddy (A1 mini management).
- **Networking:** AdGuard Home and OpenSpeedTest.
- **Images & Videos:** Immich.

Maintainerr stays with Arr; qBittorrent has its own Utility section.
All five groups use column layouts, with Media first and up to five group
columns on larger displays. Smaller displays wrap responsively. The wide-grid
experiment was reverted at the owner's request; native CPU temperature remains
enabled. Full service
cards, links and widget settings are preserved when regrouping the live dashboard.
Fresh installs use the same grouping in the seed. Existing installations need a
selective merge with a private backup, preserving operator edits.

Radarr, Sonarr and Lidarr show only `queued`. qBittorrent shows `leech`, `seed`,
`download` and `upload`, without expanded per-torrent progress rows. These native
count blocks represent unfinished/completed torrents, including paused or queued
ones; they are not strict counts of torrents currently transferring bytes. Rates
are live sums. AdGuard shows only `blocked` and `latency`. Maintainerr retains
handled items/reclaimable storage; the other enabled widgets are unchanged.

Lifecycle commands map the existing RADARR_API_KEY, SONARR_API_KEY, LIDARR_API_KEY,
QBITTORRENT_PASSWORD and optional ADGUARD_PASSWORD into explicit Homepage-only
HOMEPAGE_VAR aliases. No duplicate secret inputs are required and `.env` is never
sourced or passed to containers. Homepage receives only these selected values,
not other media account passwords. Navidrome still receives only its derived token.
Missing optional AdGuard credentials do not block main-stack operations. Recreate
only Homepage to load the selected environment after updating Compose:

```sh
scripts/check
scripts/up
```

AdGuard retains its independent DNS network and additionally joins the existing
`ohara_default` network so Homepage reaches `http://adguard:3000` internally.
Start the main stack before starting AdGuard on a fresh host. The dashboard still
binds only host loopback 3003; DNS binds the verified LAN address with its existing
allowlist. Credentials, router/client DNS, filters and published ports are unchanged.
When applying this to an existing DNS container, connect its additional network
without restarting DNS; its Compose definition retains that connection on recreation.
Verify authenticated widget proxy responses, credential redaction and UDP/TCP DNS.
