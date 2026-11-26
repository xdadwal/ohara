# Verification record

Implementation verification on 2026-10-15:

- 29 Python tests passed, covering strict configuration, command-injection rejection,
  configuration preservation, package conflicts/failures, privilege checks, missing
  optional preflight tooling, storage permissions, Nginx rollback, and ACME hostname
  migration/failure recovery.
- CLI checks passed for help, invocation from another directory, noninteractive
  initialization, dry-run noncreation, unknown arguments, and config preservation.
- Bash syntax, ShellCheck, Python compilation, and Git whitespace checks passed.
- Real disposable Docker smoke checks passed on local arm64 Docker: Seerr,
  Copyparty, OpenSpeedTest, Pi-hole; authenticated file upload/download; anonymous
  read/write denial; UDP DNS fixture; rendered Nginx HTTPS routes/redirects; and
  a 35 MiB speed-test upload. Only upstream addresses and self-signed fixture
  certificates differ from production routing. Test projects are removed afterward.
- Image index manifests were checked for linux/amd64 and linux/arm64.
- Independent whole-branch review found two Important issues (preflight tool
  availability and certificate issuance after hostname changes). Both were fixed
  with regression tests. No Critical or Minor findings were reported.

CI reruns static/configuration checks and disposable application/proxy checks on
Ubuntu amd64. CI results belong to the particular commit reported in the PR.

Not yet verified: full installation twice on fresh Ubuntu 24.04/Debian 13 systemd
VMs, actual production mounts/ownership, real ACME issuance/renewal, router/ISP
reachability, externally trusted certificates, and DNS behavior from a real LAN
client. Before production use, perform those acceptance steps in operations.md.
No live server deployment, DNS change, router change, external credential rotation,
or deletion of existing application data was performed by this implementation.

