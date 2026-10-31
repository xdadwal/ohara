# ntfy notifications and host alerts

ntfy is an optional independent `ohara-ntfy` Compose project. Its non-root,
capability-free server publishes only `127.0.0.1:2586` and stores SQLite state on
local application storage, outside the mergerfs media pool. Host Nginx provides
`https://ntfy.xdadwal.in`. It has no Docker socket, SMTP, attachments, public
registration, Firebase credentials, web-push keys or shared authentication.
The main eleven-service setup/up commands do not start ntfy.

## Current host readiness

On 2026-10-31, the owner explicitly authorized generation of the ntfy-only
password; it was saved directly in private `.env` without displaying its value.
The owner selected Android, so no iOS/upstream relay is configured. This is a
specific owner-authorized exception, not a change to the default credential policy.

Production ntfy is running with native topic authentication and trusted HTTPS
at `https://ntfy.xdadwal.in`. The live Homepage card was verified through its
authenticated API, the exact AdGuard rewrite passed UDP/TCP checks, and the
host alert timer is installed/enabled. Authenticated test publishing succeeded;
actual Android background/mobile-data delivery remains owner verification.
Independent public reachability and reboot persistence have not been established
by the server-local checks. The exact live proxy is tracked under
`configs/nginx/deployed/ohara-ntfy.conf`.

## Inputs and preparation

Read AGENTS.md and adding-services.md first. Inspect actual mounts, ports,
certificate coverage, public DNS, private inputs and existing service state.
Verify the official version/digest in `versions.ntfy.env`; the reviewed image
supports amd64 and arm64. Do not copy this host's IP/certificate assumptions to
another server. The automatic proxy helper currently requires the existing
xdadwal.in wildcard certificate; adapt/review another host's proxy deliberately.

The owner supplies an independent `NTFY_PASSWORD` privately in the existing
mode-0600 `.env`: at least 16 characters, at most 72 UTF-8 bytes (bcrypt limit).
Never request the value in chat, choose one, reuse another service password, or
print resolved Compose/environment data. Optional non-secret inputs are:

```dotenv
NTFY_HOST=ntfy.xdadwal.in
NTFY_ROOT=/ohara/ntfy
NTFY_MOUNT=/
NTFY_IOS_RELAY=none
```

Confirm whether the phone is Android or iPhone before enabling a relay.
Android subscribes directly; enable the app's instant-delivery/background service
and allow its background operation. For iPhone instant delivery, the owner must
explicitly approve `NTFY_IOS_RELAY=https://ntfy.sh`. That relay receives the SHA256
of the topic URL and a message ID, not alert text or login credentials. Without
it, iOS delivery can be substantially delayed. No relay is assumed by default.

`NTFY_ROOT` must be separate from media and every existing application's storage;
`NTFY_MOUNT` is the expected local Linux filesystem mountpoint. Do not place it
on the pool whose failures it reports. Initial preparation creates only missing
owned directories and stores a bcrypt hash of the supplied password in a private
server configuration. Plaintext is not passed through the container environment.

```sh
scripts/ntfy check --static
# Supply NTFY_PASSWORD privately before prepare/check/up.
sudo scripts/ntfy prepare
scripts/ntfy check
scripts/ntfy up
scripts/ntfy status
```

Install distribution `python3-bcrypt` and `python3-yaml` if missing. `prepare`
preserves existing server configuration, authentication database and message
cache; reruns never reset users. Changing `.env` alone does not rotate an existing
password or change an already-prepared relay. Use supported ntfy account controls,
keep private inputs synchronized, and deliberately reconcile persisted settings.
Update the declarative password hash too: a UI-only password change may be
overwritten by auth-users on the next restart.
Declarative user/ACL configuration is provisioned by ntfy at startup; preserve
it rather than removing entries, which upstream may interpret as user deletion.

The `admin` account is a regular user with read/write access only to topic
`ohara-alerts`. Anonymous reads and writes are denied, including with a guessed
topic name. Other topics are denied. No administrator password or access token
is invented. The web app itself and health endpoint remain publicly readable;
this does not grant access to message data. Message cache retention is 24 hours.

## HTTPS, Homepage and DNS

