# Verification record

Implementation verification on 2026-10-15:

- 28 Python tests passed, covering strict configuration, command-injection rejection,
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
