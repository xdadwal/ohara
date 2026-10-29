# Ohara media pool

The owner approved a mergerfs pool at `/ohara/mnt` on the current host.
It merges these directories without moving existing files:

| Branch | Backing filesystem | Purpose |
|---|---|---|
| `/ohara/media` | Internal Samsung NVMe, ext4 root filesystem | Existing media tree |
| `/mnt/disks/crucial-240/media` | Crucial BX500 USB SSD, ext4 | Additional media capacity |

This is host-specific setup, not an automatic action in `scripts/setup` or
`scripts/up`. Application paths and private `MEDIA_ROOT` remain unchanged.
Services still access `/ohara/media` directly and do not yet use the pooled
capacity. Keep databases and other application state on their existing storage.
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
future consumers must explicitly require the pool mount before startup.

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
No reboot, disk-disconnection test, service migration, or new public endpoint was
performed. No service restart was required. Capacity at setup was approximately
679 GiB total and 413 GiB available; the internal branch shares space with `/`.

`findmnt --verify --tab-file /etc/fstab` reports no parse errors, but its generic
source/filesystem probes warn about the colon-separated FUSE source and
`fuse.mergerfs`. Successful systemd activation and actual pool I/O are the runtime
evidence; those warnings are not an ext4 UUID error.

Private pre-change fstab copies and operational records are under
`local/storage-preparation/`. To retire the pool, stop all future consumers first,
then stop only this mount and remove only its fstab entry:

```sh
sudo systemctl stop ohara-mnt.mount
# Edit /etc/fstab: remove only the /ohara/mnt mergerfs entry.
sudo systemctl daemon-reload
```

Do not delete branch directories or their contents: those are the actual files.
Do not restore the whole saved fstab over unrelated later changes.

A future service cutover must preserve the shared downloads/library tree and
verify imports/hardlinks through the pool before changing storage policy. Add
startup dependencies on `ohara-mnt.mount` and handle Docker's existing bind mounts
deliberately; simply changing a host mount does not migrate running containers.

References: [Debian 2.40.2 manual](https://manpages.debian.org/trixie/mergerfs/mergerfs.1.en.html),
[upstream systemd mount dependencies](https://trapexit.github.io/mergerfs/latest/quickstart/#systemd-mount-dependencies).
