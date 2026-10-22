# Immich implementation and remaining deployment steps

The independent Immich Compose project is now implemented. See
[Immich operations](immich.md) for configuration, private startup, backups,
restore testing, drive/machine migration and deliberate HTTPS activation.

Confirmed: same Ohara host; photo root `/ohara/immich/library`; PostgreSQL in a
container with host storage `/ohara/immich/postgres`; no machine-learning service
or AI jobs. The planned hostname remains `immich.xdadwal.in`.

Pending before production use: library size/growth, independent backup destination
and retention, user-supplied database password, private owner setup, upload/video
checks and an isolated backup restore. Public HTTPS and a Homepage link have been requested; activation is pending
private inputs, owner readiness and host administrator access. No live deployment or public activation is implied by the
repository implementation.
