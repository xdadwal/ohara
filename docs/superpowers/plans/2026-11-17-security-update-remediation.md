# Security update remediation tracker

**Status:** approved planning/tracking document; no live deployment is authorized
by this file alone. Apply each item only after a reviewed change, the required
state backup, and explicit owner approval for that maintenance action.

**Audit date:** 2026-11-16. Re-read upstream release notes and re-resolve image
digests immediately before preparing each change; versions below must not be
treated as permanent package-manager or registry state.

**Owner direction (2026-11-17):** proceed with the one-by-one remediation plan,
but **do not upgrade the Seerr image**. Keep the separately approved public-route
containment for Seerr unless the owner later gives new instructions.
Schedule host package changes last unless preparation of another item finds a
verified dependency that requires applying H-01 earlier.

## Goal and scope

Track security-driven and reviewed maintenance for the host, the eleven-app main
Compose project, and the approved optional projects. Keep every change separately
attributable, preserve accounts/data/networks/routes, and distinguish repository
checks from disposable runtime checks, real provisioning, and public/LAN reachability.

This document does not add services, credentials, shared authentication, Docker
socket access, public database ports, or infrastructure. Canonical deployment files
are listed in [deployment layout](../../deployment-layout.md). Read
[operations](../../operations.md) and the relevant service guide before a live
change. Private inputs remain in root `.env` and ignored `local/` files; never
print them, source them, or pass the whole dotenv to a container.

## Universal workflow

Use one branch and PR per row wherever practical. The only approved coupled groups
are Immich's release-matched dependencies and Bambuddy's matching OrcaSlicer sidecar.

1. **Research:** read advisories, release/migration notes, and the current registry
   manifest. Confirm the target release still exists and has the required architecture.
2. **Prepare:** update only the canonical version manifest and documentation/tests
   required by that item. Do not change live state merely to prepare a PR.
3. **Review:** run the relevant checks below and open a PR.
4. **Owner approval:** obtain explicit approval for live application and any backup
   or deferred-backup decision.
5. **Back up:** stop database writers or use each application's supported export.
   Record commit, image tag/digest, private storage scope, and rollback location.
6. **Apply:** use the documented lifecycle helper from the repository root.
7. **Verify:** record static, disposable, real-host, and public/LAN outcomes
   separately. Health checks alone are not functional verification.
8. **Close or roll back:** update this tracker with evidence and limitations.

Baseline repository checks for image/version changes:

```sh
python3 -m unittest discover -s tests -v
tests/test_setup.sh
tests/test_cli.sh
tests/static.sh
```

Relevant project checks:

```sh
scripts/check --static
scripts/immich check --static
scripts/bambuddy check --static
scripts/orcaslicer check --static
scripts/ntfy check --static
scripts/kutt check --static
scripts/maintainerr check --static
scripts/adguard check
```

Existing disposable smoke tests may be used when their scope matches the change:

```sh
tests/smoke.sh
python3 tests/smoke_immich.py
python3 tests/smoke_bambuddy.py
python3 tests/smoke_kutt.py
```

Do not claim host provisioning, public reachability, or LAN reachability from a
static or disposable check.

## Tracker

| ID | Scope | Priority | State |
|---|---|---:|---|
| P-00 | This plan/tracking document | Foundation | Complete when merged |
| H-01 | Host security packages and reboot | P0 | Scheduled last by owner; escalate only for a verified dependency |
| SE-01 | Seerr public-route containment | P0 | Prepared; live application pending |
| SE-02 | Seerr image upgrade | P0 | **Owner skipped; do not prepare or apply** |
| HP-01 | Homepage 2.5.0 to 2.8.0 | P0 | Prepared; live application pending |
| IM-01 | Immich release-matched update | P1 | Prepared; live application awaits owner backup decision |
| NT-01 | ntfy 2.35.0 to 2.38.1 | P1 | Prepared; live application pending |
| AG-01 | AdGuard Home 0.107.79 to 0.107.80 | P1 | Prepared; live application pending |
| MT-01 | Maintainerr 3.31.0 to 3.32.0 | P1 | Prepared; live application pending |
| OST-01 | OpenSpeedTest digest refresh | P1 | Prepared; live application pending |
| JF-01 | Jellyfin 12.2 to 12.4 | P2 | Prepared; live application pending |
| SO-01 | Sonarr base-image refresh | P2 | Prepared; live application pending |
| PR-01 | Prowlarr 2.6.5 to 2.7.0 | P2 | Prepared; live application pending |
| LI-01 | Lidarr 3.1.0 to 3.1.6 | P2 | Prepared; live application pending |
| QB-01 | qBittorrent 5.2.4 to 5.3.0 | P2 | Prepared; live application pending |
| RA-01 | Radarr 6 to 7 migration | P2 | Prepared; live migration pending |
| BB-01 | Bambuddy + matching OrcaSlicer | P3 | Prepared; live application pending |
| KU-01 | Kutt PostgreSQL same-version refresh | P3 | Prepared; live application pending |
| BZ-01 | Bazarr containment/release monitoring | P1 | Blocked on fixed stable |
| NV-01 | Navidrome 0.64.2 | Monitor | Current |
| CB-01 | Certbot 4.0.0 | Monitor | Current |
| KU-02 | Kutt application 3.2.6 | Monitor | Current |
| FO-01 | Separate portfolio service | Optional | Separate audit required |

