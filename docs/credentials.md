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
credential entries in `.env.example`; it contains no working credential defaults.

| Service | Required keys |
|---|---|
| Homepage | `HOMEPAGE_AUTH_ENABLED=true`, `HOMEPAGE_AUTH_PASSWORD`, `HOMEPAGE_AUTH_SECRET` |
| Jellyfin | `JELLYFIN_PASSWORD` |
| qBittorrent | `QBITTORRENT_PASSWORD` |
| Radarr | `RADARR_PASSWORD`, `RADARR_API_KEY` |
| Sonarr | `SONARR_PASSWORD`, `SONARR_API_KEY` |
| Prowlarr | `PROWLARR_PASSWORD`, `PROWLARR_API_KEY` |

Homepage passwords require at least 8 characters, media passwords 16, and the
Homepage session secret 32. Acquisition API keys must be 32 hexadecimal characters.
Use independent values. Existing installations must use their actual application
values. Seerr initially authenticates through Jellyfin; OpenSpeedTest has no login.
Application databases retain their own account hashes/session tokens: this change
consolidates operator inputs, not application-managed persistent state.

Optional widget inputs are `HOMEPAGE_VAR_JELLYFIN_API_KEY` and
`HOMEPAGE_VAR_SEERR_API_KEY`. Copy actual application-issued keys after account
setup; omit/comment them until available. See [widget setup](homepage-widgets.md).

## Migrate the old files

With the updated checkout, before running setup/up:

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
