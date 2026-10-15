# Immich follow-up

Immich has not been deployed. It will manage personal photos/videos using the
upstream production Docker Compose deployment. It will run on the **same fresh
Linux machine as Ohara**, as confirmed by the user. Keep an independent Compose project for its application/database lifecycle.

## Decisions before implementation

1. Available CPU/RAM/architecture, accounting for the other Ohara services. Current upstream guidance
   lists 6 GB minimum RAM, 8 GB recommended, 2 CPU cores minimum and 4 recommended.
   On amd64, current v3 machine learning requires x86-64-v2 instructions.
2. Media storage path, filesystem and capacity, including current library size
   and growth. Plan for thumbnails/transcoded videos as well as originals.
3. Database path on local SSD storage, not a network share.
4. An independent backup destination for originals and database, and a restore
   test. A second directory on the same disk is not an off-host backup.
5. Confirmed hostname: `immich.xdadwal.in`. Confirm whether access will be public.
   Reuse host Nginx for HTTPS and bind the Immich web port to loopback.

## Implementation scope

- Add an independently operated Compose project using the official release-matched
  Immich files. Keep its required database/cache and machine-learning services;
  removing standalone Redis from Ohara does not remove Immich dependencies.
- Document required settings in a separate example env file and pin a tested
  release. Reuse the Ohara host bootstrap where appropriate; avoid coupling
  photo-service restarts or database state to the small utility stack.
- Create explicit persistent paths and verify mounts, available capacity and
  permissions before startup. Do not expose the photo archive through Copyparty
  or import/delete existing originals by assumption.
- Configure HTTPS with the supported large-upload/WebSocket proxy settings and
  a dedicated hostname. Do not serve Immich from a URL subpath.
- Create the owner account, configure phone photo/video backup, and test upload,
  download, playback, metadata and representative large videos.
- Back up both media and database, restore into an isolated instance and verify
  representative albums/assets before treating deployment as ready.
- Add a Homepage link only after its actual hostname and deployment are known.

## Current primary references (checked 2026-10-15)

- [Requirements](https://docs.immich.app/install/requirements/)
- [Official Compose installation](https://docs.immich.app/install/docker-compose/)
- [Reverse proxy](https://docs.immich.app/administration/reverse-proxy/)
- [Backup and restore](https://docs.immich.app/administration/backup-and-restore/)
