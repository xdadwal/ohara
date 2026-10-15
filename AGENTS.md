# Working on Ohara

Ohara provisions a small Linux homeserver. Read README.md and docs/operations.md
before changing deployment behavior. The approved migration plan is under
docs/superpowers/plans/.

- Active applications: Seerr (Jellyseerr's successor), Pi-hole, Copyparty,
  OpenSpeedTest, and Homepage. Nginx and Certbot run on the host. Domain: xdadwal.in.
- Homepage serves the apex with password login; no Docker socket or API keys.
  Immich will share this machine in its own Compose project; deployment is pending
  storage/hardware/backup details. See docs/immich-next.md.
  Do not introduce removed media/download services or additional infrastructure.
- `compose.yaml`, `.env.example`, and `versions.env` define deployment;
  `.env` and `local/` are private. Never print secrets or resolved Compose config.
- Commands resolve their own repository path. Use `scripts/setup --help`,
  `scripts/check`, `scripts/up`, `scripts/status`, and `scripts/tls --help`.
- Setup prepares a supported Linux host; `up` starts local services; TLS activation
  is a separate explicit step after owner/account setup. Do not deploy to a live
  host merely because a code change was requested.
- Backend web ports bind to loopback. Pi-hole DNS binds only to the LAN IP;
  its administration interface must never get a public Nginx route.
- Preserve configuration, volumes, existing files/ownership, unrelated Nginx sites,
  SSH access, networking, and host DNS. No recursive chown or destructive cleanup.
- Never execute dotenv contents. Add configuration validation before consumption.
- Verify with `python3 -m unittest discover -s tests -v`, `tests/test_setup.sh`,
  `tests/test_cli.sh`, and `tests/static.sh`. Docker smoke tests: `tests/smoke.sh`.
- Report static checks, disposable runtime checks, real Linux provisioning, and
  public reachability separately. One does not establish the others.
- Commit feature work, push its feature branch, and open a PR unless opted out.
  Never merge or rewrite Git history without authorization.
