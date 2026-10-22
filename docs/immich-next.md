# Immich deployment status

The independent Immich project is running on this Ohara host with PostgreSQL and
Valkey; machine learning is disabled. Its approved paths are
`/ohara/immich/library` and `/ohara/immich/postgres`. The operator supplied the
DB password and explicitly accepted its shorter length through a per-command
exception.

LAN-only HTTPS onboarding at `https://immich.xdadwal.in` is active with the
existing wildcard certificate. A live Homepage card and an AdGuard rewrite to
192.168.1.101 are installed. UDP/TCP DNS, trusted LAN HTTPS and rejection of
untrusted/forged-forwarding sources were checked.

Next: create the owner and verify login, then enable public access deliberately.
Library size/growth, independent backup destination/retention, real photo/video
and phone checks and an isolated restore remain pending. See
[Immich operations](immich.md). Do not treat the archive as backup-ready yet.
