# Maintainer commands

From any current directory, invoke the checkout's `scripts/ohara` by its absolute
path. Within the checkout:

```sh
./scripts/ohara --help
./scripts/ohara check --static
./scripts/ohara status
./scripts/ohara doctor
./scripts/ohara doctor --json
./scripts/ohara tools --dry-run
sudo ./scripts/ohara tools --install
```

The unified entry point also supports `check`, `up` and `status` with the existing
semantics. Existing scripts remain supported. Optionally add the checkout's
scripts directory to your own PATH to use `ohara doctor`; setup does not modify
shell configuration or install a global executable pointing at a moving checkout.

## Doctor

Doctor is read-only and does not invoke sudo, repair permissions, start services,
change networking or install packages. It checks configuration, systemd health,
Nginx service/configuration, Certbot timer, optional Tailscale online state, optional
terminal tools, storage capacity/inodes, containing mounts, media directory mode
permissions and the existing container/HTTP health checks. It inspects the standard
Ohara and Ohara-wildcard certificate paths when readable. It warns on certificates
with less than 30 days left, missing certificates, unknown expiry and permissions
that prevent validation. Run `sudo nginx -t` separately for authoritative privileged
configuration validation. Child stderr and credential values are never printed.

Capacity warnings start at 85%; failures start at 95% for blocks or inodes. Storage
statistics describe the containing filesystem, so DATA_ROOT and MEDIA_ROOT can
report the same disk. A root-filesystem mount warns for manual review; it can be
intentional. Other mount points still require comparison to the intended storage
layout: doctor cannot infer which disk/NAS should be mounted from these paths.
Media write checks use configured UID/GID mode bits, not ACLs, supplementary groups,
read-only mount enforcement or an actual write test. Inspect failures locally.

Each result has a check name, status (`ok`, `warn`, `fail`, `skip`) and detail.
Exit status is 1 if any check fails, 0 otherwise; warnings/skips are not proof that
those checks passed. JSON includes `checks` and the matching `exit_code`. Individual
subprocesses are bounded; aggregate runtime includes up to five seconds per HTTP
service. Results can include local mount paths and should still be reviewed before
sharing. Missing/invalid .env fails configuration but independent host checks run.

Doctor does not establish public reachability, real acquisition/playback, SSH
access policy, backup freshness/restorability, certificate hostname coverage or
successful ACME renewal. Custom certificate locations are not discovered.

## Optional terminal tools

`tools` without arguments or with `--dry-run` only reports availability. Explicit
`--install` requires root and supports Ubuntu 24.04 / Debian 13. It installs missing
`tmux` and `bpytop` packages through distribution apt, preserving installed versions
and all shell/dotfiles settings. No background monitor or extra container is added.
Python 3 must already be available; use normal bootstrap first on a fresh machine.

Use `tmux new -s maintenance`, detach with Ctrl-b then d, and reconnect with
`tmux attach -t maintenance`. Run `bpytop` for interactive CPU/RAM/process/network
and disk monitoring. These are operator tools; agents should use bounded doctor
output rather than launching an unattended interactive terminal session.