Local macOS tests use Homebrew Python (Apple's system Python lacks scrypt). Host
bootstrap is Linux-only; supported Linux Python provides the required OpenSSL
scrypt implementation.

Hosted amd64 smoke behavior passed on the first run, but cleanup failed because
Linux preserves container-owned fixture files. Cleanup now restores ownership only
inside generated test data. Compose 2.38.2 static validation without secret files
was also reproduced and fixed; the test suite covers absent private configuration.

## Homepage addition

33 unit tests now include Homepage config/auth seeding and preservation, safe
ownership after partial setup failure, and rejection of disabled login or wildcard
host validation. Homepage v2.5.0's index was checked for amd64/arm64 and pinned.
The expanded five-application smoke test verifies anonymous redirect, a real
password/CSRF login, signed session access to configured service links, and
Nginx's password-attempt rate limit, alongside the previous file/DNS/speed checks.
Immich is confirmed for the same machine but remains unimplemented pending
hardware capacity, storage and backup details.

## Seerr media stack addition

37 unit tests pass, including backward-compatible media defaults, generated
credential/config preservation, private media port enforcement, non-root service
users, shared mount paths, read-only Jellyfin library storage and the new HTTPS
hostname. CLI checks include media-setup help from another working directory.
Bash syntax, ShellCheck, compilation and Git whitespace checks pass.

The disposable ten-application smoke test passes on local arm64 with the pinned
images: Jellyfin 12.2; Radarr 6.4.4.10685; Sonarr 4.0.20.3014;
Prowlarr 2.6.5.5623; qBittorrent 5.2.4. All five added images have amd64/arm64
index manifests. Media containers run directly as RUN_UID/RUN_GID; LSIO's s6
runtime uses a matching-ownership /run tmpfs, with dropped capabilities and
no-new-privileges, so startup does not recursively chown mounted configuration.

Runtime assertions cover seeded qBittorrent password login and protected API access,
Radarr/Sonarr download-client API connection tests, root folders, Prowlarr application
connection tests, Jellyfin first-user creation/login and libraries, Seerr first-owner
login, completed wizard, two enabled libraries, one default server per media type,
and a second connector run without duplicated download clients/application sync.
Rendered Nginx reaches tv.xdadwal.in over fixture TLS. Existing Homepage,
Copyparty, Pi-hole and speed-test acceptance checks also pass.

Current API compatibility fixes were verified in real containers: qBittorrent's
published/listening Web UI port must match, login success is verified by a protected
API rather than a version-dependent response body, Jellyfin requires first-user
initialization and a token in its Authorization header, and Seerr requires an
explicit empty URL base and writable-only Jellyfin settings payload.

Independent whole-diff review found no blocking issues. Its one minor upgrade
observation (existing Homepage files preserve the old link list) is documented
with manual insertion guidance in media.md. No production deployment was performed.
Indexer selection/accounts and real movie/episode search, transfer, import,
availability refresh and HTTPS playback remain real-host acceptance steps.
Fresh Linux provisioning, real ACME/public reachability and GPU transcoding remain
outside this disposable test's evidence.

## User-managed credential inputs (2026-10-16)

43 unit tests pass. New cases cover missing user inputs before storage creation,
invalid inputs before provisioning/package changes, literal punctuation/spaces,
private file permissions, blank template rejection, symlink rejection, errors that
do not echo secret values, and missing qBittorrent config preventing startup with
an upstream temporary password. Existing preservation and configuration checks pass.
Setup/CLI checks, Bash syntax, ShellCheck, compilation and whitespace checks pass.

The ten-service disposable smoke test passes on local arm64 using explicitly
supplied test input files with spaces, dollar signs, hash characters and equals
signs in passwords/session secret. It covers Homepage login, authenticated file
access, media API connections and reruns, Pi-hole DNS and Nginx HTTPS routes.
No deployment command generates passwords, acquisition API keys or Homepage secrets;
only password-hash salts and native application-issued tokens remain automatic.
Tracked templates contain empty fields. Test dummy inputs are isolated under tests/.
Independent review found no blocking issues; its literal-space test suggestion was
included in the expanded smoke run. Existing-account rotation and actual production
ownership/public deployment remain operator verification steps.

## Pi-hole removal (2026-10-16)

45 unit tests pass, including new assertions that only nine services remain,
DNS/admin ports are absent, retired LAN_IP/PIHOLE_PASSWORD inputs are ignored
without rewriting user files, and status iterates exactly the remaining services.
The stale DNS status tuple found during implementation/review was reproduced by
that status regression test, fixed, and the full suite passed afterward.
Setup/CLI, syntax, ShellCheck, compilation and whitespace checks pass.

The real nine-service disposable arm64 smoke passed: supplied-credential logins,
media API connections and rerun preservation, Homepage sessions/login rate limiting,
file authorization, Nginx TLS routing and a 35 MiB speed upload. Pi-hole's container,
image pin, storage preparation, credentials, environment file and DNS probes are
removed from active deployment code. Historical verification entries describe
older snapshots. Independent review reports no remaining blocking findings.
No live resolver/router changes, container stops or retired-data deletion occurred.

## Copyparty removal and current stack (2026-10-16)

48 unit tests pass. New checks cover the eight-service inventory, four fresh public
hostnames, removed 3923/files routes, ignored retired FILES_ROOT/FILES_HOST inputs,
no file-share storage/config creation, unconsumed legacy credentials, and ACME-only
handling for old certificate names without retired HTTPS application routes.
Setup/CLI, syntax, ShellCheck, compilation and whitespace checks pass. Independent
whole-diff review reports no blocking findings and independently confirms 48 tests.

The real eight-service disposable arm64 smoke passes with user-supplied test inputs.
It now includes normal runtime.check before startup, media accounts/connections,
rerun preservation, Homepage authentication/rate limiting, Nginx HTTPS routes and
a 35 MiB speed upload. Fixture cleanup uses the retained qBittorrent image; no
Copyparty image or config is needed. Historical entries describe older snapshots.

Current credentials are only .env.
GoDaddy public DNS, deployed container shutdown, old certificate retirement/renewal,
operator-edited Homepage config and production access remain deployment checks.
No live share data, credentials, containers or public DNS records were changed.
See stack.md for current applications and the pending Immich follow-up.

## Unified credentials and media policy (2026-10-16)

82 unit tests, setup/CLI checks, ShellCheck/compilation and an isolated eight-app
Docker smoke passed. Smoke verifies first-run media connections and reruns,
Homepage login with literal credential punctuation, native widgets and proxy routes.
Migration tests cover preserved values, private backups, removed legacy inputs,
conflicts and reruns. Runtime tests verify only Homepage credentials reach Compose,
static rendering omits secrets, and Arr cleanup is disabled before seed limits.

On the deployed host, migrated the two legacy inputs into private .env without
changing values, kept originals in a private backup, recreated Homepage and verified
login/session, both media widgets, qBittorrent login and Arr API authentication.
All eight services remained running. Browser playback, a real TV request/import,
off-host restore and automated GoDaddy renewal remain separate acceptance tasks.

## Homepage OpenSpeedTest widget (2026-10-16)

The existing OpenSpeedTest card now embeds its configured HTTPS hostname using
Homepage v2.5.0's supported iframe widget. It loads lazily with no autostart query
or refresh timer and keeps the full-page header link. No new service or credentials.
The pinned Homepage image includes the configured h-96 height utility; the pinned
OpenSpeedTest response does not deny cross-origin framing.

48 unit tests and static checks pass. The expanded eight-service arm64 smoke
passes, including authenticated Homepage API delivery of the iframe type, resolved
HTTPS source, lazy loading and no refresh interval, plus speed endpoint frame-header
checks and an actual 35 MiB proxy upload. Independent review found no blocking issues.
No browser session was available: rendered layout at desktop/mobile widths, clicking
Start and completing an in-frame measurement remain manual browser acceptance.
Existing edited dashboards require merging the documented widget block; setup
preserves those operator edits. No live deployment was changed.

## Immich implementation (2026-10-22)

Implemented an optional independent `ohara-immich` project from official v3.3.5
release Compose dependencies. Registry indexes for the server, PostgreSQL and
Valkey were checked for amd64/arm64 and pinned separately. Machine learning is
absent from the project and disabled in the effective server settings. No
production Immich directories, credentials, accounts, DNS or Nginx routes changed.

Static/mocked verification: all 131 Python tests pass, including storage path and
mount rejection, secret/environment isolation, preservation and port exposure
checks. `tests/test_setup.sh`, `tests/test_cli.sh`, `tests/static.sh`,
`scripts/check --static`, `scripts/immich check --static` and `git diff --check`
pass. Existing main-stack image inventory is unchanged.

Disposable runtime verification on this Linux host: `tests/smoke.sh` passes for
the eleven-app stack, media API setup/reruns, Homepage auth/widgets, Nginx and
35 MiB speed upload, AdGuard DNS/filtering, and LAN proxy ACLs/routes.
`python3 tests/smoke_immich.py` passes with random test project/port and isolated
named volumes: all three containers healthy, ping API, first-owner signup/login,
effective machine-learning disabled setting, and a tiny PNG upload followed by
byte-identical original download. Its test containers/volumes were removed.
The opt-in Immich proxy template also passes `nginx -t` in a disposable pinned
Nginx container with a temporary test certificate; no host configuration reload.

Real provisioning/production acceptance remains pending: real database password,
photo-library sizing/growth, independent backup destination/retention, actual
owner onboarding, representative photo/video/phone tests and isolated backup
restoration. Public/private hostname access, DNS/TLS activation, large uploads
through that live route and Homepage link remain pending. Disposable tests do
not establish these outcomes or full supported-host provisioning.

### Public activation preparation (2026-10-22)

The operator requested live startup, public HTTPS and a Homepage card. Inspection
confirmed no production Immich containers/storage yet, about 236 GiB free on the
approved local filesystem, existing custom Homepage configuration, and
immich.xdadwal.in resolving to 45.120.160.21. IMMICH_DB_PASSWORD is absent and
noninteractive sudo requires authentication; neither was bypassed. No production
service, Homepage, Nginx or DNS changes were made in this preparation.

Added a host-specific transactional scripts/immich-proxy installer and a seed
Homepage link. 134 Python tests, setup/CLI/static checks pass. A disposable Nginx
instance verified the actual rendered candidate's syntax, HTTPS proxy, HTTP
redirect, mobile discovery path and replacement of spoofed forwarding headers.
Production activation, owner login, certificate validation, off-host backups and
external reachability remain pending. The existing PR includes this preparation.

### Private Immich startup (2026-10-22)

The operator supplied the private database password and explicitly accepted its
shorter length. Added a per-command --allow-short-db-password exception; normal
checks keep their original default. Empty/unsupported inputs remain rejected, and
the main stack ignores this optional project's credential. All 135 Python tests
and CLI/static checks pass. No password was generated, changed or printed.

Ran scripts/immich prepare and up with the explicit exception, using the approved
/ohara/immich/library and /ohara/immich/postgres paths on the root ext4 NVMe.
All three production containers are healthy and the local API ping succeeds.
The onboarding endpoint reports no owner account yet. Public activation and the
live Homepage card remain pending owner login; sudo authentication remains
unavailable in the agent session. Off-host backups/restoration and real photo,
video and phone acceptance remain unverified.

### LAN onboarding and Homepage/AdGuard integration (2026-10-22)

With operator authorization, installed the separate ohara-immich.conf route in
LAN-only onboarding mode using the existing wildcard certificate. The installer
validated the real certificate chain/hostname/expiry and tested/reloaded Nginx;
its exact live file is tracked under configs/nginx/deployed/. No other Nginx file
or certificate was replaced. Trusted HTTPS works via loopback and the server's
192.168.1.101 LAN address; HTTP redirects to HTTPS. A request from an untrusted
Docker subnet was denied with 403 even with a forged LAN X-Forwarded-For header.

Added only the Immich Photos section to live Homepage services.yaml, preserving
all prior contents and file permissions with a private backup under local/.
Restarted only Homepage. Verified its trusted HTTPS password login and the
authenticated services API returning the Immich link. Added the exact AdGuard
rewrite immich.xdadwal.in -> 192.168.1.101 through its authenticated API, verified
all old rewrites remain, and verified UDP and TCP DNS answers. Updated its fresh
seed and documented the existing-install change. No router/client DNS or public
GoDaddy record was changed.

Owner creation/login, unrestricted public access, actual archive/phone acceptance
and off-host backup/restore remain pending. LAN reachability does not establish
Internet reachability. No private credentials were recorded in repository files.

Captured the service-addition workflow in docs/adding-services.md and linked it
from AGENTS.md and docs/agent-setup.md, including complete integration, scoped
credential exceptions, terminal-specific sudo authentication and LAN onboarding.

Final checks for this phase: all 137 Python tests, setup, CLI and static checks
pass. The focused disposable AdGuard smoke passes with the updated Immich seed;
both main-stack and Immich static Compose checks pass.

### Owner completion and public route (2026-10-22)

The operator confirmed owner setup. The API now reports both isInitialized and
isOnboarded true, with smart search, facial recognition and OCR still disabled.
Applied scripts/immich-proxy --apply --accounts-ready: validated the existing
wildcard certificate, privately backed up the LAN-only route, tested Nginx and
reloaded. The tracked ohara-immich.conf matches the live public route; no other
host routes, certificates or DNS records changed. HTTPS ping works through the
public hostname from this host and from the Homepage container. A previously
disallowed Docker subnet now also receives 200, verifying the LAN gate removal.
The external web-fetch tool could not access the hostname, so independent
Internet/browser reachability is not established by these local checks.

Prepared the native Homepage Immich widget version 2 with users/photos/videos/
storage, HTTPS transport through host Nginx, and the optional allowlisted
HOMEPAGE_VAR_IMMICH_API_KEY. The live card remains link-only until the operator
supplies an actual server.statistics API key privately. No API key was generated
or invented. 138 Python tests pass, including optional-key routing/isolation;
setup/CLI/static checks and both static Compose checks pass. Archive/phone/video
acceptance and independent backup/restore remain pending.

### Live Immich statistics widget (2026-10-22)

The operator supplied HOMEPAGE_VAR_IMMICH_API_KEY privately in .env. Validated the
private input and retrieved the production Immich server statistics over trusted
HTTPS with that key; no key value was printed or written outside private inputs.
Merged only the native widget block into the existing live Immich card, retaining
all other dashboard contents and permissions with a private backup under local/.
Recreated only Homepage using the project's allowlisted environment wrapper.

Verified trusted Homepage password login, all four existing dashboard groups,
the native Immich widget in its authenticated services response, and a successful
statistics_v2 widget-proxy response with photo/video/storage data. The actual key
was absent from both browser-facing responses. No other application was restarted.
The previously tested repository configuration already included this widget and
credential allowlist; this step changes live configuration and deployment notes.
Browser layout and archive/phone/video/backup acceptance remain separate checks.

### Immich widget field selection (2026-10-22)

At the operator's request, changed only the live/seed Immich fields to photos,
videos and storage, hiding the user count. The prior live dashboard is privately
backed up, other contents/permissions are preserved, and only Homepage restarted.
Verified the exact field list through the authenticated services API and confirmed
the native statistics_v2 response still succeeds. Git whitespace checks pass.

### Invite-only Google OAuth preparation (2026-10-22)

The operator requested Google accounts with invite-only membership. Reviewed the
official Immich OAuth/user-management guidance, Google OIDC setup, and the pinned
v3.3.5 authentication service: it links an existing account by normalized email
and rejects a missing account when autoRegister is false. This is admin-created
membership, not a new invitation-email or shared-authentication service.

Added optional private Google client inputs, a server-only derived configuration
and scripts/immich oauth. Managed policy enforces autoRegister=false,
autoLaunch=false, password fallback and machine learning disabled. Activation
recreates only Immich server and restores the previous configuration on failure;
failed/prior configurations remain private. Google credentials never enter
Compose interpolation environments or unrelated service inputs.

149 Python tests and setup/CLI/static checks pass, including literal secret
preservation, isolation, private-file permissions, registration/lockout policy
and failed-activation rollback. The disposable Immich smoke passes owner login,
photo round trip and effective disabled auto registration/password fallback.
Both static Compose checks and whitespace validation pass. Restarted only the
production Immich server to load the explicit disabled-registration baseline;
the API continues to report password login enabled, Google OAuth disabled and ML
disabled. Actual Google OAuth client inputs are absent, so activation and approved/
uninvited Google account browser tests remain pending. No external account,
client secret, users, passwords or API keys were generated or changed.

### Live invite-only Google OAuth activation (2026-10-22)

The operator filled the private Google Web client JSON. Verified regular/private
file permissions, JSON structure, credential formats and declared redirect URIs
without displaying values. A token request with an intentionally invalid test
code returned invalid_grant rather than invalid_client; this is an initial check,
not proof of a complete authorization-code exchange or Console redirect settings.
Imported only the supplied client fields into the existing .env atomically,
preserving all other inputs and a private backup. No credential was generated.

Ran scripts/immich oauth with the existing database-password exception. Only the
Immich server was recreated; PostgreSQL, Valkey and other services remained up.
All three Immich containers are healthy. Verified private generated-file mode
0600, Google enabled, autoRegister=false, autoLaunch=false, password fallback and
machine learning disabled. Google OIDC discovery and both web/mobile authorize
requests succeed with the expected client, HTTPS Google endpoint, limited scopes
and canonical redirects; no client secret appears in the authorization URLs.
The existing statistics API key still retrieves production server statistics.

The implementation's 149-test/static/disposable checks passed in the preceding
phase; no implementation code changed in this activation. Full approved-account
Google login/logout, rejected uninvited-account login, account linking and mobile
acceptance still need real owner/browser checks. No such checks are inferred from
the successful initial provider or authorization URL responses.

### Google-only login and user onboarding (2026-10-22)

At the operator's explicit request, changed the Google OAuth renderer to disable
password login. Validation permits Google-only mode only with OAuth configured
and rejects a policy disabling both login methods. Fresh-install bootstrap keeps
password login until Google is configured; future OAuth regenerations retain
Google-only mode. Existing accounts/password hashes/sessions were not reset.

150 Python tests, setup/CLI/static checks and both static Compose checks pass.
The disposable Immich smoke still passes fresh owner login and a photo round
trip. Reconfigured/recreated only production Immich server. All three containers
are healthy. Verified the live feature API reports OAuth enabled/password login
disabled, the password endpoint explicitly returns 401 with the disabled-login
message, OAuth authorize returns the Google endpoint, autoRegister stays false,
ML remains disabled, and the existing widget statistics key still works.

Documented the pinned v3.3.5 new-user form workflow: admin pre-creates the exact
Google email/name with an appropriate quota, leaves password fields blank,
disables required password change and keeps ordinary users non-admin. The owner
shares the service URL manually; first Google login links the existing account.
The Google basic-identity-scope exception means Google's Testing user list is
not the application membership gate. No users, invitations or messages were
created/sent during this change. Full Google browser acceptance remains an owner
check; endpoint/configuration verification is not a completed Google login.

### Production-readiness CI compatibility check (2026-10-22)

The live service is healthy; the main remaining archive-readiness gap is an
independent media/database backup and isolated restore, plus real browser,
phone/video and outside-network acceptance. PR #21 remained open. Hosted CI at
a60ae88 passed both the existing-stack and Immich container jobs but failed the
static configuration job because Compose versions serialize create_host_path
booleans differently: older releases omit false; current Compose omits true.

Fixed validation by rendering a non-secret, daemon-free two-bind reference model
with explicit false/true flags and using its observed encoding. This avoids
weakening the storage guard: explicit/implicit true is still rejected, and a
Compose implementation losing both flag values fails closed. Regression tests
cover both encodings, rejection of unsafe binds and indistinguishable flags.
All 152 Python tests, setup/CLI/static checks, the Immich static check and Git
whitespace checks pass locally. No production services/configuration changed.
Hosted CI must rerun for this commit before release approval.

### Operator release decisions and green CI (2026-10-22)

The operator confirmed successful OAuth login, accepted capacity for the current
single-user deployment, and explicitly deferred backups/restore testing for
later. Updated current status, agent instructions and PR scope to reflect those
choices without claiming unperformed backup, restore or remaining acceptance
checks. No live settings, quotas, authentication or storage were changed.

Both hosted CI runs for 5c21a89 passed: pull_request run 39831104313 and push run
39831093941. Each passed configuration, existing-stack containers and
immich-containers. The 152 local tests and required checks had already passed.
The previous Compose serialization CI blocker is resolved. This follow-up changes
only documentation; whitespace validation passes. PR #21 remains unmerged.

### Homepage v2.8.0 security-update preparation (2026-11-17)

Re-resolved the official `ghcr.io/gethomepage/homepage:v2.8.0` OCI index and
verified linux/amd64 and linux/arm64 manifests before pinning its index digest.
The update includes the upstream v2.6.0 authentication-bypass fix while retaining
the existing private authentication inputs and dashboard configuration policy.

All 257 Python tests, setup/CLI/static checks, the main-stack static check, Git
whitespace validation, and the full disposable eleven-application smoke pass.
The real-container smoke verifies v2.8.0 startup, password/CSRF login, signed
session access, existing media/resource widgets, the OpenSpeedTest link, private
backend behavior, Nginx TLS routing, and a 35 MiB upload. No production container
was recreated in this preparation step.

### OpenSpeedTest digest refresh preparation (2026-11-17)

Re-resolved the mutable `openspeedtest/latest` tag and replaced the 2025 snapshot
with its current OCI index digest. The index provides linux/amd64 and linux/arm64
images. The disposable eleven-application smoke uses this exact pin and verifies
startup, the public speed-test route, iframe/link compatibility through Homepage,
and a 35 MiB proxy upload. This is a dependency/base-image refresh; no production
container was recreated.

### ntfy v2.38.1 security-update preparation (2026-11-17)

Re-resolved the official v2.38.1 manifest list and verified linux/amd64 and
linux/arm64 before pinning its index digest. The disposable ntfy fixture runs the
exact pin and verifies non-root startup, anonymous read/write denial, scoped ACLs,
authenticated publish/read, persistent cache state, native Homepage widget proxying,
and browser credential exclusion.

The offline account-rename guard was separately reviewed against v2.38.1. Its
SQLite user table still uses the stable `id` primary key and `user` name column,
and the helper continues to change only `user.user` so IDs, ACLs, tokens, prefs
and cached messages remain attached to the same account. Future releases remain
refused until reviewed. No production ntfy container, account, timer, or route
was changed during preparation.

### AdGuard Home v0.107.80 security-update preparation (2026-11-17)

Re-resolved the official v0.107.80 OCI index and verified linux/amd64 and
linux/arm64 before pinning it. Upstream's configuration schema remains version 34,
so the seeded private configuration and existing-state preservation behavior are
unchanged. The disposable AdGuard fixture runs the exact pin and verifies non-root
startup, protected control API, UDP/TCP rewrites, IPv6 responses, filtering,
encrypted upstream resolution, and restart persistence. No production DNS service,
configuration, client setting, or router setting was changed.

### Maintainerr v3.32.0 dependency-security preparation (2026-11-17)

Re-resolved the official v3.32.0 OCI index and verified linux/amd64 and
linux/arm64 before pinning it. The disposable Maintainerr fixture runs the exact
image and verifies non-root startup, readiness, state persistence after container
recreation, disabled telemetry, and the deliberate absence of media mounts, rules,
collections, and destructive actions. No production Maintainerr container, private
state, connections, rules, or route was changed.

### Jellyfin v12.4 update preparation (2026-11-17)

Reviewed the intervening v12.3 and v12.4 release notes. Both are minor bug-fix
releases; v12.3 fixes subtitle/probe crashes and v12.4 updates the .NET runtime.
Upstream continues to recommend a full backup before upgrade. Re-resolved the
official v12.4 manifest list and verified linux/amd64 and linux/arm64 before
pinning its index digest.

The disposable eleven-application smoke runs the exact image and verifies startup,
first-owner setup, Movies/TV libraries, persistent Abyss overlay generation against
the changed image pin, media APIs, Nginx TLS routing, and playback-related service
connections. No production Jellyfin server, database, libraries, theme state, or
plugins were changed.

### Sonarr base-image refresh preparation (2026-11-17)

Re-resolved LinuxServer's current Sonarr `latest` index and verified linux/amd64
and linux/arm64 manifests. Its image label remains Sonarr `4.0.20.3014` while the
build advances to `ls5` (created 2026-11-14), making this a base-image/dependency
refresh rather than an application upgrade. The disposable eleven-application smoke
runs the exact pin and verifies startup, Sonarr configuration preservation, API
connectivity, download-client setup, quality profile behavior, and rerun safety.
No production Sonarr container or database was changed.

### Prowlarr v2.7.0 update preparation (2026-11-17)

Reviewed the v2.7.0.5723 release notes, including its allowed-hosts fix and
dependency updates. Re-resolved LinuxServer's current `latest` index and verified
linux/amd64 and linux/arm64; its label is `2.7.0.5723-ls168`. Upstream v3.0.2 was
published after the original audit, but no corresponding LinuxServer image tag was
available at this check, so it is not substituted blindly.

The disposable eleven-application smoke runs the exact pin and verifies Prowlarr
startup, preserved/chosen indexers, application connections to Radarr/Sonarr/Lidarr,
qBittorrent integration, rerun preservation, Nginx TLS routing, and private ports.
No production Prowlarr container, database, or indexer definitions were changed.

### Lidarr v3.1.6 update preparation (2026-11-17)

Reviewed the v3.1.6.5079 release notes, including hostname/allowed-hosts handling,
qBittorrent compatibility, dependency updates, import fixes, and safeguards against
unwanted missing-album searches. Re-resolved LinuxServer's current `latest` index
and verified linux/amd64 and linux/arm64; its label is `3.1.6.5079-ls48`.

The disposable eleven-application smoke runs the exact pin and verifies Lidarr
startup, private networking, root-folder policy, indexer synchronization from
Prowlarr, qBittorrent connectivity, media setup rerun preservation, Nginx TLS
routing, and no automatic music acquisition. No production Lidarr container,
database, artists, root folders, or indexer definitions were changed.

### qBittorrent v5.3.0 security-update preparation (2026-11-17)

Reviewed the official v5.3.0 release notes. Relevant fixes include WebUI
authentication bypass through `X-Forwarded-For` spoofing, rejecting unauthenticated
tracker announces, SMTP injection handling, HTTPS dynamic DNS, and IPv6 filter
parsing. Re-resolved LinuxServer's current `latest` index and verified linux/amd64
and linux/arm64; its label is `5.3.0_v2.1.2-ls487`.

The disposable eleven-application smoke runs the exact pin and verifies qBittorrent
startup, native password login, protected API access, category/save-path policy,
the approved stop-after-240-minutes seeding behavior with file preservation,
Arr download-client connectivity, media setup rerun safety, private ports, and
Nginx TLS routing. No production qBittorrent container, config, BT_backup state,
torrents, or seeding policy was changed.

### Radarr v7.0.3 major-upgrade preparation (2026-11-17)

Reviewed the v7.0.0 through v7.0.3 release paths. Important v7 changes include
.NET 10, FluentMigrator updates, batched/lower-memory media-info migration, a
wildcard allowed-hosts fix, qBittorrent duplicate-release handling, Postgres
credential log protection, ImageSharp decoder restrictions, and .NET runtime
updates through 10.0.15. The release path provides no supported in-container
self-update; Docker deployments must replace the image.

Re-resolved LinuxServer's current `latest` index and verified linux/amd64 and
linux/arm64; its label is `7.0.3.10918-ls328`. The disposable eleven-application
smoke runs the exact pin and verifies startup, API setup, root folders, quality
profile/custom-format behavior, qBittorrent connectivity, Prowlarr synchronization,
Seerr integration, rerun preservation, private ports, and Nginx TLS routing.
This fresh-container check does not prove migration of the production v6 database.
No production Radarr container, database, profiles, indexers, or movie records
was changed.

### Bambuddy/OrcaSlicer v1.3.1 matched preparation (2026-11-17)

Reviewed the upstream v1.3.0 and v1.3.1 release paths together. v1.3.0 closes
three dependency advisories, applies broad database/queue/archive fixes, changes
some API responses, and adds automatic database tables/columns. v1.3.1 fixes a
SQLite camera-view CPU issue and other release follow-ups. The release explicitly
requires updating the slicer sidecar together with Bambuddy for the new OrcaSlicer
2.5.0 backend.

Re-resolved Bambuddy v1.3.1 as a linux/amd64 and linux/arm64 OCI index and the
exact `bambuddy-1.3.1` sidecar as the reviewed linux/amd64 manifest required by
the existing x86-64 policy. The disposable Bambuddy fixture verifies v1.3.1
startup, health, non-root operation, fresh setup state, SQLite persistence,
container recreation, and exact Docker-gateway proxy trust with spoofed-header
rejection. No account, printer, job, or print was created. The sidecar's health
and OrcaSlicer 2.5.0 version were then checked in a separate isolated linux/amd64
container with writable private state; no model was uploaded or sliced. The
disposable pinned Homepage widget check still verifies custom headers, expected
status fields, and browser credential exclusion.
No production Bambuddy/OrcaSlicer container, database, settings, archive, or
slicer state was changed.

### Kutt PostgreSQL same-version digest refresh preparation (2026-11-17)

The Kutt application remains v3.2.6. Docker's `postgres:17.11-alpine3.24` tag was
rebuilt from October base images to November base images without changing the
PostgreSQL version. Re-resolved the current multi-architecture OCI index and
verified linux/amd64 and linux/arm64 manifests before pinning it.

The disposable Kutt fixture runs both the unchanged application pin and refreshed
database image, then verifies PostgreSQL health, application health/startup, owner
setup state, native API behavior, persistent links/users, TLS proxy behavior,
LAN-only administration, and public-user route policy. No production Kutt or
PostgreSQL container, database volume, JWT secret, users, or links was changed.

### Immich v3.4.1 / Valkey 9.1.3 preparation (2026-11-17)

Compared Ohara's adapted three-service model with the official v3.4.1 release
Compose. The server and Immich PostgreSQL dependency pins were re-resolved. The
server uses its verified linux/amd64 manifest digest because Compose 5.6
intermittently rejects this GHCR image's manifest-list digest; upstream also
publishes arm64, but it is not pinned for this host. The official release still
referenced a Valkey 9.1.2 snapshot, so Ohara deliberately advances only the cache
dependency to the compatible Valkey 9.1.3 security release that fixes
GHSA-f4q9-j22m-xqq9. The Immich-specific PostgreSQL image and database data path
remain unchanged.

Reviewed v3.4.0's security batch (shared-link visibility, upload/update permission
checks, template escaping, partner timeline scope, OAuth cookie state, symlink
handling, and CSP hardening) and v3.4.1's shared-link performance/bug fixes. The
v3.4.1 user-creation form still permits blank passwords when OAuth is enabled and
still exposes the required-password-change control used by the invite-only
onboarding guide.

