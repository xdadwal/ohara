# Ohara media pool

The owner approved a mergerfs pool at `/ohara/mnt` on the current host.
It merges these directories without moving existing files:

| Branch | Backing filesystem | Purpose |
|---|---|---|
| `/ohara/media` | Internal Samsung NVMe, ext4 root filesystem | Existing media tree |
| `/mnt/disks/crucial-240/media` | Crucial BX500 USB SSD, ext4 | Additional media capacity |
| `/mnt/disks/wd-500/media` | WD5000AAKX USB HDD, ext4 | Additional media capacity |

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
UUID=d8f5335d-0032-4029-bf0a-2ec7500cee2c /mnt/disks/wd-500 ext4 defaults,nofail,x-systemd.device-timeout=10s 0 2
/ohara/media:/mnt/disks/crucial-240/media:/mnt/disks/wd-500/media /ohara/mnt fuse.mergerfs defaults,nofail,allow_other,default_permissions,cache.files=partial,dropcacheonclose=true,category.create=mfs,minfreespace=20G,fsname=ohara-media,x-systemd.requires-mounts-for=/mnt/disks/crucial-240,x-systemd.requires-mounts-for=/mnt/disks/wd-500 0 0
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

The WD drive (serial `WD-WCAYUU292552`, label `Ohara-External`) was added as
a third branch after read-only inspection found only `lost+found`. Its existing
ext4 filesystem was preserved; it was not formatted. The new `media` directory
is `akshay:akshay`, mode `0775`. Both external disk mounts are required before
systemd starts the pool. With all three branches online, available space at this
point was about 870 GiB (approximately 1.11 TiB total). Current free capacity
changes with writes; the internal branch continues to share space with `/`.

`allow_other` permits service users to access the root-mounted FUSE filesystem;
`default_permissions` retains normal Unix permission enforcement. Source ownership
is preserved. Both external `media` branches are `akshay:akshay`, mode `0775`.
The empty underlying `/ohara/mnt` directory is `root:root`, mode `0555`, so ordinary
users cannot silently write there when the pool is unmounted. Root can bypass this;
media consumers explicitly require the pool mount before startup (see below).

`nofail` allows the host to boot without this optional storage. The pool's
`x-systemd.requires-mounts-for` generates both requirement and ordering dependencies
on both external mounts: systemd must mount both disks successfully before starting the
pool. Do not replace this with a mere check that the branch directory exists.
Use systemd to start the pool; manual `mount /ohara/mnt` bypasses systemd's dependency
management. Do not unplug a mounted disk during writes.

## qBittorrent memory-mapped I/O compatibility

Use `cache.files=partial,dropcacheonclose=true` on the installed mergerfs 2.40.2.
The original `cache.files=off` configuration failed qBittorrent 5.2.4's
memory-mapped disk access with `file_mmap ... No such device` despite healthy
mounts, permissions and free space. The write/read/hardlink checks used at initial
setup did not exercise `mmap` and therefore missed this incompatibility.

The incident was reproduced with a disposable 4 KiB Python `mmap` write in the
pool: errno 19 before the fix, successful write/flush/read afterward. The live
cache mode and only the pool's fstab option were changed to `partial`, preserving
all branches and data. The supported live control avoided unmounting the pool:

```sh
sudo python3 -c "import os; os.setxattr('/ohara/mnt/.mergerfs', 'user.mergerfs.cache.files', b'partial')"
# Also change only the pool's /etc/fstab cache.files option to partial.
sudo systemctl daemon-reload
```

Runtime controls alone do not persist across remounts. qBittorrent was restarted
to reopen handles; no other container or playback service was restarted. The four
new errored downloads returned to downloading/queued/stalled-peer states and data
transfer resumed. Seven older `missingFiles` entries were left untouched. Do not
redownload or delete library files to repair missing torrent metadata.