## H-01 — Host security packages and reboot

**Target at audit time:** Nginx `1.26.3-3+deb13u10`, Linux `6.12.117`,
Docker Engine `29.9.3`, and the current Debian security candidates for zlib,
expat, CA certificates, containerd, Compose, and Tailscale. Re-resolve all
candidates on the maintenance day.

**Scheduling (owner direction, 2026-11-17):** perform this after the application
and optional-project items unless a reviewed target image or runtime requirement
depends on a newer host package, an active incident requires earlier patching, or
the owner changes the order. During each earlier item, record whether it has such
a dependency. If one is found, pause that item and obtain explicit owner approval
before moving H-01 forward. The audit found no such dependency for the planned
application updates.

Prerequisites: owner-approved reboot window, verified fallback LAN/SSH path,
known storage mount state, and no mid-flight application remediation.

Inspect without changing state:

```sh
uname -r
apt list --upgradable
nginx -v
docker version
docker compose version
tailscale version
systemctl list-timers --all
```

Apply only in the approved window:

```sh
sudo apt-get update
sudo apt-get full-upgrade
sudo reboot
```

Use `full-upgrade` because ordinary `upgrade` may retain the kernel. Preserve the
existing Tailscale role/policy: ordinary OpenSSH only, no Tailscale SSH, DNS
acceptance, subnet routing, exit node, Serve, or Funnel changes.

Post-reboot verification:

```sh
uname -r
nginx -v
docker version
docker compose version
tailscale version
systemctl --failed
scripts/status
scripts/immich status
scripts/adguard status
scripts/maintainerr status
scripts/ntfy status
scripts/kutt status
scripts/bambuddy status
scripts/orcaslicer status
```

Verify `/ohara/mnt` and all configured pool branches remain mounted, the
storage-watchdog timer is unchanged, public HTTPS routes work, LAN-only routes
still deny non-LAN clients, and remote SSH still uses ordinary OpenSSH. Check
Certbot timer state separately. Roll back a defective kernel by booting the
previous installed kernel; package rollback requires the recorded pre-change
package versions and available cache/snapshot. Do not downgrade application data.

## SE-01 — Seerr public-route containment