The disposable Immich fixture runs the prepared server, Valkey 9.1.3, and unchanged
Immich PostgreSQL image. It verifies all three services healthy, ping, owner
signup/login, machine-learning-disabled policy, invite-only registration default,
and a byte-identical PNG upload/download round trip. This does not migrate or
back up production data. Independent production backup/restore testing remains
deferred by the owner; live migration still requires the explicit backup/risk
decision and maintenance window from the remediation plan.

### 2026-11-18 production rollout status and corrections

The merged main-stack pins were applied after the required Jellyfin theme refresh.
`scripts/check` and `scripts/up` completed, and `scripts/status` subsequently
reported all eleven main-stack containers running and reachable; Homepage and
Jellyfin reported healthy. Container inspection confirms Homepage 2.8.0, Jellyfin
12.4, Sonarr `4.0.20.3014-ls5`, Lidarr `3.1.6.5079-ls48`, qBittorrent
`5.3.0_v2.1.2-ls487`, Radarr `7.0.3.10918-ls328`, and OpenSpeedTest
`1.30.6-alpine`. The Seerr image remains intentionally unchanged at v3.5.2.

Prowlarr was deployed by its recorded digest and runs `3.0.2.5780-ls169`. This
exposed a preparation error: earlier text incorrectly associated that digest with
v2.7.0-ls168. Direct image inspection proves digest `sha256:45117…` is
v3.0.2-ls169, while digest `sha256:666078…` is v2.7.0-ls168. The v3.0.2 container
is retained and its `/ping` endpoint returns `OK`; documentation/tracker are
corrected. Full indexer/sync and public/LAN acceptance remain pending.

