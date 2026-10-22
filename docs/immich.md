# Immich operations

Immich is implemented as the independent `ohara-immich` Compose project in
`compose.immich.yaml`. It is optional: the main setup/up/status commands never
start it. The release is v3.3.5, with immutable images in `versions.immich.env`
matching the official release Compose dependencies. PostgreSQL and Valkey run in
containers with no published ports. Only Immich publishes `127.0.0.1:2283`.
The production instance was started privately on 2026-10-22 after the operator
supplied the database password. All three containers are healthy. The operator completed owner onboarding;
the initialized/onboarded state was verified and public HTTPS is now active,
with the live Homepage link and local AdGuard rewrite.

The owner selected no AI features. There is no machine-learning container;
`configs/immich/immich.json` sets `machineLearning.enabled=false`. Uploads,
albums, browsing, metadata and playback remain available; semantic search,
face recognition and OCR are disabled. Thumbnail/metadata jobs have concurrency
one; video conversion also has concurrency one and FFmpeg uses two threads.
These are starting settings for this shared 2-core/4-thread, 7.6 GiB host, not a
performance guarantee. Observe resource use during an initial small upload.

## Inputs and storage

The approved starting paths are `/ohara/immich/library` for the complete upload
tree and `/ohara/immich/postgres` for PostgreSQL. Both currently live on the local
ext4 NVMe root filesystem, with about 239 GiB free at inspection. Photo-library
size/growth and an independent backup destination remain operator inputs.

Keep credentials in the existing private root `.env`, mode 0600. Privately append
`IMMICH_DB_PASSWORD` with an independent password of at least 16 ASCII letters
and digits, following upstream's character restrictions. No value is generated.
An operator may explicitly accept an existing shorter alphanumeric password with
`--allow-short-db-password` on `prepare`, `check` and `up`. The default remains
16 characters; empty values and unsupported characters are always rejected.
The operator authorized this exception for the current host on 2026-10-22.
Use that flag on subsequent operations while retaining this input. Main-stack
credential checks ignore this optional project's password.

Keep this value synchronized with the actual database account; editing it does
not rotate an initialized PostgreSQL password. Immich's owner account is separate
and is created privately through the application during onboarding.

Optional non-secret overrides in the same `.env` are:

```dotenv
IMMICH_LIBRARY_ROOT=/ohara/immich/library
IMMICH_DATABASE_ROOT=/ohara/immich/postgres
IMMICH_LIBRARY_MOUNT=/
IMMICH_DATABASE_MOUNT=/
```

These are also the defaults. `*_MOUNT` records the expected mounted filesystem:
update it to the new mountpoint when moving to a dedicated drive. The script
refuses missing mounts, a different underlying mount, symlink ancestors, nested
library/database paths, overlap with existing Ohara media/application storage,
and a database on a network filesystem. PostgreSQL must remain on suitable local
SSD storage. The 2 GiB free-space guard is a minimum check, not sizing approval.
Allow capacity for originals, thumbnails, transcoded videos and database backups.

The complete upload tree is mounted at `/data` inside Immich. Keep that internal
path stable during any move. No shared media-library paths or external libraries
are mounted by default. The required database extension image is retained even
with machine learning disabled.

## Check, prepare and private startup

Commands locate the repository from any current directory:

```sh
scripts/immich check --static
# After filling IMMICH_DB_PASSWORD privately and reviewing capacity/mounts:
sudo scripts/immich prepare
scripts/immich check
scripts/immich up
scripts/immich status
scripts/immich stop
```

`check --static` uses `.env.example` and empty secret placeholders; it needs
Docker Compose but no daemon, private credentials or storage. Normal checks read
`.env`, validate the real credential and verify storage. `prepare` validates all
inputs before creating directories; it preserves existing content and ownership.
Container entrypoints initialize their own new state. No recursive chown, volume
removal or automatic migration is performed. `up` validates before starting and
waits at most 180 seconds for health, within a bounded command timeout. `status`
checks all three containers and the local ping API; it does not verify accounts,
asset integrity or backup readiness. `stop` preserves all state and needs no real
password. Logs/expanded Compose environments can contain private information;
inspect locally and never publish them.