Seerr `3.5.2` is affected by an unauthenticated `/imageproxy` disk-exhaustion
issue ([GHSA-849x-56wc-5rrv](https://github.com/seerr-team/seerr/security/advisories/GHSA-849x-56wc-5rrv)).
The owner has skipped SE-02, the fixed-image upgrade. Therefore this containment
must remain deliberate and documented.

Preferred owner choice: restrict the whole Seerr HTTPS host to LAN/owner access.
If partial public use is required, add a reviewed deny location before Seerr's
general proxy and test encoded/path-equivalence variants:

```nginx
location ^~ /imageproxy {
    return 404;
}
```

If any variant is not unambiguously denied, use full-host containment instead.

Update both the repository baseline `configs/nginx/deployed/ohara.conf` and the
installed `/etc/nginx/conf.d/ohara.conf` in the same deliberate change. Follow
[the deployed baseline instructions](../../../configs/nginx/deployed/README.md):
compare first, preserve a private rollback copy, test with `sudo nginx -t`, and
reload Nginx only after validation. Do not overwrite unrelated sites.

Verify:

- Public or non-owner clients cannot reach `/imageproxy` variants.
- Containment does not alter Homepage, Jellyfin, OpenSpeedTest, Navidrome, or LAN routes.
- Seerr normal UI/request behavior is either intentionally restricted or, under
  the partial choice, still usable except for the denied proxy path.
- The repository file and installed file match after the change.

Rollback is the saved Nginx file plus `sudo nginx -t && sudo systemctl reload nginx`.
No Seerr container, account, database, or image pin changes during SE-01.

## SE-02 — Seerr image upgrade

**Owner skipped on 2026-11-17. Do not prepare or apply this item.** Do not remove
SE-01 as a completion step. Revisit only if the owner explicitly reverses this
decision and a fixed release/image has been independently verified.

## HP-01 — Homepage security update

Update `HOMEPAGE_IMAGE` in `versions/stack.env` from v2.5.0 to a reviewed v2.8.0
digest. The installed version is in the affected range for
[GHSA-qxcr-4rv3-v23r](https://github.com/gethomepage/homepage/security/advisories/GHSA-qxcr-4rv3-v23r),
fixed in v2.6.0. Preserve the private password/cookie inputs and edited dashboard files.

Back up Homepage configuration before recreation. Apply with:

```sh
scripts/check --static
scripts/up
scripts/status
```

Verify failed unauthenticated dashboard access, correct password login, bad-password
rejection, secure cookies, existing links, Jellyfin/Seerr/Immich/resource/OpenSpeedTest
widgets, and no broadened credential. Roll back by reverting the reviewed pin and
recreating through `scripts/up`; restore the configuration backup only if needed.

## IM-01 — Immich release-matched update

Compare `compose/immich.yaml` and `versions/immich.env` with the official v3.4.1
release files. v3.4.0 contains a large security-fix batch and v3.4.1 is its
correction release. Update only release-matched dependency pins that upstream
also changed; likely targets are Immich server and Valkey, with the Immich-specific
PostgreSQL image included only if upstream moved it. Never substitute generic
PostgreSQL.

Before live work, the owner must choose among:

1. Proceed with a documented same-host consistent backup while independent
   restore testing remains deferred.
2. Establish independent backup/restore first.
3. Defer IM-01.

Do not imply that deferred independent backup testing is implemented.

Pause uploads/jobs, create the supported database dump, stop Immich, and privately
back up `IMMICH_LIBRARY_ROOT`, database state/dump, managed settings, commit, and
image pins. Preserve `/data`, machine-learning disabled, Google-only invite-only
OAuth, `autoRegister=false`, disabled password login, users, albums, and jobs.

Apply:

```sh
scripts/immich check --static
sudo scripts/immich up
scripts/immich status
```

Verify local ping, public Google login, timeline, representative photo/video,
small upload and byte-identical download, albums, thumbnails/metadata jobs, ML
disabled, invite-only registration, and the Homepage statistics widget. Rollback
requires stopping the project, restoring the pre-change library/database pair,
reverting all related pins together, and restarting; do not assume the old server
can read a migrated database.

## NT-01 — ntfy security update

Update `NTFY_IMAGE` in `versions/ntfy.env` from v2.35.0 to reviewed v2.38.1.
Before recreation, stop ntfy for a consistent copy and privately back up its
SQLite/auth/config state, root-only alert files, and route references. Preserve
the account ID, ACLs, tokens, message cache, `ohara-alerts`, loopback backend,
and Homepage reader scope. Do not rotate credentials for this update.

Apply:

```sh
scripts/ntfy check --static
sudo scripts/ntfy up
scripts/ntfy status
scripts/ntfy test
```

Verify authenticated publishing, denied anonymous topic access, disabled public
signup, separately confirmed phone delivery, host alert timer health, Seerr native
delivery, and the Homepage reader. Roll back by stopping ntfy and its alert worker,
restoring the prior private state, reverting the pin, and re-running status/test.

## AG-01 — AdGuard Home security update

Update `ADGUARD_IMAGE` in `versions/adguard.env` from v0.107.79 to reviewed
v0.107.80. Stop the service for a consistent private copy of `conf` and `work`;
include private inputs only in the existing encrypted backup process. Preserve
accounts, filters, rewrites, reserved-LAN bind, client allowlist, loopback
dashboard, and disabled DHCP.

Apply:

```sh
scripts/adguard check
sudo scripts/adguard up
scripts/adguard status
```

From an approved LAN client, verify resolution, an allowed domain, a blocked
domain, and local rewrites. Separately verify dashboard/DNS are not public and
DHCP remains disabled. Do not change router/client DNS as part of this image update.
Roll back by restoring prior `conf`/`work`, reverting the pin, and re-running LAN tests.

## MT-01 — Maintainerr dependency-security update

Update `MAINTAINERR_IMAGE` in `versions/maintainerr.env` from 3.31.0 to reviewed
3.32.0. Stop Maintainerr and privately copy its entire state directory. Record
existing connections/rules/collections/tags without publishing private details.

Apply:

```sh
scripts/maintainerr check --static
sudo scripts/maintainerr up
scripts/maintainerr status
```

Verify the UI/API remains LAN-only, Jellyfin/Seerr/Radarr/Sonarr connections remain,
rules and schedules retain their enabled/disabled state, and no cleanup action runs.
Roll back by stopping the service, restoring state, reverting the pin, and restarting;
never reset accounts or delete collections to recover.

## OST-01 — OpenSpeedTest digest refresh

Update `SPEED_IMAGE` in `versions/stack.env` from the old pinned mutable-tag
snapshot to the reviewed current digest. Confirm the upstream page, required
architecture, upload behavior, and compatible frame headers.

Apply:

```sh
scripts/check --static
scripts/up
scripts/status
```

Verify the HTTPS page, Start control, real download, nontrivial upload, Homepage
iframe compatibility, and Nginx buffering behavior. Roll back by reverting the old
reviewed digest and recreating with `scripts/up`.

## JF-01 — Jellyfin update and theme refresh

Update `JELLYFIN_IMAGE` from 12.2 to reviewed 12.4. First review every intervening
release for database/plugin/transcoding/Nginx changes. The cited historical critical
issue affects versions before 12.0, so 12.2 is not in that affected range.

Privately back up config/database, generated theme state, Enhanced integration,
branding, and user preference snapshots. Confirm no active playback. Preserve
Movies/TV/Music libraries, users, branding, plugin settings, and Intro Skipper policies.

Apply:

```sh
scripts/check --static
scripts/up
sudo scripts/jellyfin-theme install
scripts/status
```

Verify login, movie/TV playback, retained Music library, representative transcoding
and direct play, Abyss theme after a hard refresh, Enhanced plugin, Intro Skipper
policy, Seerr connection, and WebSockets. Roll back by reverting the pin, restoring
theme state if needed, and restoring the pre-change database if migration occurred.

## SO-01 — Sonarr base-image refresh

The application remains `4.0.20.3014`; refresh `SONARR_IMAGE` from the older
LinuxServer build to the reviewed current digest. Back up Sonarr config/database.
Review the LinuxServer changelog, then update the pin and apply through the reviewed
PR with `scripts/up`.

Verify series/root folders, indexers, qBittorrent client, quality profiles,
completed-download handling, and an interactive search that does not start a download.
Roll back by reverting the pin; restore the database snapshot only if startup migration
changed state unexpectedly.

## PR-01 — Prowlarr update

Update `PROWLARR_IMAGE` from 2.6.5.5623 to reviewed 2.7.0.5723. Back up
config/database and privately record indexer/sync targets. Apply through `scripts/up`.

Verify private UI access, preserved indexer definitions and health, sync to
Radarr/Sonarr/Lidarr, and no credential leakage in logs. Roll back by reverting the
pin and restoring state only if required.

## LI-01 — Lidarr update

Update `LIDARR_IMAGE` from 3.1.0.4875 to reviewed 3.1.6.5079. Back up
config/database. Preserve artists, root folders, quality profiles, indexers, and
qBittorrent client. Apply through `scripts/up`.

Verify artist inventory, music root, indexer connectivity, download-client
connectivity, and that deployment itself does not search or acquire music. Roll back
by reverting the pin and restoring state only if required.

## QB-01 — qBittorrent update

Update `QBITTORRENT_IMAGE` from 5.2.4 to reviewed 5.3.0. Stop qBittorrent for a
private backup of config and BT_backup state. Record torrent count, categories,
save paths, and paused/running state. Confirm managed Arr completed-download cleanup
remains disabled and the approved storage/seeding policy is unchanged.

Apply through `scripts/up`. Verify WebUI, unchanged torrent count/categories/save
paths, no unexpected resume or deletion, 240-minute stop behavior, data preservation,
and Arr connectivity. Rollback is stop, revert pin, restore config/BT_backup if needed,
restart, and verify torrent state.

## RA-01 — Radarr major migration

Update `RADARR_IMAGE` from 6.4.4 to reviewed 7.0.3 only after reading all official
v7 migration requirements. Back up config/database and record movie count, root
folders, indexers, quality profiles, custom formats, lists, and download clients.
Confirm no active import and obtain explicit owner approval.

Apply through `scripts/up` in a maintenance window and monitor startup migration
locally. Verify movie count, root folders, profiles/formats, indexers, qBittorrent,
existing paths/hardlinks, interactive search, Seerr requests, and that no unwanted
search/redownload occurs. Roll back by stopping Radarr, restoring the pre-v7
database/config, reverting the pin, and restarting; never run v6 against a migrated
v7 database.

## BB-01 — Bambuddy and matching OrcaSlicer update

Bambuddy 1.2.5.7 is already newer than the historical critical advisory fixed before
0.1.7; this is normal maintenance. Update Bambuddy and its sidecar together only after
confirming an exact release-matched OrcaSlicer tag for Bambuddy 1.3.1.

Use Bambuddy's supported backup path, stop the sidecar, and privately copy sidecar
state. Preserve owner accounts, printer/access settings, archive/SQLite directories,
bridge networking, resource limits, no Docker socket, no printer-device passthrough,
loopback backend policy, and public native login without MFA.

Apply:

```sh
scripts/bambuddy check
sudo scripts/bambuddy up
scripts/bambuddy status
scripts/orcaslicer check
sudo scripts/orcaslicer up
scripts/orcaslicer status
```

Verify native login, printer status, camera/archive behavior, sidecar health, `.3mf`
upload and slicing, and that deployment does not start/queue a print. Roll both pins
back together and restore sidecar/Bambuddy backups as required.

## KU-01 — Kutt PostgreSQL refresh

Keep the Kutt application at v3.2.6. If upstream's `postgres:17.11-alpine3.24` tag
has a newer reviewed digest, refresh only `KUTT_POSTGRES_IMAGE`. First run:

```sh
sudo scripts/kutt backup
```

Preserve the database volume, JWT secret files, users, links, statistics,
independent network, and no-public-PostgreSQL policy. Apply with `sudo scripts/kutt up`
and verify `sudo scripts/kutt status`, owner login, redirects, link editing, regular-user
behavior, and LAN-only owner/admin routes. Roll back by reverting the same-version pin;
use the backup only if database integrity is questioned.

## BZ-01 — Bazarr containment and monitoring

Bazarr stable 1.6.2 has upstream advisories, but no fixed stable image was observed.
Do not silently switch to beta. Verify Bazarr remains LAN-only and backend 6767 is not
public. Optionally tighten its existing LAN route or temporarily stop Bazarr if the
owner accepts the availability impact. Preserve subtitle languages/providers and all state.

Recheck upstream until a fixed stable image exists. If one appears, prepare a separate
reviewed upgrade with config/database backup, then verify Radarr/Sonarr connections,
languages, providers, manual search, and existing subtitles. A beta upgrade requires a
separate explicit owner risk acceptance and is not treated as stable remediation.

## Monitor-only items

- **NV-01 Navidrome:** installed 0.64.2 was current at audit. Do not change the pin;
  recheck releases later.
- **CB-01 Certbot:** installed 4.0.0 had no pending package. Verify timer/renewal state
  during H-01; do not alter certificates for an application update.
- **KU-02 Kutt application:** installed 3.2.6 was current. Only KU-01 is planned.
- **FO-01 Portfolio:** inspect its separate repository/deployment independently; it is
  not part of Ohara's Compose image inventory.

## Execution order

1. Merge this tracker.
2. SE-01: contain the public Seerr route.
3. HP-01: update Homepage.
4. OST-01: refresh OpenSpeedTest.
5. IM-01: update release-matched Immich after the owner's backup decision.
6. NT-01: update ntfy.
7. AG-01: update AdGuard Home.
8. MT-01: update Maintainerr.
9. JF-01: update Jellyfin and refresh its theme.
10. SO-01: refresh Sonarr.
11. PR-01: update Prowlarr.
12. LI-01: update Lidarr.
13. QB-01: update qBittorrent.
14. RA-01: migrate Radarr.
15. BB-01: update Bambuddy/OrcaSlicer together.
16. KU-01: refresh Kutt PostgreSQL.
17. Keep BZ-01 contained and monitor for a fixed stable Bazarr release.
18. Do not execute SE-02 under the current owner direction.
19. H-01: patch host packages and reboot in the final maintenance window, unless
    an earlier reviewed item found a verified host dependency.

## Completion evidence

For every applied item, record:

- advisory/release reason and reviewed target tag/digest;
- repository commit and PR;
- exact tests run and their scope;
- owner approval and maintenance window;
- backup scope/location and whether restore was tested;
- real-host status and functional checks;
- public/LAN reachability results where applicable;
- rollback result or reason rollback was not needed;
- remaining limitations or explicit owner deferral.