ntfy 2.38.1, Maintainerr, Bambuddy 1.3.1, and the matched OrcaSlicer sidecar were
restored/updated through their helpers. Helper status checks pass; ntfy
authenticated publishing accepts a test notification, while phone delivery remains
owner confirmation. The optional-state backup remains available for rollback.

An unintended DNS outage occurred when AdGuard was stopped for a consistent
backup. The owner manually restored the unchanged v0.107.79 service; authenticated
API and DNS status then passed. While preparing the safety correction, a later
`scripts/adguard up` used the merged pin and recreated AdGuard as v0.107.80; this
was not the intended deferral sequence and is recorded as part of the incident.
The running service now reports authenticated API and DNS status, and host-local
UDP/TCP queries return answers. The default `scripts/adguard stop` now refuses an
outage and requires `--allow-dns-outage`; this guard is repository safety, not
evidence that a fallback resolver has been deployed. A separate LAN client must
verify UDP/TCP queries before closure. Kutt remains unchanged pending the
root-required documented backup. Seerr's installed Nginx route and host packages
also remain pending.

With root access, the installed Nginx baseline was backed up, replaced, validated,
and reloaded. Local public-edge checks returned 404 for `/imageproxy`,
`/imageproxy/`, duplicate-slash, encoded, and case-variant paths; adjacent
Homepage, OpenSpeedTest and Jellyfin routes remained reachable. The documented
Kutt backup then succeeded before the application/database recreation.
`sudo scripts/kutt status` reports Kutt/PostgreSQL healthy, the restricted
database role, and existing owner setup. Native owner login and external HTTPS
acceptance remain pending.

### 2026-11-18 host-side post-rollout verification

Scope: read-only real-host checks at about 13:00 UTC. Hostname checks used
`curl --resolve HOST:443:127.0.0.1`, so they exercise the installed Nginx
configuration but are **not** external or separate-LAN reachability evidence.
Application checks used loopback backends and existing private keys through
`scripts/lib/credentials.py`; no value was printed and no setting was changed.

- **Pins and Nginx:** every running container's image digest equals its pin in
  `versions/`; installed `ohara*.conf` files are identical to
  `configs/nginx/deployed/`; `systemctl --failed` lists nothing; the alert,
  storage-watchdog and Certbot timers are scheduled; `/ohara/mnt` is mounted.
- **Seerr containment:** 404 for `/imageproxy`, trailing slash, a real-shaped
  `/imageproxy/tmdb/...` path, upper case, duplicate slash, percent-encoded
  letters, `/./`, `/foo/../`, `/foo/%2e%2e/`, a query string and `%2f` forms.
  `/;/imageproxy/...` is forwarded but Seerr answers with its login redirect, not
  the image proxy. `/login` and `/api/v1/status` still return 200.
- **Radarr 7.0.3.10918:** 29 movies (26 with files), root folder accessible,
  six quality profiles, no health issues, empty queue, two indexers.
- **Sonarr 4.0.20.3014:** six series, 146 episode files, three indexers, no
  health issues; the owner confirmed the existing queue.
- **Lidarr 3.1.6.5079:** two artists, 136 track files, two indexers, no health
  issues.
- **Prowlarr 3.0.2.5780:** three indexers, none in failure status, applications
  for Radarr, Sonarr and Lidarr present. A short post-restart rate-limit cleared.
- **qBittorrent 5.3.0:** 48 torrents, none missing files or errored, categories
  and save paths intact, 240-minute seeding limit enabled, ratio and inactivity
  limits disabled. Completed-download removal remains disabled in Radarr, Sonarr
  and Lidarr.
- **Jellyfin 12.4.0:** six users, nine plugins active including Intro Skipper,
  Enhanced and LetterboxdSync, `scripts/jellyfin-theme check` passes, no active
  playback. Libraries are Movies, Stand-ups, TV Shows and Collections; the owner
  confirmed no Music library is needed.
- **ntfy 2.38.1:** anonymous read of `ohara-alerts` returns 403 and account
  signup is refused as not enabled.
- **AdGuard 0.107.80:** host-local UDP and TCP answers, a blocked domain returns
  `0.0.0.0`, the local rewrite resolves, and DNS listens only on the LAN address.
- **Maintainerr 3.32.0:** database readiness passes and no removal activity is
  logged since restart; the owner confirmed its two collections.
- **Kutt:** both containers healthy; the application reconnected after
  PostgreSQL was recreated and `/login` returns 200.
- **Bambuddy 1.3.1 / OrcaSlicer:** both healthy; MQTT reconnected to the printer.
- **Homepage 2.8.0:** unauthenticated `/` and `/api/services` redirect to sign-in.

**Immich v3.4.1 found applied.** `docker inspect` shows the server and Valkey
containers created at 12:35 UTC by a session that did not update the records.
Server logs show three migrations succeeding and v3.4.1 added to the upgrade
history. No backup decision or pre-upgrade backup is recorded and none was found
under `local/`. The owner accepted the applied state subject to functional
checks. Verified: `scripts/immich status`, ping, server v3.4.1, Valkey 9.1.3,
PostgreSQL container not recreated, `/data` directories present, 141 photos and
35 videos reported for one user, unauthenticated API calls return 401, the
managed configuration still has OAuth enabled with `autoRegister=false`, password
login and machine learning disabled, the Homepage key is refused outside
`server.statistics`, and `immich.xdadwal.in` serves through Nginx. Not verified:
Google login, timeline rendering, upload/download round trip and jobs, which need
the owner's browser.

Not done here: external and separate-LAN checks, browser logins, playback, a
speed test, slicing, phone delivery, and any search or download.

### 2026-11-18 owner confirmations and Jellyfin metadata repair

The owner confirmed AdGuard works for LAN clients, Seerr is reachable from the
public Internet, service logins work, and Jellyfin media plays. These are owner
reports, not agent-run checks. `scripts/ntfy test` published a notification at
19:08 IST that the server accepted; phone arrival awaits the owner. External
`/imageproxy` denial, LAN-only denial from outside, an OpenSpeedTest run,
Bambuddy slicing and an Immich upload/download round trip are not yet reported.

Jellyfin logs from 2026-11-16 to 16:44 IST on 2026-11-18 show about 600 daily
`Resource temporarily unavailable` failures for `api.themoviedb.org` and
`www.omdbapi.com` in the previous container. The recreated 12.4 container
resolves both and logs no such failure. Movies imported in that window kept an
empty provider match and a non-replacing refresh did not re-match them. The exact
TMDb result was applied to The Batman (2022), Pride & Prejudice (2005) and
Requiem for a Dream (2000) with `POST /Items/RemoteSearch/Apply/{id}`; each now
has TMDb/IMDb IDs, overview, genres and artwork. Two older stand-up items without
a provider match were left unchanged. The cause of the old container's resolver
failure was not determined.

### Prowlarr explicit stable tag (2026-11-18)

Upstream Prowlarr's newest non-prerelease release is v3.0.2.5780 and LinuxServer's
newest non-prerelease build is `3.0.2.5780-ls169`. `docker buildx imagetools
inspect` resolves both `lscr.io/linuxserver/prowlarr:3.0.2.5780-ls169` and
`:latest` to index digest `sha256:45117ba8…`, the digest already pinned and
running. Only the tag text of `PROWLARR_IMAGE` changed. `scripts/check --static`
and the repository tests pass. The container has not been recreated with the new
reference; that happens on the next `scripts/up`. The owner separately confirmed
ntfy phone delivery, an Immich upload and an OpenSpeedTest run.

### Explicit version tags for all pins (2026-11-18)

`docker buildx imagetools inspect` confirmed that each versioned tag resolves to
the digest already pinned and running: Radarr `7.0.3.10918-ls328`, Sonarr
`4.0.20.3014-ls5`, Lidarr `3.1.6.5079-ls48`, qBittorrent `5.3.0_v2.1.2-ls487`,
Bazarr `v1.6.2-ls368`, OpenSpeedTest `v2.0.8` and Valkey `9.1.3`. Only tag text
changed in `versions/stack.env` and `versions/immich.env`; no pin uses `latest`
or a major-only tag any more. `scripts/check --static`, `scripts/immich check
--static` and the repository tests pass. Not applied live: the changed references
make Compose recreate these containers on the next `scripts/up` and
`sudo scripts/immich up`.

### Seerr LAN-only containment preparation (2026-11-18)

The owner chose to restrict the whole Seerr host to LAN sources. The deployed
baseline `configs/nginx/deployed/ohara.conf` gained a dedicated guarded HTTP
server for `seerr.xdadwal.in`, removed that name from the shared ACME/redirect
server, and added the `$ohara_lan_allowed` guard ahead of the existing
`/imageproxy` denial in the HTTPS server. The reusable template is unchanged.

- Unit: `python3 -m unittest tests.test_proxy` (11 tests) covers the guard order,
  both Seerr servers, and equivalence of every other route with the template.
- Disposable: `python3 tests/smoke_lan_proxy.py` loads the three actual baseline
  files in an offline Nginx container. An allowed source gets 200 for `/discover`,
  301 on HTTP and 404 for six `/imageproxy` variants; a disallowed source gets 403
  on HTTP and HTTPS for `/`, `/discover`, `/api/v1/status` and the same variants,
  with and without forged forwarding headers. Six public routes still return 200.
- Real host: **not applied.** No root access in this session; the installed file
  is unchanged and now differs from the repository baseline until the documented
  commands are run.
- Not verified: a real LAN client, a real external client, and a remote request
  through Jellyfin Enhanced with the public route closed.

### Explicit-tag production release (2026-11-18)

Real host, with owner approval after PRs #54-#56 merged. `scripts/check` and
`scripts/up` recreated seven main-stack containers at 14:39 UTC; `docker inspect`
shows each on its versioned reference with the previously pinned digest.
`scripts/status` reports all eleven containers running and reachable. Read-only
API checks before and after match: Radarr 29 movies, Sonarr 6 series, Lidarr 2
artists, Prowlarr 3 indexers and three applications, qBittorrent 48 torrents
(43 stopped, 3 stalled, 2 queued uploads) with unchanged categories and seeding
policy, and no health issues.

With root access supplied by the owner, the Seerr LAN-only baseline was then
installed at 20:14 IST: backup at `/var/backups/ohara/ohara.conf.20261118-201432`,
`nginx -t` passed before and after, Nginx reloaded, and `cmp` against the
repository baseline is silent. Real-host checks with `curl --resolve`: from
192.168.1.101 Seerr returns 307 for `/`, 200 for `/login` and `/api/v1/status`,
404 for `/imageproxy/...` and 301 on HTTP; from the host's Tailscale address
(not in the allowlist) `/`, `/login`, `/api/v1/status` and `/imageproxy/...`
return 403 on HTTPS, `/` returns 403 on HTTP, and forged `X-Forwarded-For` and
`X-Real-IP` headers still get 403. From that same source Homepage, Jellyfin,
OpenSpeedTest, Navidrome, Immich, Kutt, ntfy and Bambuddy still answer and
`radarr.xdadwal.in` returns 403. Inside the Jellyfin and Homepage containers
`http://seerr:5055/api/v1/status` succeeds.