Verify the intended hostname resolves to the real public IPv4 and the certificate
covers it before activation. Existing wildcard DNS may already cover ntfy; verify
rather than adding a record or modifying GoDaddy by assumption. Private topic
authentication must pass `scripts/ntfy status` before the proxy helper activates.
There is no unclaimed-owner signup flow to expose.

```sh
sudo scripts/ntfy-proxy --apply
scripts/ntfy homepage
scripts/ntfy dns
# Confirm local UDP and TCP DNS after the exact rewrite is merged:
dig @192.168.1.101 ntfy.xdadwal.in A
dig +tcp @192.168.1.101 ntfy.xdadwal.in A
```

Use the actual verified AdGuard address on another host. Public DNS and LAN DNS
are separate. The proxy helper backs up only its prior managed route, verifies
native authentication/TLS, tests Nginx and reloads; failure restores the old
route. HTTP redirects to HTTPS, preserving POST semantics with 308. Streaming,
WebSockets and long-lived subscriptions are supported. Request-URL logs are
suppressed because clients may put access tokens in URLs. The reusable rendering source is `configs/nginx/ntfy.template`. After successful
live activation, record the exact installed route as
`configs/nginx/deployed/ohara-ntfy.conf` and update its baseline README. Do not
claim a candidate route is already deployed. Preserve all other public and
LAN-only routes.

The Homepage helper selectively adds a plain ntfy card and backs up existing YAML
under ignored `local/ntfy-backups`. No ntfy password is forwarded to Homepage.
The DNS helper adds only the exact hostname to existing AdGuard rewrites and
rejects a conflicting entry. It does not change router/client DNS or publish DNS.
The seed Homepage card and initial AdGuard rewrite also cover ntfy for new setups.

## Phone subscription and delivery verification

Install the official ntfy app. Add server `https://ntfy.xdadwal.in`, sign in using
username `admin` and the supplied password, and subscribe to **ohara-alerts**.
Enable notification permission and appropriate background delivery. Then run:

```sh
scripts/ntfy test
```

This intentionally publishes one test notification to the owner-selected topic.
A successful HTTP publish is not proof of phone delivery: the owner must confirm
arrival with the app in the background/on mobile data as appropriate. Verify LAN
and external trusted HTTPS separately. Do not send credentials in topic URLs,
query strings, screenshots or diagnostic output.

## Host service and disk alerts

After actual account authentication succeeds:

```sh
sudo scripts/ntfy install-alerts
systemctl list-timers ohara-alerts.timer
sudo journalctl -u ohara-alerts.service -n 30 --no-pager
```

The installer records all eleven main services, ntfy, the Nginx HTTP edge, and the optional Immich,
Bambuddy, Maintainerr and AdGuard projects currently running. Rerun deliberately
after adding/removing optional services. It copies only the validated ntfy
publishing credentials and check definitions to root-only `/etc/ohara/alerts.json`;
the single editable credential source remains `.env`. These credentials have the
same single-topic account scope. The root-owned standalone worker is
`/usr/local/lib/ohara/alerts.py`. It does not load the repository or entire `.env`
at runtime, use a Docker socket, or restart any service.

A systemd timer checks local HTTP endpoints every minute. Two consecutive
failures trigger one high-priority notification; a subsequent successful check
triggers one recovery notification. HTTP 401/403 on protected root pages means
the application is answering; these checks do not establish full application
functionality. No repeating outage reminders are sent.

When a configured pool/watchdog exists, the installer reads its verified actual
UUIDs from `/etc/ohara/storage-watchdog.json`. A missing disk or absent mergerfs
mount triggers an immediate transition on the next timer check (usually within
a minute). Metadata-only checks do not wake the HDD. One storage-pool incident
suppresses the eight redundant media-service failures, while unrelated services
continue to be checked. The storage watchdog remains independently responsible
for recovery; notifications do not alter mount/restart behavior.

System/root filesystem free space below 10 percent is also reported after two
checks. Pool free-space monitoring is intentionally not polled, to preserve idle
spindown. Printer events, individual torrent failures and application-specific
error streams are not automatically configured by this initial monitoring setup.

State and a bounded retry outbox persist under root-only
`/var/lib/ohara-alerts/state.json`. If ntfy is temporarily unavailable, up to 100
pending transitions are retained and retried on later ticks, ten per tick. At
capacity the oldest pending entries are discarded with a journal warning. A
worker crash around publish/state persistence may repeat a notification; delivery
is not exactly-once. Pause the timer and its current worker for planned maintenance
if alerts should be suppressed:

