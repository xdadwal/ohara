# Homepage widgets

Fresh installations seed Jellyfin, Seerr, clock, weather and resource widgets.
OpenSpeedTest is a link-only card opening an on-demand browser-to-Ohara test. No new services are added.
Existing files under DATA_ROOT/homepage are deliberately preserved by setup.

AdGuard and media administration cards use LAN-only HTTPS subdomains under
HOMEPAGE_VAR_DOMAIN (supplied from DOMAIN). On this host, install the reviewed
[LAN Nginx routes](lan-services.md) and local DNS rewrites before using them.
Backends remain on loopback; SSH forwarding is still an alternative. The cards
pass no administration credentials to Homepage.

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

## Immich link

The Photos section in the seed contains a plain link to
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