`sudo scripts/immich --allow-short-db-password up` recreated only Valkey on the
`9.1.3` reference with the same digest; the first attempt without the documented
flag was refused by input validation and changed nothing. Afterwards all three
containers are healthy, `valkey_version` is 9.1.3, ping and statistics answer and
the HTTPS route returns 200.

Owner report (2026-11-18), not an agent-run check: verified on the local network
and the public Internet that Seerr loads on the LAN, is refused from outside, and
that a request made inside Jellyfin from outside still reaches Seerr.

### H-01 selective host upgrade, steps 1-3 (2026-11-18)

Real host. After `apt-get update`, three groups were installed by name with
`NEEDRESTART_MODE=l`: ca-certificates/zlib1g/libexpat1, nginx/nginx-common, and
linux-image-amd64. `dpkg-query` shows each at its target version and installed.
Service start times confirm only Nginx restarted (22:08:57 IST); Docker and all
21 containers kept running. After the Nginx upgrade `nginx -t` passes, the
installed configuration files equal `configs/nginx/deployed/`, eleven routes
answer from the LAN address, and Seerr and `radarr.xdadwal.in` return 403 from
the host's Tailscale address. The kernel package generated its initramfs and
GRUB entries; the host still runs 6.12.111 until rebooted. Not done: the Docker
upgrade and the reboot, which wait for an owner window. No external client check
was run.

### H-01 Docker upgrade, reboot and post-reboot verification (2026-11-18)

Real host. With the owner's approval of the DNS outage, docker-ce, docker-ce-cli
and docker-ce-rootless-extras were upgraded to 5:29.10.0 at 22:55 IST after
confirming no playback, download or Radarr/Sonarr queue activity; all 21
containers and every helper status returned within about a minute. The host was
then rebooted and came up at 22:58:48 IST.

Checked at 23:10 IST after the owner reconnected:

- Kernel 6.12.117+deb13-amd64; nginx 1.26.3-3+deb13u10, Docker 29.10.0, zlib1g,
  libexpat1 and ca-certificates at their targets; containerd.io 2.4.2-2,
  Compose plugin 5.6.0 and Tailscale 1.104.1 unchanged as intended.
- `systemctl --failed` lists nothing. nginx, docker, containerd, tailscaled, ssh
  and `ohara-media.service` are active; the alert, storage-watchdog and Certbot
  timers are scheduled and the watchdog's last run exited 0.
- `/mnt/disks/wd-500`, `/mnt/disks/crucial-240` and the mergerfs pool at
  `/ohara/mnt` are mounted with their top-level directories present.
- 21 containers running, none exited, unhealthy or restarting; `scripts/status`
  reports all eleven main-stack services reachable; Immich, AdGuard, Maintainerr,
  ntfy, Kutt and Bambuddy helper statuses pass; OrcaSlicer is healthy and
  `scripts/jellyfin-theme check` passes.
- Application state through existing keys: Radarr 30 movies, Sonarr 6 series,
  Lidarr 2 artists, Prowlarr 3 indexers, all without health issues and with
  accessible root folders; qBittorrent 49 torrents in the same states as before
  with the 240-minute limit; Jellyfin 12.4.0 with nine plugins; Immich 3.4.1
  with Google-only login; Seerr 3.5.2.
- Nginx: installed files equal the baseline; from the LAN address twelve hosts
  answer and `/imageproxy` returns 404; from the Tailscale address Seerr and
  three LAN-only hosts return 403 while public hosts answer.
- AdGuard answers UDP and TCP on 192.168.1.101 only, blocks a filtered domain
  and serves the local rewrite. No container publishes a non-loopback port
  except DNS.
- Tailscale is connected with Tailscale SSH, DNS acceptance, route acceptance,
  advertised routes and exit node all off and no Serve configuration.
- Jellyfin logs no name-resolution failure since boot.

Not verified here: external Internet reachability, playback, a LAN device other
than the host, and phone notification delivery after the reboot.

### Samba disabled on the host (2026-11-19)

Owner decision after a read-only security review: Samba is not used by Ohara and
was listening on every interface (139/445 TCP, 137/138 UDP) with guest mapping.
`smbstatus` showed no sessions or open shares and `/etc/fstab` has no CIFS mount.
Applied on the real host:

```sh
sudo systemctl disable --now smbd.service nmbd.service winbind.service
```

Afterwards the three units are inactive and disabled, `ss -ltnup` shows no
listener on 137-139 or 445, and local user lookup still works. Packages,
`/etc/samba/smb.conf` and the `winbind` entries in `/etc/nsswitch.conf` were left
unchanged. Roll back with `sudo systemctl enable --now smbd nmbd winbind`. Ohara
setup does not install or manage Samba; this is host hardening specific to this
machine. Remaining non-loopback listeners: SSH 22, Nginx 80/443, AdGuard DNS on
192.168.1.101:53, Tailscale, and Avahi mDNS 5353.

### Avahi disabled on the host (2026-11-19)

Owner decision from the same review: mDNS discovery is not used by Ohara.
Applied on the real host:

```sh
sudo systemctl disable --now avahi-daemon.socket avahi-daemon.service
```

Both units are inactive and disabled and nothing listens on UDP 5353. The package
is left installed. This did not last: see "Avahi masked after it restarted itself
(2026-11-22)" below for the current, masked state. Roll back with
`sudo systemctl enable --now avahi-daemon.socket avahi-daemon.service`.
Non-loopback listeners are now SSH 22, Nginx 80/443, AdGuard DNS on
192.168.1.101:53 and Tailscale only.

### SSH restricted to key authentication (2026-11-19)

Owner decision from the security review, after the owner added a key for the one
device that still used a password. Installed root-owned
`/etc/ssh/sshd_config.d/90-ohara-keys-only.conf` (mode 644) containing:

```
PasswordAuthentication no
KbdInteractiveAuthentication no
```

then `sudo sshd -t && sudo systemctl reload ssh`. `sshd -T` reports both options
`no` with public-key authentication on, and a password-only attempt against
192.168.1.101 is refused with `Permission denied (publickey)`. The existing key
session stayed connected. `/etc/ssh/sshd_config`, `authorized_keys`, host keys,
root login and X11 forwarding settings were not changed. The owner then
confirmed a key login from the phone over Tailscale, the one device that had
used a password; other devices already used keys. Roll back by removing the drop-in and reloading
`ssh`; the local console still accepts the account password.

The policy was then added to the repository as
`configs/ssh/90-ohara-keys-only.conf` with the procedure under "Optional host
hardening" in [agent setup](agent-setup.md), which also covers the Samba and
Avahi shutdowns. The template was reinstalled over the hand-written file;
`sshd -t` passed, SSH reloaded, `cmp` against the template is silent, and the
password-only attempt is still refused. `tests/test_host_hardening.py` checks
the template's two directives and the documented commands.

### Bambuddy/OrcaSlicer 1.3.2 matched preparation (2026-11-21)

