# Current Ohara stack

This is the implemented repository configuration, not a claim that a production
server is deployed or publicly reachable. Eight applications run in Docker Compose.
Nginx and Certbot run on the Linux host. Public DNS is managed at GoDaddy.

| Component | Role | Configured access |
|---|---|---|
| Homepage | Password-protected dashboard | HOMEPAGE_HOST (default xdadwal.in); loopback 3002 |
| Seerr | Discover/request movies and series | https://watch.xdadwal.in; loopback 5055 |
| Jellyfin | Media libraries and playback | https://jellyfin.xdadwal.in; loopback 8096 |
| OpenSpeedTest | On-demand browser speed test, embedded in Homepage | https://speed.xdadwal.in; loopback 3000 |
| Radarr | Movie acquisition/import | Private loopback 7878 |
| Sonarr | Series acquisition/import | Private loopback 8989 |
| Prowlarr | Indexers and sync to Radarr/Sonarr | Private loopback 9696 |
| qBittorrent | Downloads | Private loopback 8081 |
| Nginx (host) | Public HTTPS reverse proxy | TCP 80/443 |
| Certbot (host) | Certificates and renewal | Host service/timer |

The portfolio profile sets HOMEPAGE_HOST=ohara.xdadwal.in and PORTFOLIO_PORT=8010.
The separate FastAPI portfolio then serves the apex through Nginx; it is a host
process from its own repository, not a ninth Compose application. See replication.md.

Only router TCP 80/443 is forwarded to Ohara. Application ports remain loopback-only;
private administration uses SSH forwarding. There is no shared authentication service.
Credentials come from user-created local/homepage.env and local/media-credentials.
See credentials.md for empty templates and validation. Homepage includes native
Jellyfin/Seerr widgets, clock, Open-Meteo weather and container/storage resources;
media widgets need the actual application API keys supplied privately. See
[widget setup and existing-install migration](homepage-widgets.md).

Prowlarr syncs the chosen indexers to Radarr/Sonarr. Seerr sends requests to those
services; they use qBittorrent for downloads and import into the shared library.
Jellyfin reads that library for playback. The media setup command initializes
accounts and connections; indexer accounts/choices and an actual movie/episode
request, import, availability refresh and playback still need deployment acceptance.

DATA_ROOT defaults to /ohara for application state. MEDIA_ROOT defaults to
DATA_ROOT/media, with downloads and library trees shared consistently by acquisition
services. Jellyfin's library mount is read-only. Bootstrap targets Ubuntu 24.04 or
Debian 13 with systemd on amd64/arm64. Compose plus small rerunnable scripts are used;
Ansible is not part of this setup.

Immich is planned for the same machine in a separate Compose project at
immich.xdadwal.in. It is not implemented; hardware capacity, storage and backups
remain to be confirmed. Pi-hole and Copyparty have been removed. Their old data
and live containers are not deleted by a repository change; see operations.md for
cutover guidance. files.xdadwal.in is no longer an application endpoint.
