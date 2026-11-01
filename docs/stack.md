# Current Ohara stack

This is the implemented repository configuration, not a claim that a production
server is deployed or publicly reachable. Eleven applications run in the main Docker Compose project,
with optional AdGuard Home in the separate `ohara-dns` project.
Nginx and Certbot run on the Linux host. Public DNS is managed at GoDaddy.

Jellyfin optionally uses the pinned Abyss web theme and Spotlight through a
persistent read-only overlay; see [theme operations](jellyfin-theme.md).

| Component | Role | Configured access |
|---|---|---|
| Homepage | Password-protected dashboard | HOMEPAGE_HOST (default xdadwal.in); loopback 3002 |
| Seerr | Discover/request movies and series | https://seerr.xdadwal.in; loopback 5055 |
| Jellyfin | Movie/series libraries and playback | https://tv.xdadwal.in; loopback 8096 |
| OpenSpeedTest | On-demand browser speed test, linked from Homepage | https://speed.xdadwal.in; loopback 3000 |
| Radarr | Movie acquisition/import | Private loopback 7878 |
| Sonarr | Series acquisition/import | Private loopback 8989 |
| Lidarr | Music acquisition/import | Private loopback 8686 |
| Navidrome | Music library and playback | NAVIDROME_HOST (default music.xdadwal.in); loopback 4533 |
| Bazarr | Movie/series subtitles | Private loopback 6767 |
| Prowlarr | Indexers and sync to Radarr/Sonarr/Lidarr | Private loopback 9696 |
| qBittorrent | Downloads | Private loopback 8081 |
| Nginx (host) | Public HTTPS reverse proxy | TCP 80/443 |
| Immich (optional separate project) | Personal photos/videos; no ML | immich.xdadwal.in; loopback 2283 |
| Bambuddy (optional separate project) | A1 mini management; native password login | bambuddy.xdadwal.in; loopback 8008 |
| AdGuard Home (optional) | LAN DNS, filtering, domain rewrites | Reserved LAN IPv4 TCP/UDP 53; loopback dashboard 3003 |
| Tailscale (optional host client) | Private remote OpenSSH; separate enrollment | Tailnet SSH port only via operator network policy |
| Certbot (host) | Certificates and renewal | Host service/timer |
| ntfy (optional separate project) | Private notification topics and host alerts | ntfy.xdadwal.in; loopback 2586 |
| bpytop (host) | CPU, memory, disk, network and process monitoring | Interactive terminal or SSH |

The portfolio profile sets HOMEPAGE_HOST=ohara.xdadwal.in and PORTFOLIO_PORT=8010.
The separate FastAPI portfolio then serves the apex through Nginx; it is a host
process from its own repository, not a Compose application. See replication.md.

Only router TCP 80/443 is forwarded to Ohara. Application web ports remain
loopback-only; private administration uses SSH forwarding. Optional AdGuard DNS
is the explicit LAN-only exception, never a router port forward.
There is no shared authentication service.
This host also has approved [LAN-only HTTPS administration routes](lan-services.md)
for AdGuard, Radarr, Sonarr, Prowlarr, qBittorrent, Lidarr and Bazarr. Their backend
ports stay on loopback; native application logins remain required.
Credentials come from user-created .env.
See credentials.md for empty templates and validation. Homepage includes native
Jellyfin/Seerr widgets, Navidrome Now Playing, clock, Open-Meteo weather and
container/storage resources. Jellyfin/Seerr use privately supplied API keys;
Navidrome uses a token derived locally from its existing password. See
[widget setup and existing-install migration](homepage-widgets.md).

Prowlarr syncs the chosen indexers to Radarr/Sonarr/Lidarr. Seerr sends movie/series
requests to Radarr/Sonarr; music is managed directly in Lidarr. Acquisition services
use qBittorrent for downloads and import into the shared library. Jellyfin handles
movie/series playback; Navidrome reads the music library for playback. Fresh
Jellyfin setup seeds Movies and TV Shows only; existing Music libraries are preserved. Bazarr connects
to Radarr/Sonarr and writes subtitles beside their media through the shared `/data`
paths. Operators choose subtitle languages/providers and supply provider credentials. The media setup command initializes
accounts and connections; indexer accounts/choices and an actual movie/episode
request, import, availability refresh and playback still need deployment acceptance.

DATA_ROOT defaults to /ohara for application state. MEDIA_ROOT defaults to
DATA_ROOT/media, with downloads and library trees shared consistently by acquisition
services. Jellyfin's library mount is writable so authorized Jellyfin users can
delete media. Navidrome uses the official
`deluan/navidrome` image, stores writable state in DATA_ROOT/navidrome at `/data`,
and reads MEDIA_ROOT/library/music read-only at `/music`. Bootstrap targets Ubuntu 24.04 or
Debian 13 with systemd on amd64/arm64. Compose plus small rerunnable scripts are used;
Ansible is not part of this setup.

Lidarr and Bazarr have no public admin subdomains. All services run in the current
Compose stack. A future NAS/multiple-node layout, including an acquisition node
for these services, is a discussed target and is not implemented here.

Immich is implemented as the optional separate `ohara-immich` Compose project,
operated with `scripts/immich`; production is running with public HTTPS and owner setup complete. It includes its own
PostgreSQL and Valkey containers, no machine-learning container, and a loopback-only
web port 2283. Approved storage is `/ohara/immich/library` and
`/ohara/immich/postgres`. The owner accepted current single-user capacity and
explicitly deferred independent backups/restore testing; these are not release
blockers or implemented protections. See [Immich operations](immich.md). Pi-hole and Copyparty have been removed. Their old data
and live containers are not deleted by a repository change; see operations.md for
cutover guidance. files.xdadwal.in is no longer an application endpoint.

Maintainerr is an optional separate `ohara-maintainerr` Compose project for media
maintenance, connected to Jellyfin/Seerr/Radarr/Sonarr on the main Docker network.
Its backend is loopback-only 6246; `maintainerr.xdadwal.in` uses the LAN-only admin
proxy, Homepage card and exact AdGuard rewrite. It has no built-in login.
Setup creates no cleanup rules or collections; retention/deletion policy is an
owner choice. See [Maintainerr operations](maintainerr.md).

Bambuddy is an optional independent Compose project for the owner's Bambu Lab
A1 mini. Use `scripts/bambuddy` and [Bambuddy setup](bambuddy.md); printer access
codes are entered only in the private HTTPS UI. Its server, public HTTPS, Homepage and exact local DNS rewrite are live;
native authentication is enabled; owner-login and actual printer readiness
remain separate UI verification steps.

ntfy runs outside the media pool in its own project, with anonymous topic access
denied. The independent host alert timer observes service/disk transitions and
queues notifications during ntfy downtime; see [ntfy operations](ntfy.md).
