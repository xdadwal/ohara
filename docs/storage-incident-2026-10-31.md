# Repeated media outages: 2026-10-31 investigation

The confirmed outage mechanism is a USB block-device disconnect, followed by
failed filesystem I/O and removal of the guarded mergerfs mount. The dependent
`ohara-media.service` stops its eight consumers. Reattachment allows the existing
watchdog to settle, remount and restart them. The precise physical cause of the
USB disconnect is not established: cable/connector, bridge, power supply, manual
unplugging or controller behavior remain possibilities. Disk surface failure is
not proven by the post-disconnect I/O errors alone.

## Evidence on this host

The last 24 hours contained 12 USB disconnect records across the two storage
paths (including an earlier port assignment). The media unit had four stop/start
cycles. Examples in IST on October 31:

| Event | Time |
|---|---|
| Both USB storage devices disconnect; filesystem journal/superblock I/O fails | 11:00:08 |
| Media services running after automatic recovery | 11:01:42 |
| WD HDD USB path `1-3` disconnects; journal write fails | 14:40:31 |
| Media services running after automatic recovery | 14:42:05 |

The WD path used a `14cd:6116` USB2 bridge with `usb-storage`; the Crucial path
used `152d:0583` USB3 with `uas`. Both were attached to PCI controller
`0000:00:14.0`, on separate USB2/USB3 root buses. These are observations, not a
reason to disable UAS globally: the most recent failure was the non-UAS HDD.
Port names and device letters are attachment-specific; discover UUID/model on
another host before interpreting logs.

At inspection, both USB devices had `power/control=on`, runtime status active,
and zero runtime-suspended milliseconds since their latest attachment.
[Kernel documentation](https://docs.kernel.org/driver-api/usb/power-management.html)
defines `on` as disallowing runtime autosuspend. Global usbcore autosuspend=2
does not override those per-device settings. This does not establish their state
before the latest attachment or rule out every controller/bridge power fault.
No system sleep/lid events were found in the inspected unit logs. The HDD's ATA
standby policy is separate from USB autosuspend; neither was changed during this
investigation, and the evidence does not prove standby caused the disconnect.

No kernel OOM kills were recorded in that 24-hour window. Running containers had
zero Docker restart counts and OOMKilled=false; system disk was 57% used, with
about 3.6 GiB memory available. Nginx, Docker and Tailscale had not restarted with
the media consumers. Main local HTTP and trusted HTTPS routes answered 200 at
inspection. This does not establish Internet/client availability during another
incident. The 17:42 ntfy and 17:43/17:46 Homepage restarts were deliberate widget
setup, later than the recorded storage outages.

## Distinct false Maintainerr alert

The alert worker's `ProtectHome=yes` hides `/root`. The root Docker CLI tried its
default `/root/.docker/config.json`, emitted an `Error loading config file`
warning, then successfully read the requested container logs. The worker included
Docker stderr when matching application errors, so this warning caused a false
`maintainerr:logs` failure despite no Maintainerr error lines in the sample.

The unit now creates a private mode-0700 `RuntimeDirectory=ohara-alerts-docker`
and sets `DOCKER_CONFIG=/run/ohara-alerts-docker`. Its read-only Docker commands
use an empty temporary CLI configuration instead of the hidden owner home.
`ProtectHome=yes` and the empty capability set remain. Systemd creates/removes
this directory for each run; no credentials/config are copied into it. Genuine
container stderr remains monitored, and warning text is not silently discarded.
The sandbox fault was reproduced in a disposable transient systemd unit; the
same read with the private runtime configuration produced no warning.

## Reproduce investigation and install the alert correction

Read [storage operations](storage-pool.md) and [alerts](alerts.md). Inspect actual
mounted UUIDs and current services before changing anything. These commands are
read-only and deliberately avoid printing Docker environments/private configs:

```sh
uptime
free -h
df -h /
systemctl --failed --no-pager
lsusb -t
lsblk -o NAME,TRAN,SIZE,FSTYPE,MOUNTPOINTS,MODEL
sudo journalctl -k --since '24 hours ago' --no-pager \
  -g 'USB disconnect|I/O error|EXT4-fs error|oom-kill|Out of memory'
sudo journalctl -u ohara-storage-watchdog.service --since '24 hours ago' \
  --no-pager -g '^Storage watchdog:'
sudo journalctl -u ohara-media.service -u ohara-mnt.mount \
  --since '24 hours ago' --no-pager
```

For current USB power policy, discover each disk's USB path with `udevadm info`
and `lsusb -t`, then read that path's `power/control`, `power/runtime_status` and
`power/runtime_suspended_time` under `/sys/bus/usb/devices`. Do not write global
power settings or copy another machine's USB paths.

The alert correction is part of the versioned unit template, so every subsequent
fresh installation gets it. Existing hosts need deliberate reinstallation; a Git
pull alone does not update `/etc/systemd/system/ohara-alerts.service`:

```sh
sudo scripts/ntfy install-alerts
sudo systemctl start ohara-alerts.service
systemctl show ohara-alerts.service --no-pager -p Result -p ExecMainStatus
sudo journalctl -u ohara-alerts.service -n 20 --no-pager
```

This requires the working private `.env`, authenticated ntfy, existing running
managed services and the actual installed watchdog config when a pool is enabled.
The installer backs up installed units, worker and private publisher config under
`/var/backups/ohara/ntfy-alerts-*`, validates units, reloads systemd and enables the
timer. It preserves watchdog recovery and persistent alert state. Follow
[alert rollback](alerts.md#verification-and-rollback) to restore the selected
backup if needed. Restoring the older unit also restores its false-warning risk.

## Physical isolation still needed

Confirm whether each logged event was intentional unplugging. If unexpected,
check the existing data cable, SATA/USB bridge, connectors and external HDD power
supply, changing one component/path at a time. The desktop WD disk's adapter/power
arrangement has not been verified remotely. Compare incident timestamps after
each controlled change; do not unplug mounted writable filesystems as a test.
Use the normal guarded media shutdown and clean unmount procedure before any
physical change. Preserve backups before filesystem maintenance; do not run fsck
on mounted pool branches. SMART and offline filesystem checks have not been run.

The watchdog mitigates an outage but cannot prevent a disappearing USB device.
Do not weaken the mount guard or force containers to use an unmounted directory;
that risks split writes/data damage. No reboot, forced unmount, repair, disk test,
USB driver quirk, standby change or hardware replacement was performed.

The corrected unit was installed on this host on 2026-10-31. An explicit worker
run completed with Result=success, ExecMainStatus=0, no unhealthy recorded checks
and an empty outbox; the prior false Maintainerr state recovered. All 243 unit
tests and setup/CLI/static checks passed. Real systemd sandbox reproduction and
live installed-worker execution were verified separately. No physical disconnect
or complete fresh Linux provisioning was performed for this correction.
