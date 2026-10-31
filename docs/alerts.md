# Host and application alerts

Use the authenticated private `ohara-alerts` topic on the optional local ntfy
server. Follow [ntfy setup](ntfy.md) first, including anonymous denial checks.
Notifications use no external publishing relay. Android phone delivery must be
confirmed separately from a successful publish.

## Installation and repeatable configuration

The prerequisites are the existing supported Linux/systemd/Docker installation,
Python standard library, `dig` (`sudo apt-get install dnsutils` on Debian/Ubuntu), and working ntfy
credentials in the private mode-0600 `.env`. Never source that file. Optional
printer observation needs the owner's existing read-status-only
`HOMEPAGE_VAR_BAMBUDDY_API_KEY`; new installations obtain that key through
[Bambuddy onboarding](bambuddy.md). Seerr uses the existing private
`HOMEPAGE_VAR_SEERR_API_KEY`, not a new account/token. Missing optional printer
keys leave printer event monitoring unconfigured; supply privately and reinstall.

Inspect `scripts/status`, `docker ps`, `systemctl status tailscaled` and mounted
storage first. For a media pool, configure and verify the target's real UUIDs
using [storage setup](storage-pool.md), never example identities. The installer
reads `/etc/ohara/storage-watchdog.json`, the running managed Compose inventory,
configured `ADGUARD_BIND_IP`, and the ntfy/Seerr/Jellyfin hostnames. It does not
change Tailscale preferences, DNS settings, printer controls or watchdog recovery.

```sh
sudo scripts/ntfy install-alerts
sudo scripts/ntfy seerr
sudo systemctl start ohara-alerts.service
systemctl list-timers ohara-alerts.timer
sudo systemctl status ohara-alerts.service --no-pager
sudo journalctl -u ohara-alerts.service -n 30 --no-pager
```

`install-alerts` verifies ntfy authentication before installing. It copies only
ntfy publishing credentials, the optional Bambuddy read-only key and validated
check definitions to root-only `/etc/ohara/alerts.json`. The standalone root worker
is `/usr/local/lib/ohara/alerts.py`; its timer runs every minute. State and retry
outbox persist under `/var/lib/ohara-alerts`, independently of media storage.
Repository source files are templates, not the installed worker/configuration.
Rerun installation after changing credentials, monitored services or hostnames.
Existing-state reinstall preserves alert state and backs up installed worker,
configuration and units in `/var/backups/ohara/ntfy-alerts-*`. It inventories only
currently running managed services; start intended services before installation.
Stopped retired containers and unrelated projects are excluded. Pause the timer
and worker during deliberate maintenance, then resume it; do not reinstall while
intended monitored services are stopped.

`seerr` backs up only the current native ntfy provider to root-private
`/var/backups/ohara/ntfy-seerr-*/provider.json`, tests publishing using Seerr's
native endpoint, then saves/verifies the provider through its supported API.
Other notification providers and request/user automation are preserved. An
already enabled different ntfy destination is refused for review. Reapply this
command after ntfy credential rotation. Seerr persists the scoped ntfy account
credentials in its own private application settings; they never go to Homepage.

## Triggers and limits

| Component | Trigger |
|---|---|
| Storage | Missing configured disk/pool, unsafe/read-only mount reported by watchdog, three recovery attempts exhausted in an hour, return to healthy storage; watchdog timer/observation failure |
| Bambuddy | Printer disconnected/reconnected, hardware errors, transition to FINISH, FAILED or PAUSE; service/API observation failure |
| AdGuard | Local service failure and actual DNS lookup failure against its configured private LAN IP |
| Maintainerr | Local service failure and errors/fatal entries in its container logs since the previous sample |
| Nginx | HTTP service failure, local trusted TLS/SNI route failures or HTTP 5xx for ntfy/Seerr/Jellyfin, certificate under 14 days and under 3 days, failed Certbot service result |
| Tailscale | Backend not Running or this node offline; read-only CLI failure |
| Containers | Expected container absent/stopped, unhealthy, at least three observed restarts within five minutes, transition to OOMKilled |
| Seerr | Native Request Pending Approval, Request Automatically Approved, Automatic Request events; no historical backlog |