For owner onboarding use `ssh -L 2283:127.0.0.1:2283 user@server`, then open
`http://localhost:2283`. Create the real owner using a user-chosen password;
do not place the DB password in the owner password field. Verify login/logout,
photo upload/download, metadata, an album, and representative video upload and
playback. Configure phone backup deliberately, initially with a small test album.
Keep original copies on the phone or elsewhere until restore testing passes.

The settings file disables editing system settings in the UI, including settings
not explicitly listed in the file. To customize, edit the versioned JSON and
recreate the Immich server deliberately. Defaults for unspecified settings come
from the pinned release. Do not remove the file to change settings without first
preserving the machine-learning-disabled policy.

## Backup and restore acceptance

Before relying on Immich as a personal archive, select an independent/off-host
backup destination and retention policy. A directory on this NVMe or Immich's
built-in `backups` directory alone is not independent protection. No backup job
or destination is assumed or automatically installed.

Follow the release's supported [backup and restore procedure](https://docs.immich.app/administration/backup-and-restore/):

1. Pause phone/client uploads and background jobs. Create a database dump through
   Administration > Job Queues > Create job > Create Database Dump. Wait for it
   to finish, then stop Immich to freeze the associated file tree before copying.
2. Back up the entire `IMMICH_LIBRARY_ROOT`, including hidden mount-check files
   and `upload`, `library`, `thumbs`, `encoded-video`, `profile`, and `backups`.
   Include the completed database dump. Copying only the nested `library` directory
   misses assets; copying photos without the database loses application state.
3. Encrypt and transfer the backup off-host. Privately preserve `.env`, any local
   settings, the deployment commit and `versions.immich.env`. Raw PostgreSQL files
   copied while the database is running are not a consistent database backup.
4. Restore into an isolated project with separate paths/volumes and a different
   loopback port, using the same Immich release and its supported onboarding
   database-restore flow. Never point this test at production paths or both
   instances at the same database. Keep external/phone clients disconnected.
5. Verify owner login, albums, asset counts, representative photo checksums,
   originals/downloads, metadata and video playback. Record the evidence. Only
   this establishes restore readiness; a successful copy or health check does not.

## Move photos to another drive

Keep PostgreSQL on local SSD unless there is a separate reason to move it.
Mount the new Linux filesystem deliberately and verify free space/ownership.
Stop Immich before the final copy so uploads, file jobs and the database remain
consistent. Copy the complete upload root, including hidden files, preserving
relative paths and metadata; verify checksums. Change `IMMICH_LIBRARY_ROOT` and
`IMMICH_LIBRARY_MOUNT` privately, then run check/up/status. The container still
sees `/data`, so host-path changes do not require rewriting asset records.
Verify representative assets before switching phone uploads back on. Retain the
old tree for rollback; do not delete/reimport files or bypass mount-check errors.
Ensure the new drive mounts at boot before Docker/Immich starts: Compose does not
run the wrapper's mount checks on automatic container restarts. Before enabling
unattended startup on a new drive, add/review the host's mount ordering (for
example Docker systemd `RequiresMountsFor=`), preserving existing Docker users.
Otherwise a missing mount can expose an empty mountpoint directory.

## Move to another machine

Use the same consistent media-plus-database backup and isolated restore process.
Transfer configuration and credentials privately; use the same pinned release
first and upgrade as a separate operation. Keep `/data` and any external-library
container paths unchanged. Restore PostgreSQL through a logical dump rather than
assuming raw data directories work across architectures/database versions.
Verify available local SSD space, permissions and representative assets before
moving `immich.xdadwal.in` and its host Nginx route. Keep the old server stopped
but intact, and avoid two writable copies accepting phone uploads during cutover.
A new machine with the same working hostname can keep the client-facing URL.

## HTTPS and Homepage activation

