# Homepage widgets

Fresh installations seed Jellyfin, Seerr, clock, weather and resource widgets.
OpenSpeedTest remains an on-demand browser-to-Ohara test. No new services are added.
Existing files under DATA_ROOT/homepage are deliberately preserved by setup.

## Connect media widgets

Complete media setup first, then copy the actual application-issued keys into
local/homepage.env using a private editor. Keep mode 0600; never send keys in chat,
commit them, invent replacements, or use the Jellyfin account password as an API key.

- Jellyfin: Dashboard > Advanced > API Keys. Add
  HOMEPAGE_VAR_JELLYFIN_API_KEY with the application's key.
- Seerr: Settings > General > API Key. Add HOMEPAGE_VAR_SEERR_API_KEY with that key.

The commented entries in configs/credentials/homepage.env.example show the names.
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

The resource strip enables CPU, memory, uptime, network and temperature readings
where supported. It is labeled Homepage container: CPU/RAM/network/uptime must
not be interpreted as a complete Linux host monitor. Temperature can be unavailable
in Docker or on unsupported hardware. Full host monitoring would require an
additional collector such as Glances, which is outside this change.

Storage checks /app/config (the filesystem holding Homepage state) and
/monitor/media (a read-only bind of MEDIA_ROOT/library). The media bind provides
filesystem capacity without giving Homepage write access. It does expose library
contents read-only to Homepage. If both paths share one filesystem, capacity is
naturally duplicated. Separate mounts beneath the media tree require their own
explicit monitored paths. Root disks, backup disks, SMART/GPU data and other
unmounted filesystems are not implicitly monitored. Resource polling is 10 seconds.

## Existing installations

Back up DATA_ROOT/homepage/services.yaml and widgets.yaml. Merge the selected
widget sections from configs/homepage into those files, preserving custom links,
weather location and other edits. Do not overwrite them automatically. Update the
checkout/Compose definition and recreate Homepage with scripts/up to add the
read-only media mount and credential environment, then refresh Homepage.
Verify login, native widget values and media capacity. Allow browser geolocation
or configure coordinates and verify weather; check temperature availability on
the actual Linux hardware. Local container tests do not verify browser permission
prompts, visual layout or real host sensors.

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
