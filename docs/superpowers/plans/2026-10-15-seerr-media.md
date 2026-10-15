# Seerr media stack

User-approved scope: add the services and connections needed for Seerr requests,
acquisition, and playback on Ohara. This supersedes the earlier media removal.

1. Add pinned Jellyfin, Radarr, Sonarr, Prowlarr, qBittorrent containers, shared
   media storage, backward-compatible settings, credentials, and exposure checks.
2. Add an agent command to connect Radarr/Sonarr to qBittorrent and Prowlarr;
   document Jellyfin/Seerr account setup and supported internal connection values.
3. Add jellyfin.xdadwal.in to HTTPS/certificates/Homepage. Keep all acquisition
   administration private. Preserve existing files and credentials.
4. Verify configuration, preservation, runtime services and API connections;
   obtain independent review, then commit, push, open a new PR and check CI.

Do not select indexers or create external accounts. Do not deploy on a live host.
Immich remains a separate follow-up. Software transcoding is the portable default.

Implementation record: all four steps completed. New regression tests were
observed failing before media defaults/storage implementation, then passing.
Non-root ownership preservation was similarly checked RED to GREEN. 37 unit
tests, CLI/setup/static checks and the real ten-service smoke pass locally.
Independent whole-diff review: no blocking findings; existing Homepage link
preservation documented. Real indexer acquisition/playback and host/public
activation remain deployment acceptance steps, not repository test claims.
