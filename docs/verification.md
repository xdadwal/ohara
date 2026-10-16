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
