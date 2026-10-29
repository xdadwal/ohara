# Ohara media pool

The owner approved a mergerfs pool at `/ohara/mnt` on the current host.
It merges these directories without moving existing files:

| Branch | Backing filesystem | Purpose |
|---|---|---|
| `/ohara/media` | Internal Samsung NVMe, ext4 root filesystem | Existing media tree |
| `/mnt/disks/crucial-240/media` | Crucial BX500 USB SSD, ext4 | Additional media capacity |

The disk/pool mount setup is host-specific, not an automatic action in
`scripts/setup` or `scripts/up`. The current host's private `.env` now sets
`MEDIA_ROOT=/ohara/mnt` and `MEDIA_POOL_MOUNT=/ohara/mnt`. All seven media consumers and Homepage
use the pool; databases and application state remain on their original storage.
Do not put `/ohara`, `/`, or `/ohara/mnt` itself into the branch list.

## Installed configuration

On 2026-10-29, Debian's `mergerfs` package version `2.40.2-5` was installed:

```sh
sudo apt-get install --no-install-recommends mergerfs
```

The Crucial was identified by model `CT240BX500SSD1`, serial `2117E41893C1`.
Its previous Windows partitions were erased with the owner's authorization and
replaced by one GPT/ext4 partition labeled `crucial-media`. Existing files on the
internal drive were preserved. `/etc/fstab` contains:

```fstab
UUID=abb98774-3ec1-4cf5-a91f-eff080c29ceb /mnt/disks/crucial-240 ext4 defaults,nofail,x-systemd.device-timeout=10s 0 2
/ohara/media:/mnt/disks/crucial-240/media /ohara/mnt fuse.mergerfs defaults,nofail,allow_other,default_permissions,cache.files=off,dropcacheonclose=true,category.create=mfs,minfreespace=20G,fsname=ohara-media,x-systemd.requires-mounts-for=/mnt/disks/crucial-240 0 0
```

Use the verified disk UUID on a different host, never copy this UUID blindly.
The pool is started through the generated systemd mount unit:

```sh
sudo systemctl daemon-reload
sudo systemctl start ohara-mnt.mount
systemctl status ohara-mnt.mount
findmnt -T /ohara/mnt
```

`category.create=mfs` selects the eligible branch with the most available space
for new files. `minfreespace=20G` excludes a branch from new-file placement below
that threshold; it is not a reservation or quota and does not stop an existing
file growing or direct writes to a branch. Files stay whole on individual disks.
The pool provides neither redundancy nor an independent backup.

`allow_other` permits service users to access the root-mounted FUSE filesystem;
`default_permissions` retains normal Unix permission enforcement. Source ownership
is preserved. The external `media` branch is `akshay:akshay`, mode `0775`.
The empty underlying `/ohara/mnt` directory is `root:root`, mode `0555`, so ordinary
users cannot silently write there when the pool is unmounted. Root can bypass this;
media consumers explicitly require the pool mount before startup (see below).

`nofail` allows the host to boot without this optional storage. The pool's
`x-systemd.requires-mounts-for` generates both requirement and ordering dependencies
on the Crucial mount: systemd must mount the disk successfully before starting the
pool. Do not replace this with a mere check that the branch directory exists.
Use systemd to start the pool; manual `mount /ohara/mnt` bypasses systemd's dependency
management. Do not unplug a mounted disk during writes.

## Verification and recovery

Live verification covered branch visibility, ordinary-user write/read/fsync,
rename, and real hardlinks confirmed against backing inode/device, with all
probe files removed afterward. The pool stopped/started through systemd and
remained accessible. Generated `Requires=` and `After=` include the Crucial mount.
The seven media consumers were subsequently recreated with pooled bind mounts
and their original container paths. No reboot, disk-disconnection test or new
public endpoint was performed. Capacity at setup was approximately
679 GiB total and 413 GiB available; the internal branch shares space with `/`.

`findmnt --verify --tab-file /etc/fstab` reports no parse errors, but its generic
source/filesystem probes warn about the colon-separated FUSE source and
`fuse.mergerfs`. Successful systemd activation and actual pool I/O are the runtime
evidence; those warnings are not an ext4 UUID error.

Private pre-change fstab copies and operational records are under
`local/storage-preparation/`. To retire the pool, stop its consumers first,
then stop only this mount and remove only its fstab entry:

```sh
sudo systemctl stop ohara-media.service
sudo systemctl disable ohara-media.service
sudo systemctl stop ohara-mnt.mount
# Edit /etc/fstab: remove only the /ohara/mnt mergerfs entry.
sudo systemctl daemon-reload
```

Do not delete branch directories or their contents: those are the actual files.
Do not restore the whole saved fstab over unrelated later changes.

## Service cutover and startup guard

The host's unified private `.env` contains:

```dotenv
MEDIA_ROOT=/ohara/mnt
MEDIA_POOL_MOUNT=/ohara/mnt
```

`MEDIA_POOL_MOUNT` is optional and must equal `MEDIA_ROOT`. Leave it unset on
ordinary storage. Runtime startup (`up`, `create`, `run`, `start`, `restart`),
non-static checks and media directory preparation verify an exact active
`fuse.mergerfs` mount before touching storage or starting containers. Static
Compose rendering remains usable without the disk.

When this option is set, the runtime includes `compose.media-pool.yaml`, which
changes the seven media consumers and Homepage to `restart: on-failure:5`. Docker can
restart crashed processes, but does not automatically start these containers
at daemon startup ahead of their storage dependency. The remaining services keep
`unless-stopped` and do not depend on the pool.

Install the media startup unit after mounting the pool and setting both private
values. Check Jellyfin playback before the initial cutover: starting the unit can
recreate containers whose mounts or restart policy changed.

```sh
scripts/check
sudo scripts/media-pool install-unit
sudo systemctl start ohara-media.service
systemctl status ohara-media.service
scripts/media-pool check
scripts/status
```

`install-unit` enables but does not start the unit. The generated root-owned
`/etc/systemd/system/ohara-media.service` starts Homepage, Jellyfin, Navidrome, Radarr,
Sonarr, Lidarr, Bazarr and qBittorrent through the repository's supported Compose
wrapper, preserving Abyss and existing environment filtering. It uses
`RequiresMountsFor=`, `BindsTo=` and `After=` for the pool and Docker; `PartOf=` and
`WantedBy=docker.service` arrange startup on Docker activation and restart.
Stopping the pool stops these consumers. `ExecStopPost` also stops partial startup
on failure. After recovering a missing disk, start the mount and this unit again.
No Docker-daemon restart or host-wide storage dependency was introduced.

| Services | Pool source | Container path |
|---|---|---|
| Radarr, Sonarr, Lidarr, qBittorrent | `/ohara/mnt` | `/data` |
| Jellyfin | `/ohara/mnt/library` | `/media` |
| Bazarr | `/ohara/mnt/library` | `/data/library` |
| Homepage (capacity widget) | `/ohara/mnt` | `/media-storage` (read-only) |
| Navidrome | `/ohara/mnt/library/music` | `/music` (read-only) |

Seerr, Prowlarr and Maintainerr use application APIs and have no media bind mount.
AdGuard, OpenSpeedTest and Immich retain their independent existing
storage; Immich's `/data` path and database/cache are preserved. No application
root folder, download path, user account or source torrent was intentionally
changed. Do not copy between the pool and its branches; they expose the same files.

Cutover validation includes backing-inode/device hardlinks from downloads to the
library, plus hardlink visibility inside all four `/data` consumers. Existing
Jellyfin/Bazarr library access and API health are checked independently. These
checks do not claim a new acquisition, real playback or a host reboot was tested.
The owner-queued Jellyfin Enhanced 12.14.0.0 update activated on the restart;
Abyss remains valid. The Enhanced settings checker intentionally refuses this
unreviewed version (its profile still pins 12.13.0.0); no settings reset or schema
change was applied. Seven qBittorrent entries report missing files whose content
paths are absent from both the original branch and the pool. No torrent cleanup,
redownload, path repair or seeding policy change was attempted.

For rollback, stop/disable `ohara-media.service` before reverting only the two
private inputs to the previous configuration (`MEDIA_ROOT=/ohara/media`, remove
`MEDIA_POOL_MOUNT`). Recreate the eight consumers through the wrapper to restore
their original mounts and restart policy. **Files created on the Crucial after
cutover will not appear through the internal branch alone**; inventory them and
plan a non-destructive migration before reverting active use. Do not delete the
external branch or restore the whole private `.env` over later credential edits.

References: [Debian 2.40.2 manual](https://manpages.debian.org/trixie/mergerfs/mergerfs.1.en.html),
[upstream systemd mount dependencies](https://trapexit.github.io/mergerfs/latest/quickstart/#systemd-mount-dependencies).