The operator requested public HTTPS at `immich.xdadwal.in` and a Homepage link.
Public HTTPS is active on the current host after the operator completed owner
onboarding, with an AdGuard rewrite to 192.168.1.101 and a live Homepage card. No certificate issuance or public DNS change was needed. `scripts/tls` continues to manage only its established
service inventory; it does not activate Immich.

`configs/nginx/immich.template` supplies the reviewed opt-in HTTPS server block:
large request bodies, unbuffered uploads, forwarded headers, WebSockets and long
streaming timeouts. Serve the root of `immich.xdadwal.in`, never a URL subpath.
After private account and restore acceptance, verify DNS and a certificate that
covers the hostname. Preview the rendered host-specific candidate with `scripts/immich-proxy`.
To finish the host integration before creating an owner, use the LAN-only mode:

```sh
sudo scripts/immich-proxy --apply --onboarding-only
```

This mode permits only loopback and this host's verified 192.168.1.0/24 LAN on
both HTTP and HTTPS. It rejects untrusted sources regardless of forwarded headers.
Open `https://immich.xdadwal.in` from a LAN client using AdGuard to create the owner.
This was the initial mode; the current live public route is tracked in
`configs/nginx/deployed/ohara-immich.conf`.

After verifying the owner login, enable public access with:

```sh
sudo scripts/immich-proxy --apply --accounts-ready
```

The installer verifies the existing certificate chain/hostname/expiry, initialized
owner state and disabled ML features; it refuses duplicate/unmanaged routes.
It installs only `/etc/nginx/conf.d/ohara-immich.conf`, validates and reloads Nginx,
and restores the previous file on failure. No certificate is issued or replaced.
`--accounts-ready` attests to an actual private login check; an initialized flag
alone does not establish successful login. This installer is specific to the
existing xdadwal.in wildcard host. Its no-argument preview needs no root access.
For another host, render `${IMMICH_HOST}`, `${CERTIFICATE}` and
`${CERTIFICATE_KEY}` explicitly, leaving Nginx runtime variables intact. Review existing routes, certificate renewal coverage and ACLs. Install as
a separate managed block with an HTTP redirect/ACME route appropriate to the
chosen certificate method; route `/.well-known/immich` to Immich rather than a
generic dotfile denial. Test `nginx -t` before reloading and retain rollback copies.

After successful application, track the exact live `ohara-immich.conf` under
`configs/nginx/deployed/` and update its README. Verify trusted
HTTPS, phone connection, photo upload/download and a representative large video
from the intended networks. The Homepage seed includes a plain Immich card; merge only that card into the
live dashboard after deployment is verified, preserving operator edits. No Homepage API key is needed for a link.

## Verification

Run the repository's standard Python/setup/CLI/static checks and
`scripts/immich check --static`. `python3 tests/smoke_immich.py` starts only a
randomly named disposable project with test accounts, random loopback port and
named test volumes. It verifies startup, owner login, a small photo upload/download round trip and
the effective disabled ML policy, then removes only that test project's volumes. It never uses `.env`
or production storage. This smoke does not establish backup restoration, photo
import/playback, real Linux provisioning or public access.

References: [official installation](https://docs.immich.app/install/docker-compose/),
[requirements](https://docs.immich.app/install/requirements/),
[configuration file](https://docs.immich.app/install/config-file/),
[reverse proxy](https://docs.immich.app/administration/reverse-proxy/),
[release v3.3.5](https://github.com/immich-app/immich/releases/tag/v3.3.5).

## Invite-only Google OAuth

See [Google OAuth setup](immich-google-oauth.md). Registration is always disabled
in the managed policy; administrators provision approved users by their Google
email. Google credentials come only from the private .env and are rendered into
a private read-only server configuration by scripts/immich oauth. Live Google
login is enabled with the supplied client credentials; browser acceptance with
approved and uninvited accounts remains pending. Google is the only enabled
interactive login method; password login is disabled. The onboarding workflow is
in that guide, with no extra authentication or SMTP service.