Ordinary health failures require two successive samples; recovery needs one.
Disk loss, watchdog unsafe/exhausted state and critical certificate expiry alert
on the next observation. There are no repeating outage reminders. Log errors
produce one transition until a clean sampled interval, then a recovery. Messages
never contain raw logs, API responses or credentials. The worker reads selected
Docker state via the host CLI (therefore the root daemon socket); no container
gets a Docker socket. It reads no container environments or healthcheck output.

Pool loss suppresses HTTP/container checks for the eight media consumers, avoiding
a cascade while the independent watchdog recovers. No monitoring action starts,
stops or restarts services. Disk checks inspect kernel metadata and watchdog state,
not media files or pool free space. Application probes can themselves cause normal
application activity; metadata checks alone do not establish physical HDD standby.

Polling is approximately minute-resolution: short printer events and crashes
entirely between samples can be missed. Printer power-off counts as disconnected;
PAUSE is reported whether manual or unexpected. OOMKilled is the current Docker
state flag, not a historical kernel audit. Maintainerr reads the last 200 log
lines per sample; a burst larger than that can lose events. It does not run rules
or infer successful cleanup from a healthy web UI. DNS probes test an A lookup
for `example.org`; they do not audit every configured upstream. Local TLS tests
exercise the Nginx route and trust chain, not router forwarding or remote Internet
reachability. A single host cannot alert immediately when it or its network is
offline; an external observer remains a separate option.

The persistent outbox retries failed ntfy delivery (100 messages, ten per tick).
A crash around publication/state persistence may duplicate a message. Seerr uses
its own native delivery behavior, separately from the worker outbox.

## Verification and rollback

Run the repository checks in AGENTS.md and
`python3 -m unittest discover -s tests -p test_alert_integrations.py -v` for
simulated disconnect, recovery, crash-loop, OOM and printer transitions. Do not
unplug a live disk, stop SSH/networking, create a real request or start a print to
test alerts. `scripts/ntfy seerr` sends a labelled test without creating a request.
Confirm that test on the owner's Android phone; server publishing alone is not
proof of phone delivery.

To roll back host monitoring, stop `ohara-alerts.timer` and
`ohara-alerts.service`, restore the selected private backup's `alerts.json` to
`/etc/ohara/alerts.json` (root:root 0600), `alerts.py` to
`/usr/local/lib/ohara/alerts.py` (root:root 0644), and its unit files to
`/etc/systemd/system` (root:root 0644). Run `sudo systemctl daemon-reload`, start
`ohara-alerts.service`, inspect its result, then start `ohara-alerts.timer`.
Keep backups/state. To disable only Seerr notifications, disable its ntfy provider
in Settings → Notifications; restore exact prior provider through the supported
API with the private backup and existing Seerr key if required. Never paste the
backup or credentials into a shell command or chat. No ntfy database, request,
printer, media or watchdog configuration needs removal.

## Homepage

The installed Homepage includes its native ntfy widget, documented
[upstream](https://gethomepage.dev/widgets/services/ntfy/). It displays the latest
message, priority and receipt time. The existing ntfy link remains active; its
widget is not enabled because there is no separate owner-supplied read-only ntfy
credential. Do not forward `NTFY_PASSWORD` to Homepage, make the topic public or
generate credentials to work around this. Provision a distinct reader account
with read-only ACL for this topic and supply its token privately before adding a
selective widget integration and runtime credential allowlist.

## Verified on the current host (2026-10-31)

The expanded host worker was installed and its oneshot completed successfully;
83 recorded checks were healthy with an empty retry outbox. Seerr's native test
published successfully, and its configured new-request events were read back
through the supported API. No real request, print, drive fault or service outage
was induced. Android receipt is still owner verification, and local checks do
not establish external reachability. Initial Docker probes revealed containers
without healthchecks; the corrected projection treats those as running-only
checks. Homepage's local HTTP health probe uses its accepted internal localhost
Host header. Neither fix changes application authentication or public routing.
