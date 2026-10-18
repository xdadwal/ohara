# Current Ohara stack

This is the implemented repository configuration, not a claim that a production
server is deployed or publicly reachable. Eleven applications run in Docker Compose.
Nginx and Certbot run on the Linux host. Public DNS is managed at GoDaddy.

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
| Tailscale (optional host client) | Private remote OpenSSH; separate enrollment | Tailnet SSH port only via operator network policy |
| Certbot (host) | Certificates and renewal | Host service/timer |
| bpytop (host) | CPU, memory, disk, network and process monitoring | Interactive terminal or SSH |

The portfolio profile sets HOMEPAGE_HOST=ohara.xdadwal.in and PORTFOLIO_PORT=8010.
The separate FastAPI portfolio then serves the apex through Nginx; it is a host
process from its own repository, not a Compose application. See replication.md.

Only router TCP 80/443 is forwarded to Ohara. Application ports remain loopback-only;
private administration uses SSH forwarding. There is no shared authentication service.
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
services. Jellyfin's library mount is read-only. Navidrome uses the official
`deluan/navidrome` image, stores writable state in DATA_ROOT/navidrome at `/data`,
and reads MEDIA_ROOT/library/music read-only at `/music`. Bootstrap targets Ubuntu 24.04 or
Debian 13 with systemd on amd64/arm64. Compose plus small rerunnable scripts are used;
Ansible is not part of this setup.

Lidarr and Bazarr have no public admin subdomains. All services run in the current
Compose stack. A future NAS/multiple-node layout, including an acquisition node
for these services, is a discussed target and is not implemented here.

Immich is planned for the same machine in a separate Compose project at
immich.xdadwal.in. It is not implemented; hardware capacity, storage and backups
remain to be confirmed. Pi-hole and Copyparty have been removed. Their old data
and live containers are not deleted by a repository change; see operations.md for
cutover guidance. files.xdadwal.in is no longer an application endpoint.