Reference: [upstream mmap compatibility and qBittorrent guidance](https://trapexit.github.io/mergerfs/2.41.1/known_issues_bugs/).

## Reboot and runtime reconnect behavior

On boot, the UUID-based fstab entries mount both external disks. The generated
pool unit requires both disk mounts, and Docker activation pulls in the enabled
media unit, which waits for the pool before starting its eight consumers. With a
missing disk, `nofail` lets the host boot while pool-dependent services remain
unavailable. Startup ordering is configured and inspected, but a full host reboot
has not been tested.

Runtime USB reconnect alone is not an automatic retry mechanism. The optional
watchdog below adds bounded recovery after both disks return. When systemd stops the pool mount, the media
unit's `BindsTo=` dependency stops its consumers. A hardware disconnect can also
leave stale mounts or I/O errors rather than an immediately clean stop; no
physical unplug test has established recovery behavior for these USB adapters.
Avoid disconnecting a mounted drive during writes.

After both drives are reconnected, when the pool is inactive, restore it with:

```sh
sudo systemctl start ohara-mnt.mount
sudo systemctl start ohara-media.service
scripts/status
```

The first command starts both required disk mounts. If a mount still appears
active but returns I/O errors, inspect mount/unit state and logs first; merely
starting an already-active unit will not repair it. Stop consumers before any
mount repair, and do not force/lazy-unmount storage while applications use it.
Reconnection does not by itself restart a failed media unit.

## Optional HDD standby and automatic reconnect recovery

The owner approved an opt-in systemd timer and guarded recovery on 2026-10-30.
The timer runs `ohara-storage-watchdog.service` every 30 seconds; no cron job or
host reboot is involved. Its root-owned Python worker reads UUID device nodes,
udev/sysfs and the kernel mount table. It does not periodically read library files,
issue SMART checks or read filesystem capacity, so the checks themselves do not
prevent HDD standby. Other applications may still wake the disk.

The WD HDD receives `hdparm -S 242` (60 minutes of firmware inactivity) once per
device attachment/boot. Both its ATA serial and rotational-device flag must match
before the command is allowed. SSDs and unrelated drives are not changed. The
setting is reapplied after reconnect; no forced standby or USB power-off is used.
The command returning success establishes acceptance, not that a physical idle
spin-down/wake cycle has been observed through this USB bridge.

Live installation on 2026-10-30 verified timer execution and acceptance of the WD
standby command. While checking, the expected disks reappeared after the observed
outage: journal entries progressed from `missing` to `settling` to `recover`,
then both external mounts, the pool and all eight guarded consumers started
automatically. No reboot or deliberate disk unplug was used to test recovery.

Recovery decisions and timestamps persist in root-only
`/run/ohara-storage-watchdog/state.json` between timer runs. This runtime state
resets on reboot. Missing disks clear the settling timestamp and stop only the
guarded consumers/pool; no recovery attempt is spent while a disk is absent.
After both expected UUIDs remain present for 60 seconds, the worker queues
`systemctl start ohara-media.service`; existing dependencies mount both external
filesystems and the pool before starting the eight consumers. Startup is bounded
by the existing unit and Compose timeouts. In-progress jobs are left alone.
An unsuccessful activation waits at least five minutes before another attempt,
with at most three activations per rolling hour. Healthy running services are
left alone. A device reappearing resets settling but does not erase the retry
budget. The timer does not overlap its own running service.

Wrong filesystem/device, read-only mounts, missing branches under a live pool,
or an observed device-generation change underneath an existing branch mount
require manual inspection. Consumers are stopped if necessary; no forced/lazy
unmount, fsck, filesystem repair, disk reset or data cleanup is attempted. A
metadata-only watchdog cannot establish that every block is readable or detect
all silent I/O failures; inspect kernel logs and storage health for those cases.

Install on this host after reviewing the example's exact UUIDs/serial against
the attached disks and `/etc/fstab` (replace them for any other host):

```sh
sudo apt-get install --no-install-recommends hdparm
sudo scripts/storage-watchdog install --config configs/storage/watchdog.example.json
systemctl list-timers ohara-storage-watchdog.timer
sudo journalctl -u ohara-storage-watchdog.service -n 30 --no-pager
```

The installer checks the branch UUID/mountpoint pairs against fstab and requires
the existing guarded media service. It installs a root-owned copy of the worker
at `/usr/local/lib/ohara/storage_watchdog.py`, configuration at
`/etc/ohara/storage-watchdog.json`, and the two units under `/etc/systemd/system`.
It enables the timer even if a disk is absent, so recovery can start after it
returns. A differing preexisting worker/config is rejected for manual review;
back it up before deliberately updating. It never changes fstab, branch data,
credentials, application configuration, router settings or DNS.

For planned maintenance, stop the timer **and** wait for its current worker before
stopping storage; otherwise it will attempt recovery after the settling period:

```sh
sudo systemctl stop ohara-storage-watchdog.timer
sudo systemctl stop ohara-storage-watchdog.service
sudo systemctl stop ohara-media.service
```

To retire automatic recovery, disable the timer with
`sudo systemctl disable --now ohara-storage-watchdog.timer` and stop its worker.
Disabling the timer does not undo a firmware standby setting already applied.
To disable that setting, first verify the HDD serial and current whole-disk
device path, then run `sudo hdparm -S 0 /dev/VERIFIED_WD_DISK`. Never substitute an
unverified `/dev/sdX`; device letters can change after reconnects.

References: [systemd timers](https://www.freedesktop.org/software/systemd/man/latest/systemd.timer.html),
[Debian hdparm manual](https://manpages.debian.org/trixie/hdparm/hdparm.8.en.html).

## Verification and recovery

Live verification covered branch visibility, ordinary-user write/read/fsync,
rename, and real hardlinks confirmed against backing inode/device, with all
probe files removed afterward. The pool stopped/started through systemd and
remained accessible. Generated `Requires=` and `After=` include both external mounts.
The three-branch expansion additionally verified writes and download-to-library
hardlinks on the WD branch before restoring the pool-dependent services.
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