```sh
sudo systemctl stop ohara-alerts.timer
sudo systemctl stop ohara-alerts.service
# After maintenance:
sudo systemctl start ohara-alerts.timer
```

A monitor and notification server on this same machine cannot notify in real time
about a complete host/power/network outage. Pending notices may arrive after
recovery, but independent outage detection requires a separately located checker;
none is introduced by this deployment.

## Persistence, backup, upgrades and rollback

The ntfy container restarts unless stopped; the enabled alert timer starts at
boot. They do not depend on the media pool. A host reboot, physical HDD unplug or
forced spindown is not necessary to test setup. Test event transitions using unit
fixtures, a disposable ntfy project and the explicit phone test above.

Keep the entire `NTFY_ROOT` (private configuration, auth database and cache),
`.env`, relevant root-only alert files and Nginx route in an encrypted backup if
backups are requested. Stop ntfy for consistent SQLite filesystem copies; preserve
existing data during upgrades. Review upstream release/migration notes and update
the pinned image in a PR before explicit recreation.

Rollback is scoped: disable/stop `ohara-alerts.timer` and its worker, stop ntfy with
`scripts/ntfy stop`, and restore/remove only its Nginx route after `nginx -t`.
Deliberately reconcile its Homepage card and exact AdGuard rewrite. Preserve all
databases, configuration and unrelated services. Installed worker/config backups
are under root-only `/var/backups/ohara/ntfy-alerts-*` and proxy backups under
`/var/backups/ohara/ntfy-proxy-*`. Never blanket-prune containers or volumes.

Verification commands:

The CI configuration job uses an isolated Python interpreter and explicitly
installs `PyYAML==6.0.3` and `bcrypt==4.3.0` before unit tests. Local host setup
uses the distribution packages above. Container CI prepares ntfy's pinned image
alongside the other smoke-test images, then runs the disposable ntfy/proxy checks.

```sh
python3 -m unittest discover -s tests -v
tests/test_setup.sh
tests/test_cli.sh
tests/static.sh
python3 tests/smoke_ntfy.py
```

Report static tests, disposable runtime tests, real host deployment, LAN/external
reachability and observed phone delivery separately. The implementation guide
alone is not evidence the private password or phone onboarding is complete.

References: [official installation](https://docs.ntfy.sh/install/),
[access control and configuration](https://docs.ntfy.sh/config/),
[phone subscription and Android instant delivery](https://docs.ntfy.sh/subscribe/phone/),
[iPhone wake-up relay](https://docs.ntfy.sh/config/#ios-instant-notifications).

## Rename the initial account and rotate its password

The owner requested username `admin` and the updated NTFY_PASSWORD on 2026-10-31,
explicitly accepting a password outside the usual minimum-length policy. Save
`NTFY_ALLOW_SHORT_PASSWORD=true` in private .env only when that exception is
explicitly authorized. The default remains 16 characters; empty values and more
than 72 UTF-8 bytes are always rejected. No other service's policy is weakened.
The username does not imply administrator privileges: the existing regular role
and topic permissions are preserved.

ntfy v2.35.0 has no username-rename CLI. The explicit helper stops ntfy, backs up
its auth database/private server config under `/var/backups/ohara/ntfy-account-*`,
renames only the existing username while retaining its ID/related records, and
updates its declarative password hash/ACL username. The supported server startup
provisions the new password. It verifies authentication and unchanged ID/role;
failure restores the original auth state. Ambiguous accounts or an unreviewed
schema/release are refused. Cached messages are not rewritten or deleted.

```sh
sudo systemctl stop ohara-alerts.timer ohara-alerts.service
sudo scripts/ntfy rotate-account
sudo scripts/ntfy install-alerts
scripts/ntfy status
scripts/ntfy test
```

Alert installation refreshes the root-only publisher identity/password and worker
and resumes the timer. If rotation fails, leave the restored account intact and
resume the existing timer after inspecting the private error; do not reset/delete
the auth database. Update saved phone/web logins to `admin` and the current private
password, keeping the same server and `ohara-alerts` topic. Existing preferences,
subscriptions and access tokens remain associated with the preserved account ID.
