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
Rendered Nginx reaches jellyfin.xdadwal.in over fixture TLS. Existing Homepage,
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
