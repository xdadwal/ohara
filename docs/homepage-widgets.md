# Homepage widgets

Fresh installations seed Jellyfin, Seerr, clock, weather and resource widgets.
OpenSpeedTest is a link-only card opening an on-demand browser-to-Ohara test. No new services are added.
Existing files under DATA_ROOT/homepage are deliberately preserved by setup.

## Connect media widgets

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

The disk entry uses /app/config to identify the filesystem holding Ohara's
Homepage state (DATA_ROOT/homepage). With expanded display, it shows used space
and total filesystem capacity, not the size of that directory. No media-library
mount is needed. A filesystem's total is not the sum of every physical disk:
unmounted disks, separate filesystems and other storage pools are not included.

## Existing installations

Back up DATA_ROOT/homepage/services.yaml and widgets.yaml. Merge the selected
widget sections from configs/homepage into those files, preserving custom links,
weather location and other edits. Do not overwrite them automatically. Update the
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
