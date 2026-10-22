# Immich deployment status

The independent Immich project is running on this Ohara host with PostgreSQL and
Valkey; machine learning is disabled. Its approved paths are
`/ohara/immich/library` and `/ohara/immich/postgres`. The operator supplied the
DB password and explicitly accepted its shorter length through a per-command
exception.

Owner onboarding is complete. Public HTTPS at `https://immich.xdadwal.in` was
activated with the existing wildcard certificate, preserving the previous
LAN-only route in a private backup. Homepage has a live link, and AdGuard rewrites
the hostname to 192.168.1.101 locally. The native Homepage statistics widget is
live, using HOMEPAGE_VAR_IMMICH_API_KEY supplied privately in .env. Its
authenticated statistics proxy was verified without exposing the key.

The hostname and Homepage-to-Immich HTTPS path respond successfully from this
host; independent off-network browser reachability is not yet confirmed.
Library size/growth, independent backup destination/retention, real photo/video
and phone checks and an isolated restore remain pending. See
[Immich operations](immich.md). Do not treat the archive as backup-ready yet.

Google OAuth is enabled with automatic registration and password login disabled.
Only administrators can provision approved users by their exact Google email;
see the onboarding workflow in immich-google-oauth.md. The supplied client passed initial validation and web/mobile
authorization URL checks. An approved-account Google login and uninvited-account
rejection still need a real browser test; see immich-google-oauth.md.
