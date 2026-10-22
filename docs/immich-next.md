# Immich deployment status

The independent Immich project is running on this Ohara host with PostgreSQL and
Valkey; machine learning is disabled. Its approved paths are
`/ohara/immich/library` and `/ohara/immich/postgres`. The operator supplied the
DB password and explicitly accepted its shorter length through a per-command
exception.

Owner onboarding and public HTTPS at `https://immich.xdadwal.in` are configured.
Homepage has the native widget showing photos, videos and total storage usage;
its private statistics key and authenticated proxy were verified. AdGuard rewrites
the hostname to 192.168.1.101 for local clients, with UDP/TCP answers verified.

Google-only OAuth is enabled with password login and automatic registration
disabled. The operator confirmed successful OAuth login on 2026-10-22. Only an
administrator can provision another user by their exact Google account email;
see the workflow in [Google OAuth setup](immich-google-oauth.md).

## Current release decisions

The operator accepted capacity for the current single-user deployment; no extra
capacity or quota work is required for this release. Independent backups,
retention and isolated restore testing are explicitly deferred for later, rather
than release blockers. No backup/restore readiness is claimed.

Both hosted push and pull-request CI runs for implementation commit 5c21a89 passed
all three jobs: configuration, existing stack containers and Immich containers.
All 152 local Python tests and required setup/CLI/static checks passed too. The
PR description and documentation record the accepted scope; merging still
requires separate operator authorization.

## Follow-up work

Independent media/database backups and restoration are deferred. Real phone
backup, representative large-video/playback tests, an uninvited Google account
rejection test and independent off-network browser access are not recorded as
verified. These remain follow-up acceptance items; successful owner OAuth login
must not be conflated with completion of every one of these checks. See
[Immich operations](immich.md).
