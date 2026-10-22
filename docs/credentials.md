# User-managed credentials

The repository's ignored **`.env`** is the single editable input for deployment
settings, Homepage login/widget keys and media-service credentials. Keep it owned
by the operator with mode **0600**. Never send secret values through chat or commit
this file. Agents and setup must not invent, generate or rotate passwords,
acquisition API keys or Homepage's session secret.

## Fresh installation

```sh
umask 077
test -e .env || install -m 600 .env.example .env
chmod 600 .env
```

Edit `.env` privately. Fill deployment settings and uncomment/fill the required
credential entries copied from `.env.example` into `.env`; the example contains
no working credential defaults.

| Service | Required keys |
|---|---|
| Homepage | `HOMEPAGE_AUTH_ENABLED=true`, `HOMEPAGE_AUTH_PASSWORD`, `HOMEPAGE_AUTH_SECRET` |
| Jellyfin | `JELLYFIN_PASSWORD` |
| qBittorrent | `QBITTORRENT_PASSWORD` |
| Radarr | `RADARR_PASSWORD`, `RADARR_API_KEY` |
| Sonarr | `SONARR_PASSWORD`, `SONARR_API_KEY` |
| Prowlarr | `PROWLARR_PASSWORD`, `PROWLARR_API_KEY` |
| Lidarr | `LIDARR_PASSWORD`, `LIDARR_API_KEY` |
| Bazarr | `BAZARR_PASSWORD`, `BAZARR_API_KEY` |
| Navidrome | `NAVIDROME_PASSWORD` |

Homepage passwords require at least 8 characters, media passwords 16, and the
Homepage session secret 32. Acquisition API keys must be 32 hexadecimal characters.
Use independent values. Existing installations must use their actual application
values. Seerr initially authenticates through Jellyfin; OpenSpeedTest has no login.
Navidrome uses its supplied password for supported first-run account creation and
login verification; it needs no additional API key. Subtitle-provider credentials,
when required, are entered privately in Bazarr after the operator chooses providers.
Application databases retain their own account hashes/session tokens: this change
consolidates operator inputs, not application-managed persistent state.

Optional widget inputs are `HOMEPAGE_VAR_JELLYFIN_API_KEY` and
`HOMEPAGE_VAR_SEERR_API_KEY`. Copy actual application-issued keys after account
setup; omit/comment them until available. See [widget setup](homepage-widgets.md).
Navidrome's Homepage widget needs no extra input: commands derive its Subsonic
token locally from NAVIDROME_PASSWORD and the template's non-secret salt. Only
the derived token is passed to Homepage; the plaintext password is not.

## Migrate the old files

With the updated checkout, before running setup/up, privately add any missing
`LIDARR_PASSWORD`, `LIDARR_API_KEY`, `BAZARR_PASSWORD`, `BAZARR_API_KEY` and
`NAVIDROME_PASSWORD` entries to root `.env`, preserving existing values. Leave
the legacy files intact for migration. The new passwords require at least 16
characters and API keys exactly 32 hexadecimal characters. Then run:

```sh
chmod 600 .env
scripts/migrate-credentials
scripts/check
scripts/up
```

The migration validates both legacy files (`local/homepage.env` and
`local/media-credentials`), preserves every value, and rejects conflicts with
existing `.env` entries. It validates the combined file before atomically replacing
`.env`, then removes the two old inputs. Original files are retained in a new
private directory under `../ohara-backups/credentials-TIMESTAMP`; use
`--backup-dir /private/new-directory` to choose another destination. No password,
API key, database or setup journal is reset. Rerunning migration on a unified
installation is a no-op. Missing/invalid legacy files stop migration without
changing the active input. Keep the backup encrypted with your other recovery data.

Legacy split files are deprecated and remain ignored by Git; runtime commands
consume only `.env`. Never put new entries in the legacy files. The entries in `.env.example` are commented and empty; setup never supplies them.

## Literal values and validation

Each non-comment line is `KEY=value`. Credential values preserve spaces, `$`, `#`,
`=`, quotes and other printable punctuation literally. Do not wrap values in shell
quotes or add inline comments. Deployment fields such as paths/hostnames retain
their existing stricter syntax. Never source/evaluate this file. Unknown/duplicate
keys, missing required credentials, short values, control characters, symlinks
and group/world-readable credential files are rejected without echoing values.

Use `scripts/check`, `scripts/up` and other project commands rather than direct
`docker compose`: scripts disable Compose dotenv loading and pass only Homepage's
allowlisted credentials through the child environment. Media passwords/API keys
are consumed by host setup/API clients and are not injected into Homepage or
unrelated containers. `scripts/check --static` renders empty secret placeholders
and deliberately skips credential validation. Never publish resolved Compose
output, container environment inspection or `.env` contents.

## Setup and rotation

Run setup/check/up as documented in README. Setup validates `.env` before host
provisioning/storage changes and never rewrites it. Initial media configuration
uses these supplied values; reruns preserve existing accounts and the journal.

Editing `.env` alone does **not** rotate existing media accounts. Update an account
through its supported private UI/API and keep `.env` synchronized. Homepage login
and widget inputs take effect when its container is recreated with `scripts/up`.
Do not delete databases or `local/media-state.json` to reset an account. Missing
values must be restored/provided privately; setup never generates replacements.

Keep `.env`, essential `local/`, application state and TLS material in encrypted
backups. Retired Copyparty/Pi-hole inputs are not consumed and may be archived
separately. Optional GoDaddy DNS API activation still uses the documented private
JSON input and a root-only installed copy; no DNS token has been supplied here.

## Optional AdGuard account

The optional DNS project reads `ADGUARD_PASSWORD` from the same private `.env`.
Choose a separate nonempty password of at most 72 UTF-8 bytes;
the initial username is `admin`. Initial setup hashes it locally with bcrypt.
It is never passed to Compose or Homepage. Existing AdGuard accounts/configuration
are preserved; editing the input alone does not rotate a password. See
[AdGuard operations](adguard.md). The eleven-app stack does not require this key.

## Optional Immich database

Immich reads `IMMICH_DB_PASSWORD` from the same private `.env`, mode 0600. Supply
an independent value of at least 16 ASCII letters/digits, following upstream's
character restrictions. Only its server and database containers receive this
value. The main stack does not require it. No password is generated or rotated;
changing the input alone does not change an existing database account. The Immich
owner has a separate application account, created privately during onboarding.
See [Immich operations](immich.md) for preparation and backup requirements.

The operator explicitly accepted the existing shorter Immich DB password on this
host. `scripts/immich prepare|check|up --allow-short-db-password` supports this
per-command exception without changing normal validation defaults or unrelated
service credentials. Empty or non-alphanumeric values remain rejected.

Optional HOMEPAGE_VAR_IMMICH_API_KEY is an Immich-issued key restricted to
server.statistics, supplied privately after owner setup. It is forwarded only
to Homepage for its native statistics widget. See homepage-widgets.md.