Reason: on production 1.3.1 the Slice dialog showed "Failed to load presets.
Open Settings → Profiles to import them first." and the Profiles cloud list
failed. The container log showed `AttributeError: 'NoneType' object has no
attribute 'get'` at `slicer_presets.py:187` and `cloud.py:609`. Bambu Cloud
returns `null` for a preset type the signed-in account has none of (upstream
#3593). Importing profiles does not help; the fix is the upstream release.
The upstream Git tag is spelled `v.1.3.2`; the image tags are `1.3.2` and
`bambuddy-1.3.2`.

- Reviewed: 1.3.2 release notes (no breaking API changes; tables/columns added
  automatically) and the v1.3.1...v.1.3.2 deployment diff. The root Compose file
  is unchanged; the sidecar Compose change only adds an optional host bind
  address, which this private bridge-only deployment does not publish.
- Re-resolved `bambuddy:1.3.2` as a linux/amd64 and linux/arm64 OCI index and
  `orca-slicer-api:bambuddy-1.3.2` as a linux/amd64 manifest.
- Offline image inspection: the pinned Bambuddy image reports `APP_VERSION`
  1.3.2 and normalises null preset types in `services/bambu_cloud.py`
  (`_slicer_settings_listing`); the pinned sidecar reports OrcaSlicer 2.5.0.
- Disposable: `python3 tests/smoke_bambuddy.py` and
  `python3 tests/smoke_bambuddy_widget.py` passed against the new pin. No
  account, printer, job or print was created; no model was sliced.
- Static: `python3 -m unittest discover -s tests` (260 tests),
  `tests/test_setup.sh`, `tests/test_cli.sh` and `tests/static.sh` passed.
- Real host: **applied 2026-11-21** from merged master (PR #58), with no print
  activity in the preceding hour of logs. Both services were stopped and the
  whole `/ohara/bambuddy` state (118 files, including the sidecar's
  `orcaslicer/` directory) was copied to the private, ignored
  `local/bambuddy-backups/20261121-113842-pre-1.3.2/`; this same-host copy is
  not an independent backup. No sudo was needed on this host because the
  operator account already has Docker access:

  ```sh
  scripts/orcaslicer stop
  scripts/bambuddy stop
  cp -a /ohara/bambuddy/. local/bambuddy-backups/<timestamp>-pre-1.3.2/
  scripts/bambuddy up
  scripts/orcaslicer up
  scripts/bambuddy status
  scripts/orcaslicer status
  ```

  Result: both containers healthy on the 1.3.2 digests, owner setup and
  authentication preserved, sidecar reports OrcaSlicer 2.5.0, public HTTPS
  returns 200 and an unauthenticated printer API call returns 401. No startup
  errors were logged.

  Rollback: revert both pins to the 1.3.1 digests and rerun the two `up`
  commands; restore the stopped-state copy only under explicit recovery scope.
- Not verified: cloud preset loading with the owner's Bambu Cloud sign-in, a
  representative slice, printer MQTT reconnection after the restart.

### AdGuard second encrypted upstream (2026-11-21)

Reason: on 2026-11-21 from 16:57 to 19:45 IST every request to the only upstream,
Cloudflare DoH, timed out (about 2,900 failed lookups in the container log), so
uncached LAN lookups hung for 10–30 seconds. The WAN stayed up and the container
did not restart; it recovered without intervention. The cause of the Cloudflare
path failure was not determined. With a single upstream and no fallback, any such
failure stops LAN DNS, so the owner approved adding Quad9 (default filtered
endpoint) as a second DoH upstream.

- Unit: `python3 -m unittest discover -s tests` covers the two-provider fresh
  config, append-only merging, idempotence, and refusal on a failed upstream
  test or an existing plaintext upstream.
- Real host: **applied** with `scripts/adguard upstreams` after copying the
  existing configuration to the private, ignored
  `local/adguard-AdGuardHome.yaml.20261121-pre-quad9`. No restart (same container
  start time, zero restarts). The installed `AdGuardHome.yaml` lists both
  upstreams and four bootstrap addresses; `fallback_dns`, the LAN allowlist and
  rate limit are unchanged. UDP and TCP queries to the bind address answered in
  7–15 ms, the local rewrite still resolves, and no errors were logged.
- Not verified: behaviour during a real single-provider outage, and queries from
  a separate LAN client.

### Avahi masked after it restarted itself (2026-11-22)

The 2026-11-19 record above no longer held: Avahi was `disabled` but had been
active again since 2026-11-20 00:04 IST, listening on UDP 5353.
`cups-browsed.service` has `Wants=avahi-daemon.service` and starts it as a
dependency; the nightly logrotate restart of CUPS is the likely trigger. Nothing
in Ohara or its Docker networks uses mDNS. The owner approved masking:

```sh
sudo systemctl mask --now avahi-daemon.socket avahi-daemon.service
```

- Real host: **applied.** Both units are `masked` and `inactive`, nothing listens
  on UDP 5353, and Avahi stayed inactive after
  `sudo systemctl restart cups-browsed.service`. CUPS, cups-browsed and SSH remain
  active.
- Not verified: the state after the next nightly logrotate run.
- Rollback: `sudo systemctl unmask avahi-daemon.socket avahi-daemon.service`, then
  `sudo systemctl enable --now` on both.

### AdGuard owner-chosen primary resolver, Quad9 retired (2026-11-23)

Reason: a second incident on 2026-11-23, 16:20-16:47 IST, timed out Cloudflare
and Quad9 DoH together, so a second encrypted provider did not help. From the
server, plain DNS to 9.9.9.9 was dropped from the start of that incident, and
TCP and ICMP to Google's address ranges (including Google DoH) failed while other
destinations and DNS answers were normal; the cause on the router/ISP path was
not determined. The owner then chose the resolver 163.53.87.74 (`dns.anonet.in`)
as primary, with Cloudflare DoH as secondary, and removed Quad9. This replaces
the earlier "no plaintext upstream" choice for this host only.

- Unit: `python3 -m unittest discover -s tests` (267 tests) covers the default
  policy, address validation, exact application, idempotence and refusal on a
  failed upstream test.
- Real host: `ADGUARD_PRIMARY_DNS` was appended to the private `.env`, the
  previous configuration copied to the ignored
  `local/adguard-AdGuardHome.yaml.20261123-pre-primary`, and
  `scripts/adguard upstreams` applied. No restart. Installed state:
  `upstream_dns` is the primary only, `fallback_dns` is Cloudflare DoH, bootstrap
  is 1.1.1.1/1.0.0.1; allowlist and DNSSEC unchanged. TCP queries, a local
  rewrite, a blocked name (0.0.0.0) and `dnssec-failed.org` (SERVFAIL) behave as
  before, and no errors were logged.
- Measured from the server: the primary validates DNSSEC and returns honest
  NXDOMAIN. Forty real names resolved 39/40 directly (average 69 ms, against
  40/40 and 21 ms for 1.1.1.1) and 40/40 through AdGuard (72 ms). Random
  uncached names timed out about 3% of the time at a 5 second client limit, both
  directly and through AdGuard.
- Not verified: fallback to Cloudflare during a real primary outage (AdGuard's
  10 second upstream timeout applies first), behaviour during another
  router/ISP incident, and queries from a separate LAN client.
- Rollback: remove `ADGUARD_PRIMARY_DNS` from `.env` and rerun
  `scripts/adguard upstreams`.

### Host Nginx security update (2026-11-23)

Reason: Debian published `1.26.3-3+deb13u11` on 2026-11-18 (urgency high),
backporting nine CVE fixes from upstream 1.30.7. The host ran `+deb13u10`.

- Real host: **applied** at 19:45 IST with the command in
  [operations.md](operations.md) ("Backups, upgrades, and recovery"). Only
  `nginx` and `nginx-common` changed; configuration files were kept. `nginx -t`
  passes, the unit is active with a master process started at 19:45:53, and
  `https://xdadwal.in/` (200), the Homepage host (307 to login) and the music
  host (302) answered from the server.
- Not verified: requests from outside the LAN.
- Not changed: the 112 other pending package updates, and automatic security
  updates, which are not installed.
- Future setups: `scripts/setup` now requires at least this release on Debian 13
  (`NGINX_MINIMUM`, unit tested; the real installed package satisfies it per
  `dpkg --compare-versions`). Not verified: a real fresh-machine setup run, and
  Ubuntu 24.04, which has no recorded floor.
- Rollback: reinstall `1.26.3-3+deb13u10` for both packages while the archive
  still offers it.

### Bundled AdGuard retired for an external resolver (2026-11-24)

Reason: the owner moved LAN DNS to an AdGuard Home with Unbound on a separate
OpenWrt device (192.168.1.105) and asked for the bundled one to be disabled.

- Unit: `python3 -m unittest discover -s tests` (272 tests) covers
  `ADGUARD_EXTERNAL_IP` validation and the alert probe's choice of resolver.
- Real host: the owner changed the router's DNS; the bundled query log showed the
  router's last query at 08:30:49 UTC and none in the following 16 minutes. The
  previous configuration was copied to the ignored
  `local/adguard-AdGuardHome.yaml.20261124-pre-retire`, and
  `scripts/adguard stop --allow-dns-outage` applied at about 08:51 UTC. Afterwards
  lookups through the router still resolved, a rewrite returned 192.168.1.101 and
  a blocked name returned 0.0.0.0. `ADGUARD_EXTERNAL_IP` was appended to `.env`
  and the installed Homepage tile repointed (previous file in
  `local/homepage-services.yaml.20261124-pre-adguard-retire`).
- Not verified: the external device across a reboot, lookups from a separate LAN
  client, and the Homepage tile (Homepage was stopped with the media pool at the
  time; see the operator report of the missing WD branch drive).
- Rollback: see "This host" in [adguard.md](adguard.md).
- 2026-11-24, later: the tracked LAN route for `adguard.DOMAIN` was repointed to
  the OpenWrt dashboard. Static and unit suites pass; the dashboard answers a
  request carrying the proxied Host header.
- Real host, 16:11 IST: `sudo scripts/lan-proxy --apply` **applied**;
  `https://adguard.DOMAIN` now serves the OpenWrt dashboard's login page, an
  unauthenticated API call returns 401, and the other LAN routes and the public
  apex answer as before. `sudo scripts/ntfy install-alerts` **applied**: the
  installed configuration probes DNS at the external address and no longer
  contains the bundled container or its dashboard check; the next timer run
  succeeded. The installed Homepage tile links to `https://adguard.DOMAIN` again,
  without a widget.
- 2026-11-24, key cleanup: `ADGUARD_EXTERNAL_IP` was renamed `DNS_IP`, and the
  optional `ADGUARD_PRIMARY_DNS` policy added the day before was removed again,
  because the bundled AdGuard it configured is retired here; the bundled policy
  is Cloudflare DoH only. Entries above keep the names used at the time. In the
  private `.env` the key was renamed and the dead `ADGUARD_PRIMARY_DNS` and
  retired, ignored `LAN_IP`, `FILES_ROOT` and `FILES_HOST` lines removed (previous file in the ignored
  `local/env.20261124-pre-key-cleanup`). `ADGUARD_BIND_IP`, `ADGUARD_NETWORK`
  and `ADGUARD_PASSWORD` stay: the Kutt LAN rule reads `ADGUARD_NETWORK`, and
  all three are needed to roll back to the bundled AdGuard. Unit suite (271),
  `scripts/check` and `scripts/status` pass; the installed alert configuration
  already holds the probe address, so no reinstall was needed.
- 2026-11-24, Homepage widget: after the owner put the external AdGuard's login
  in `ADGUARD_PASSWORD`, one authenticated status call was accepted, the widget
  block was restored in the installed `services.yaml` with the external URL
  (previous file in `local/homepage-services.yaml.20261124-pre-widget`), and
  `scripts/up` recreated only Homepage. From inside the Homepage container its
  own credential returned live statistics, and no failed login was logged
  afterwards. Not verified: the rendered tile, which is behind Homepage's login.

### External AdGuard support in scripts, config-driven dashboard, OpenWrt script (2026-11-24)

- Unit: 273 tests, including dashboard selection by `DNS_IP`, refusal of the
  bundled-only commands, and the `SEERR_LAN_ONLY` flag with the stack and
  template variables. `tests/test_setup.sh`, `tests/test_cli.sh` and
  `tests/static.sh` pass.
- Real host: `scripts/adguard status` reports the external AdGuard reachable and
  running; `up` and `upstreams` refuse. The rewrite steps of the Bambuddy,
  Maintainerr, ntfy and Kutt scripts each found their existing record on the
  external AdGuard and wrote nothing. `SEERR_LAN_ONLY=true` was added to `.env`,
  the two template lines merged into the installed `services.yaml` (previous
  file in `local/homepage-services.yaml.20261124-pre-vars`), and `scripts/up`
  recreated only Homepage; inside the container both variables hold the expected
  values and its credential fetched live statistics. Not verified: the rendered
  cards, which are behind Homepage's login.
- OpenWrt device: `configs/openwrt/setup.sh` passes `sh -n` and the device's own
  `ash -n`. Its usage error and both `network` input refusals left no pending
  change. The `dns` and `harden` phases were run on the configured device and
  changed nothing observable: both services running, key-only SSH still enforced,
  lookups, filtering, a rewrite and DNSSEC failure handling as before. Not
  verified: the `network` phase and a first-time `dns` run on a stock device.
- Browsing Security: the owner switched it off in the AdGuard dashboard on
  2026-11-24. Read from the device afterwards: `safebrowsing_enabled: false`,
  `parental_enabled: false`, no remaining connection to 94.140.14.15 in
  `/proc/net/nf_conntrack` (it closed within about two minutes), and lookups plus
  ad blocking still answer from the server.
- Alert worker realigned (2026-11-24 21:33 IST): the installed
  `/usr/local/lib/ohara/alerts.py` still named the pre-rename key
  `ADGUARD_EXTERNAL_IP` (install-time only, no runtime effect). Reran
  `sudo scripts/ntfy install-alerts` with every monitored service running;
  ntfy authentication verified, the installed worker is byte-identical to
  `scripts/lib/alerts.py`, `/etc/ohara/alerts.json` keeps the DNS probe
  192.168.1.105, a manual `systemctl start ohara-alerts.service` finished
  cleanly and the timer is active. Previous worker, configuration and units:
  `/var/backups/ohara/ntfy-alerts-20261124-213322-855868`. Rollback: copy those
  files back and run `sudo systemctl daemon-reload`.
- OpenWrt Wi-Fi and Unbound (2026-11-24, about 22:05 IST, owner-approved): first
  copies of `/etc/config/wireless` and `/etc/config/unbound` in
  `/root/ohara-backup/20261124-pre-radio-unbound/` on the device. Applied
  `unbound.ub_main.interface_auto=0`, `wireless.radio0.htmode=HE20`, and
  `country=IN` on both radios, then restarted Unbound and ran `wifi reload`.
  Verified: Unbound listens only on 127.0.0.1:5335 and the server's query to
  192.168.1.105:5335 is refused; through AdGuard from the server, `example.org`
  resolves, `doubleclick.net` returns 0.0.0.0, `adguard.xdadwal.in` returns
  192.168.1.101 and `dnssec-failed.org` returns SERVFAIL; `iw reg get` reports
  country IN; both hostapd configurations have `ieee80211ax=1` and `ieee80211n=1`;
  a 2.4 GHz client reconnected at 65 Mbit/s MCS 7 (above the 54 Mbit/s legacy
  limit) and the 5 GHz client at 1200 Mbit/s HE-MCS 11. The new `wifi` phase of
  `configs/openwrt/setup.sh` and the `interface_auto` line of its `dns` phase
  were written after the live change. The `wifi` phase was then run on the device: it reapplied the same values, `wifi reload` returned and both radios came back with country IN and `ieee80211ax=1`; it refuses a missing or malformed `COUNTRY` before changing anything. The `interface_auto` line of the `dns` phase was not rerun (already applied live). Rollback: copy the two
  saved files back to `/etc/config/`, then `/etc/init.d/unbound restart` and
  `wifi reload`.

### Repository compared with the live host; Bambuddy 2FA and portfolio assistant recorded (2026-11-25)

- Compared read-only from the host checkout at `544dd5a` (branch
  `feat/adguard-primary-resolver`, including #64). Byte-identical: the seven
  `configs/nginx/deployed/*.conf` files and `/etc/nginx/conf.d/` (no untracked
  files there), `/usr/local/lib/ohara/alerts.py` and `storage_watchdog.py`, and the
  SSH key-only policy. Nginx package `1.26.3-3+deb13u11`. All 20 running images
  match the pins in `versions/` (Immich's Valkey by digest). Projects running:
  `ohara`, `ohara-bambuddy`, `ohara-immich`, `ohara-kutt`, `ohara-maintainerr`,
  `ohara-ntfy`, `ohara-orcaslicer`; `ohara-dns` stopped by owner decision. Every
  `.env` key is known and `scripts/check` passes. The live Homepage files match
  the templates apart from rendered hostnames and the script-added Bambuddy and
  ntfy widgets.
- Docs corrected: Bambuddy's `admin` has TOTP two-factor enabled (the docs said
  no MFA); the portfolio's chat assistant, private `.env` and `/var/lib/portfolio`
  state are now described in operations.md and replication.md.
- Not compared: root-only `/etc/ohara/alerts.json` and `/etc/ohara/tls`,
  `nginx -t`, certificate expiry, and the OpenWrt device's live state.

### Root-only checks; Kutt retired and its data deleted (2026-11-25)

- Root-only comparison: the installed alert worker and both units match the repo;
  `/etc/ohara/alerts.json` is root:root 0600 and its checks and containers matched
  the running projects. `nginx -t` passes and `/etc/nginx/conf.d/` matched the
  deployed baseline. Private keys are 0600. The `ohara-wildcard` certificate
  (`*.xdadwal.in`, `xdadwal.in`) expires 2027-01-14.
- **Open: wildcard renewal is not automated.** The renewal config still uses the
  original manual hook (`local/wildcard-tls/manual-auth.py`), which only records
  the challenge locally; it has no cleanup hook. The GoDaddy hook and
  `/etc/ohara/dns-godaddy.json` are not installed. Certbot's timer will fail to
  renew from about 2026-12-15 until `sudo scripts/tls --configure-renewal` is run
  with an owner-supplied PAT (operations.md, GoDaddy DNS validation).
- Kutt retired by owner decision after #66, following the operations.md steps:
  `ohara-kutt` containers and network removed (no Kutt or PostgreSQL image was
  left on the host); `ohara-kutt.conf` and the live Homepage `services.yaml` backed
  up to root-only `/var/backups/ohara/kutt-retire-20261125-130933/`, the route
  removed, `nginx -t` passed and Nginx reloaded; the Homepage card and the four
  `KUTT_*` lines in `.env` removed; alerts reinstalled (no Kutt check, container
  or TLS entry; first run succeeded); `/ohara/kutt` (63 MB of PostgreSQL data and
  secret files) deleted. Nginx now rejects the TLS handshake for kutt.xdadwal.in;
  ohara.xdadwal.in and tv.xdadwal.in still answer, `scripts/check` and
  `scripts/status` pass, and nothing listens on 3010.
- Kept: older Kutt backups (six under `/var/backups/ohara/kutt*`, two under
  `local/kutt-backups`), pending an owner decision. The `kutt` rewrite on the
  OpenWrt AdGuard is the owner's to remove.

### Main stack split into dependency group files (2026-11-25)

- Repository change only; nothing was deployed, restarted or pulled on the host.
  `compose/stack.yaml` now names the `ohara` project and includes
  `compose/stack/media.yaml`, `navidrome.yaml`, `homepage.yaml` and
  `speedtest.yaml`.
- Static, Compose plugin 5.6.0: before and after, the resolved service
  definitions and `config --hash` values of all eleven services are identical in
  eight combinations (media-pool override on/off, theme override on/off, optional
  inputs set/unset), with and without `--no-env-resolution`. The only difference
  in the resolved model is that the unused top-level `x-*` anchor blocks are gone.
- Read-only on the xdadwal.in host with its real configuration and both overrides
  active: the new files give the same eleven hashes as the old file, and ten equal
  the running containers' `com.docker.compose.config-hash` labels. Homepage's
  label cannot be reproduced by a static render, which leaves its credentials
  empty by design; its old and new hashes are equal.
- Found while testing: an included file makes Compose read a `.env` beside it even
  with `--env-file /dev/null` and `COMPOSE_DISABLE_ENV_FILE=1`, and
  `project_directory: .` makes it read the repository's private `.env`. Every
  include entry therefore sets `env_file: /dev/null`; with that, planted `.env`
  files in the root, `compose/` and `compose/stack/` change nothing.
  `tests/test_stack.py` checks the form and the behaviour.
- Not run: `scripts/up` or any container start with the new files on this host.
  The CI container job starts the main stack from them.
- Rollback: revert the commit. No container, volume, network or host file changes
  either way.

### www redirect added; public-IP probe removed (2026-11-26)

- Live change on the xdadwal.in host, by owner request. `www.xdadwal.in` had a
  public DNS record but no server block, so HTTP was closed (444) and HTTPS
  refused the handshake. Two server blocks in `/etc/nginx/conf.d/ohara.conf` now
  return 301 to `https://xdadwal.in$request_uri` on ports 80 and 443, using the
  existing `ohara-wildcard` certificate (names `*.xdadwal.in`, `xdadwal.in`). No
  certificate, DNS record or port forward was changed.
- `/etc/nginx/conf.d/ohara-public-ip-test.conf` was removed: the router now
  forwards port 80, which is what the probe existed to confirm. Its access log
  `/var/log/nginx/ohara-public-ip-test.access.log` was left in place.
- Before editing, both tracked files were byte-identical to the live ones. Backup:
  `/var/backups/ohara/nginx-www-redirect-20261126-143712/` (both original files).
  `nginx -t` passed before and after; Nginx was reloaded, not restarted. The
  tracked `ohara.conf` is byte-identical to the live file again.
- Verified from the server:

  ```text
  $ curl -sI -H 'Host: www.xdadwal.in' http://127.0.0.1/
  HTTP/1.1 301 Moved Permanently
  Location: https://xdadwal.in/
  $ curl -sI --resolve www.xdadwal.in:443:127.0.0.1 'https://www.xdadwal.in/some/path?q=1'
  HTTP/1.1 301 Moved Permanently
  Location: https://xdadwal.in/some/path?q=1
  $ curl -sI https://xdadwal.in/
  HTTP/1.1 405 Method Not Allowed
  $ curl -sI -H 'Host: xdadwal.in' http://127.0.0.1/
  HTTP/1.1 301 Moved Permanently
  Location: https://xdadwal.in/
  $ curl -s -m 5 -H 'Host: 45.120.160.21' http://127.0.0.1/
  (curl exit 52: 52 = empty reply from server)
  $ spot checks (https status and redirect | http status and redirect)
  tv.xdadwal.in https 302 https://tv.xdadwal.in/web/ | http 301 https://tv.xdadwal.in/
  music.xdadwal.in https 302 https://music.xdadwal.in/app/ | http 301 https://music.xdadwal.in/
  ohara.xdadwal.in https 307 https://ohara.xdadwal.in/auth/signin?callbackUrl=%2F | http 301 https://ohara.xdadwal.in/
  $ curl -sI http://127.0.0.1:8010/   (portfolio backend directly, bypassing Nginx)
  HTTP/1.1 405 Method Not Allowed
  allow: GET
  $ curl -s -o /dev/null -w '%{http_code}' https://xdadwal.in/   (GET)
  200
  ```

  Through public DNS, `http://www.xdadwal.in/` and `https://www.xdadwal.in/` both
  return 301 to `https://xdadwal.in/`. Immich, Bambuddy, ntfy and OpenSpeedTest
  still return 200; the Jellyfin, Navidrome and Homepage responses equal the ones
  recorded immediately before the change.
- `curl -sI https://xdadwal.in/` returns 405, not 200. That is the portfolio
  application, which allows only GET on `/` (the backend answers HEAD with 405
  directly on 127.0.0.1:8010); it predates this change and Nginx does not cause
  it. A GET returns 200.
- Not verified: a request from outside the LAN (the public checks ran on the
  server through its public address) and a browser visit.
- Rollback: copy both files from the backup directory to `/etc/nginx/conf.d/`,
  run `sudo nginx -t`, then `sudo systemctl reload nginx`, and revert this commit.
- The reusable templates were left alone: they reference the HTTP-mode
  certificate, which lists only the configured hostnames, so a `www` HTTPS block
  there would present a certificate that does not cover `www`.

### Kutt DNS rewrite deleted; unused Docker objects removed (2026-11-26)

- By owner request. On the OpenWrt AdGuard (the resolver at `DNS_IP`), the one
  rewrite `kutt.xdadwal.in` to 192.168.1.101 was deleted through
  `/control/rewrite/delete`, using the same client and login as the service
  scripts. Rewrites went from 18 to 17; the other 17 are unchanged, and
  `ohara.xdadwal.in` still answers 192.168.1.101. `kutt.xdadwal.in` now gets the
  public answer (a wildcard CNAME to the apex), and Nginx refuses that name
  because it has no route. Nothing else on the device was changed.
- Docker, targeted removal only (no `docker system prune`, no container removed):
  - 28 images that no container uses, running or stopped: previous versions of
    current services and leftovers of retired ones (Kutt and its PostgreSQL,
    Pi-hole, Copyparty, a test Nginx). Images went from 47 to 19 and 24.99 GB to
    10.46 GB; the 19 left are the current pins, including the stopped bundled
    AdGuard's. Removed without `--force`.
  - 4 empty `ohara-bambuddy-smoke-*` networks left by smoke tests.
  - 52 anonymous volumes attached to no container. All were checked empty as
    root beforehand.
- Kept: the stopped `ohara-dns-adguard-1` container, its image and its
  `ohara-dns_default` network (bundled AdGuard is stopped, not removed, by owner
  decision), and the one volume a container uses.
- After: the same 18 containers are running with unchanged IDs; `scripts/status`
  shows all eleven main services reachable and the Immich, Bambuddy, Maintainerr
  and ntfy status commands pass.
- Consequence: rolling an application back to a previous image now needs a pull
  from its registry.

### Portfolio static files cached and compressed (2026-11-26)

- Live change on the xdadwal.in host, by owner request, in the `server_name
  xdadwal.in` HTTPS block of `/etc/nginx/conf.d/ohara.conf` only. Three new
  locations proxy to 127.0.0.1:8010 exactly like `location /` and add
  `Cache-Control`: one week for `/static/img/` and `/favicon.ico`, one hour for
  the rest of `/static/`. No `immutable` and no `always`. The same block gains
  `gzip_types` (CSS, JavaScript, JSON, XML, plain text, SVG) and `gzip_vary on`.
- Found first: no `add_header` exists anywhere in the live Nginx configuration,
  so the new locations drop no inherited header. `/etc/nginx/ohara-proxy-headers.conf`
  does not exist on this host; the live file inlines those headers, and the new
  locations do the same. `gzip on` is set in the distribution's
  `/etc/nginx/nginx.conf`, which has no tracked copy; it was left untouched and
  the types were set in the portfolio block instead, so no other site changes.
- The tracked file was byte-identical to the live one before editing. Backup:
  `/var/backups/ohara/nginx-portfolio-static-cache-20261126-153424/`. `nginx -t`
  passed before and after; Nginx was reloaded. The tracked `ohara.conf` is
  byte-identical to the live file again.
- Verified from the server (selected headers):

  ```text
  $ curl -sI https://xdadwal.in/static/css/output.css
    HTTP/1.1 200 OK
    Content-Type: text/css; charset=utf-8
    Content-Length: 25622
    Vary: Accept-Encoding
    etag: "6f4999367c0a9a65c1954a704ad4cc08"
    Cache-Control: public, max-age=3600
  $ curl -sI -H 'Accept-Encoding: gzip' https://xdadwal.in/static/css/output.css
    HTTP/1.1 200 OK
    Content-Type: text/css; charset=utf-8
    Vary: Accept-Encoding
    etag: W/"6f4999367c0a9a65c1954a704ad4cc08"
    Cache-Control: public, max-age=3600
    Content-Encoding: gzip
  $ curl -sI https://xdadwal.in/static/img/og.png
    HTTP/1.1 200 OK
    Content-Type: image/png
    Content-Length: 44950
    etag: "db939913ac129ada81b49756506df7b7"
    Cache-Control: public, max-age=604800
  $ curl -sI -H 'Accept-Encoding: gzip' https://xdadwal.in/static/img/og.png
    HTTP/1.1 200 OK
    Content-Type: image/png
    Content-Length: 44950
    etag: "db939913ac129ada81b49756506df7b7"
    Cache-Control: public, max-age=604800
  $ curl -sI https://xdadwal.in/favicon.ico
    HTTP/1.1 200 OK
    Content-Type: image/x-icon
    Content-Length: 2945
    etag: "13545db75886e6fe70581cb3e7903370"
    Cache-Control: public, max-age=604800
  $ curl -sI https://xdadwal.in/static/nope.css
    HTTP/1.1 404 Not Found
    Content-Type: application/json
    Content-Length: 22
    Vary: Accept-Encoding
  $ curl -sI https://xdadwal.in/
    HTTP/1.1 200 OK
    Content-Type: text/html; charset=utf-8
    Content-Length: 31103
    Vary: Accept-Encoding
  $ curl -sI -H 'Accept-Encoding: gzip' https://xdadwal.in/
    HTTP/1.1 200 OK
    Content-Type: text/html; charset=utf-8
    Vary: Accept-Encoding
    Content-Encoding: gzip
  $ curl -sI https://xdadwal.in/api/chat/history
    HTTP/1.1 405 Method Not Allowed
    Content-Type: application/json
    Content-Length: 31
  $ curl -s -D - -o /dev/null https://xdadwal.in/api/chat/history
    HTTP/1.1 200 OK
    Content-Type: application/json
    Content-Length: 2
  $ curl -sI -H 'Accept-Encoding: gzip' https://xdadwal.in/robots.txt
    HTTP/1.1 200 OK
    Content-Type: text/plain; charset=utf-8
    Vary: Accept-Encoding
    Content-Encoding: gzip
  $ curl -sI -H 'Accept-Encoding: gzip' https://xdadwal.in/sitemap.xml
    HTTP/1.1 200 OK
    Content-Type: application/xml
    Vary: Accept-Encoding
    Content-Encoding: gzip
  $ curl -sI -H 'Accept-Encoding: gzip' https://xdadwal.in/llms.txt
    HTTP/1.1 200 OK
    Content-Type: text/plain; charset=utf-8
    Vary: Accept-Encoding
    Content-Encoding: gzip
  $ curl -s -o /dev/null -w '%{http_code}' -H 'If-None-Match: "6f4999367c0a9a65c1954a704ad4cc08"' https://xdadwal.in/static/css/output.css
    304
  $ CSS bytes on the wire: plain vs gzip (GET)
    25622 -> 6640
  $ gzip body decodes to the same file
    identical
  $ spot checks (https status and redirect | http status and redirect)
    tv.xdadwal.in https 302 https://tv.xdadwal.in/web/ | http 301 https://tv.xdadwal.in/
    music.xdadwal.in https 302 https://music.xdadwal.in/app/ | http 301 https://music.xdadwal.in/
    ohara.xdadwal.in https 307 https://ohara.xdadwal.in/auth/signin?callbackUrl=%2F | http 301 https://ohara.xdadwal.in/
  $ browser-style revalidation: gzip + weak ETag as Nginx now sends it
    304
  $ same with a wrong ETag (must download again)
    200
  $ 304 response headers
    HTTP/1.1 304 Not Modified
    etag: "6f4999367c0a9a65c1954a704ad4cc08"
    Cache-Control: public, max-age=3600
  ```

  The stylesheet goes from 25,622 to 6,640 bytes on the wire and decodes to the
  identical file. Nginx weakens the ETag of a compressed response (`W/"..."`);
  the application still answers that with 304. The Jellyfin, Navidrome and
  Homepage responses equal those recorded before the change, and a Jellyfin
  script is still served uncompressed, as before.
- Side effects inside the portfolio block: HTML, `robots.txt`, `sitemap.xml`,
  `llms.txt` and JSON responses now carry `Vary: Accept-Encoding`, and the text
  ones are compressed when the client asks. None of them gets `Cache-Control`.
  The chat stream is `text/event-stream`, which is not in `gzip_types`.
- Not verified: a chat message through the assistant after the change, a request
  from outside the LAN, and a browser's own cache behaviour.
- Rollback: copy `ohara.conf` from the backup directory to `/etc/nginx/conf.d/`,
  run `sudo nginx -t`, then `sudo systemctl reload nginx`, and revert this commit.

### Portfolio CSS and fonts cached for a year (2026-11-26)

- Live change on the xdadwal.in host, by owner request, replacing nothing and
  adding two locations to the `server_name xdadwal.in` HTTPS block of
  `/etc/nginx/conf.d/ohara.conf`: `/static/css/` and `/static/fonts/` now get
  `Cache-Control: public, max-age=31536000, immutable`. The week for
  `/static/img/` and `/favicon.ico`, the hour for the rest of `/static/` and the
  compression settings from earlier the same day are unchanged.
- Precondition: the first check found the stylesheet linked without a version,
  so nothing was applied. Portfolio PR #12 (self-hosted fonts, `?v=<content
  hash>` on CSS and font URLs) was then merged by owner request and deployed at
  `4d7c740`. After that, every `/static/css/` and `/static/fonts/` URL on `/`,
  `/projects` and `/blog` ends in `?v=<hex>`, and the pages reference no Google
  font hosts.
- The tracked file was byte-identical to the live one before editing. Backup:
  `/var/backups/ohara/nginx-portfolio-static-cache-v2-20261126-160849/`. `nginx -t`
  passed before and after; Nginx was reloaded. There is still no other
  `add_header` in the live configuration. The tracked `ohara.conf` is
  byte-identical to the live file again.
- Verified from the server (selected headers):

  ```text
  CSS=/static/css/output.css?v=5117afd18b5b
  FONT=/static/fonts/hanken-grotesk-latin.woff2?v=1f21c6eaa000
  $ curl -sI "https://xdadwal.in/static/css/output.css?v=5117afd18b5b"
    HTTP/1.1 200 OK
    Content-Type: text/css; charset=utf-8
    Vary: Accept-Encoding
    Cache-Control: public, max-age=31536000, immutable
  $ curl -sI -H 'Accept-Encoding: gzip' "https://xdadwal.in/static/css/output.css?v=5117afd18b5b"
    HTTP/1.1 200 OK
    Content-Type: text/css; charset=utf-8
    Vary: Accept-Encoding
    Cache-Control: public, max-age=31536000, immutable
    Content-Encoding: gzip
  $ curl -sI "https://xdadwal.in/static/fonts/hanken-grotesk-latin.woff2?v=1f21c6eaa000"
    HTTP/1.1 200 OK
    Content-Type: font/woff2
    Cache-Control: public, max-age=31536000, immutable
  $ curl -sI -H 'Accept-Encoding: gzip' "https://xdadwal.in/static/fonts/hanken-grotesk-latin.woff2?v=1f21c6eaa000"
    HTTP/1.1 200 OK
    Content-Type: font/woff2
    Cache-Control: public, max-age=31536000, immutable
  $ curl -sI https://xdadwal.in/static/img/og.png
    HTTP/1.1 200 OK
    Content-Type: image/png
    Cache-Control: public, max-age=604800
  $ curl -sI https://xdadwal.in/favicon.ico
    HTTP/1.1 200 OK
    Content-Type: image/x-icon
    Cache-Control: public, max-age=604800
  $ curl -sI https://xdadwal.in/static/fonts/README.md
    HTTP/1.1 200 OK
    Content-Type: text/markdown; charset=utf-8
    Cache-Control: public, max-age=31536000, immutable
  $ curl -sI https://xdadwal.in/static/nope.css
    HTTP/1.1 404 Not Found
    Content-Type: application/json
    Vary: Accept-Encoding
  $ curl -sI https://xdadwal.in/
    HTTP/1.1 200 OK
    Content-Type: text/html; charset=utf-8
    Vary: Accept-Encoding
  $ curl -sI -H 'Accept-Encoding: gzip' https://xdadwal.in/
    HTTP/1.1 200 OK
    Content-Type: text/html; charset=utf-8
    Vary: Accept-Encoding
    Content-Encoding: gzip
  $ curl -sI https://xdadwal.in/projects
    HTTP/1.1 200 OK
    Content-Type: text/html; charset=utf-8
    Vary: Accept-Encoding
  $ curl -sI https://xdadwal.in/robots.txt
    HTTP/1.1 200 OK
    Content-Type: text/plain; charset=utf-8
    Vary: Accept-Encoding
  $ curl -sI https://xdadwal.in/api/chat/history
    HTTP/1.1 405 Method Not Allowed
    Content-Type: application/json
  $ curl -s -D - -o /dev/null https://xdadwal.in/api/chat/history
    HTTP/1.1 200 OK
    Content-Type: application/json
  $ curl -s -o /dev/null -w '%{http_code}' -H 'If-None-Match: "db939913ac129ada81b49756506df7b7"' https://xdadwal.in/static/img/og.png
    304
  $ spot checks (https status and redirect | http status and redirect)
    tv.xdadwal.in https 302 https://tv.xdadwal.in/web/ | http 301 https://tv.xdadwal.in/
    music.xdadwal.in https 302 https://music.xdadwal.in/app/ | http 301 https://music.xdadwal.in/
    ohara.xdadwal.in https 307 https://ohara.xdadwal.in/auth/signin?callbackUrl=%2F | http 301 https://ohara.xdadwal.in/
  ```

  All five font files named in the stylesheet return 200 with the year-long
  policy. Immich, Bambuddy, ntfy and OpenSpeedTest still return 200; the
  Jellyfin, Navidrome and Homepage responses equal the earlier ones.
- The rule matches by path, not by the presence of `?v=`: the bare
  `/static/css/output.css` and `/static/fonts/README.md` also get the year. Pages
  no longer link the bare stylesheet URL. The rule therefore depends on the
  portfolio linking these files only through `static_url()`.
- Not verified: a browser's own cache behaviour across a portfolio deploy, a
  request from outside the LAN, and a chat message after the change.
- Rollback: copy `ohara.conf` from the backup directory to `/etc/nginx/conf.d/`,
  run `sudo nginx -t`, then `sudo systemctl reload nginx`, and revert this commit.
  Browsers that already stored the stylesheet or a font keep it for up to a year
  under that versioned URL, which is harmless because the content under a given
  version never changes.
