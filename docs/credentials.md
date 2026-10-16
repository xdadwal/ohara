# User-managed credentials

Ohara reads credentials from files you create. Agents and setup commands must not
invent, generate, replace, or rotate passwords, acquisition API keys, or Homepage's
session secret. Use your password manager or your own tools to choose the values,
then save them locally. Do not send secret values through chat.

## Prepare the files

The two tracked examples contain empty fields, not working default credentials.
From the repository root, create private copies if they do not already exist:

```sh
umask 077
mkdir -p local
chmod 700 local
test -e local/homepage.env || install -m 600 configs/credentials/homepage.env.example local/homepage.env
test -e local/media-credentials || install -m 600 configs/credentials/media-credentials.example local/media-credentials
```

Fill in those files using a local editor or password-manager export. Keep both
files mode 0600, owned by the deployment operator. Do not replace existing files
merely to follow these instructions. `.env` is non-secret deployment configuration;
credentials belong in the ignored `local/` directory.

| File | Required inputs |
|---|---|
| `local/homepage.env` | `HOMEPAGE_AUTH_ENABLED=true`, `HOMEPAGE_AUTH_PASSWORD`, `HOMEPAGE_AUTH_SECRET` |
| `local/media-credentials` | `JELLYFIN_PASSWORD`, `QBITTORRENT_PASSWORD`, `RADARR_PASSWORD`, `SONARR_PASSWORD`, `PROWLARR_PASSWORD`, `RADARR_API_KEY`, `SONARR_API_KEY`, `PROWLARR_API_KEY` |

Homepage passwords need at least 8 characters, preserving the
operator's existing shorter passwords. Media-service passwords need at least
16 characters. Use independent values per service.
Homepage's session secret needs at least 32 characters. The three acquisition API
keys must each be exactly 32 hexadecimal characters, matching those applications'
format. Supply them yourself for a fresh installation; for an existing server,
retrieve the actual keys through its private settings rather than choosing new ones.
Seerr uses the Jellyfin password for media-server login; it has no separate initial
password in this setup. OpenSpeedTest has no login.

Each non-comment line is literally `KEY=value`. Spaces, `$`, `#`, `=`, quotes and
other printable punctuation within values are literal. Do not add shell quotes,
`export`, multiline values or command substitutions expecting them to execute.
No file is sourced or evaluated. Unknown/duplicate keys, empty/short values,
control characters, symlinks and group/world-readable files are rejected. Errors
name files/keys, never the supplied value. Compose consumes Homepage's environment
with `format: raw` to preserve literal characters.

## Setup and preservation

Run `sudo scripts/setup --dry-run`, `sudo scripts/setup --non-interactive`, then
`scripts/check` and `scripts/up`. Python validates both inputs before host provisioning
or storage preparation. On a machine without Python, the shell bootstrap first
requires the input files; Python itself must be installed before full content
validation is possible. `scripts/check --static` intentionally skips private files.
`scripts/media-setup --owner-email YOUR_REAL_EMAIL` creates first-run media accounts
and connections using your supplied values.

Setup derives media first-run configuration from these inputs and never writes
either source file. Password hashing uses cryptographically random salts; salts
are not login credentials. Applications also issue their own session and integration
tokens through supported APIs. Those tokens are not strings invented by the agent.

Reruns preserve existing application configuration and the media setup journal.
Editing an input file alone is not a supported password rotation for existing
accounts. Update the actual account through its supported private UI/API and keep
its input file in sync; preserve/back up current configuration before rotation.
Do not delete databases, source files or local/media-state.json to reset an account.
If a required input is missing, restore it from your private backup; setup fails
instead of generating replacement credentials. Previously generated files remain
readable if valid; switching values requires a deliberate account update.

Copyparty and Pi-hole are removed. The retired local/credentials file and their
old private config files are not read or required. Setup does not create them,
modify them, or delete them; retain backups before any manual cleanup.

Keep `.env`, `local/`, and application state in encrypted backups. Keep passwords,
API keys, session secrets and resolved Compose output out of Git, logs and chat.
Disposable tests use explicit dummy input files in isolated test directories;
fixtures never feed deployment defaults or tracked example credentials.
