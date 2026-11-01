# Kutt short links and QR codes

Kutt is optional, in the independent `ohara-kutt` Compose project: one Kutt app
and one dedicated PostgreSQL 17 database. Redis is disabled. Host Nginx exposes
HTTPS; Kutt binds only `127.0.0.1:3010`, and PostgreSQL publishes no host port.
The database, private inputs and lifecycle are independent of Immich and the USB
media pool. Main `scripts/setup`/`scripts/up` do not start this optional project.

## Features and reviewed behavior

The official v3.2.6 release supports editing a redirect destination while retaining
the short URL, browser-side QR display, account authentication and an admin ban
operation. Banning stops redirection without deleting the link. A supported unban
flow was not found; do not describe it as a reversible enable/disable switch.
The owner accepted this scope. Expiration is different: upstream periodically
deletes expired links, so do not use it as a pause mechanism. QR codes encode the
stable short URL, not its current target; changing the target needs no new QR.
Short codes are random by default (six characters in the pinned release); a
custom alias is optional. Example codes are illustrative, not created or reserved
before the service and owner account exist.

The helper uses official release/digest pins in `versions.kutt.env`, inspected
for amd64/arm64. Do not replace pins with `latest`. PostgreSQL uses the reviewed
Alpine image's UID/GID 70; preparation confirms its UID on the actual target.
Both containers run without root/capabilities, with read-only root filesystems
and bounded temporary writable directories. The database's `kutt` role owns only
its own database and has no superuser/role/database-creation/replication powers.
The bootstrap postgres password is cleared during first initialization, so its
superuser has no password for network login. Local administrative access is via
`docker exec` and its private Unix socket; do not mount that socket elsewhere.

References: [upstream](https://github.com/thedevs-network/kutt),
[PostgreSQL configuration](https://github.com/thedevs-network/kutt/blob/v3.2.6/docker-compose.postgres.yml),
[QR UI](https://github.com/thedevs-network/kutt/blob/v3.2.6/server/views/partials/links/actions.hbs),
[QR generation](https://github.com/thedevs-network/kutt/blob/v3.2.6/static/scripts/main.js),
[link routes](https://github.com/thedevs-network/kutt/blob/v3.2.6/server/routes/link.routes.js).
Source review alone is not runtime verification; the tests below distinguish both.

## Target discovery and private inputs

Read AGENTS.md, [adding services](adding-services.md), [agent setup](agent-setup.md),
[credentials](credentials.md) and [operations](operations.md) before installation.
Inspect existing containers, interfaces, mounts, free space, ports, Nginx sites,
TLS coverage, public DNS and AdGuard rewrites. Preserve accounts/state. Example
identities below describe the current domain, not arbitrary target machines.

```sh
scripts/status
ip -j -4 address show
findmnt --target /ohara -o TARGET,FSTYPE
ss -ltn
sudo nginx -t
dig +short kutt.xdadwal.in A
```

Choose the actual hostname and local independent filesystem. Default non-secret
settings are `KUTT_HOST=kutt.DOMAIN`, `KUTT_ROOT=DATA_ROOT/kutt`, `KUTT_MOUNT=/`.
Set them in private `.env` if different. `KUTT_LAN_NETWORK` must be the verified
private IPv4 LAN CIDR; it defaults to the explicitly configured ADGUARD_NETWORK.
The proxy verifies that an actual global-scope host interface is within it.
On other domains, provide the target's `KUTT_TLS_CERT` and `KUTT_TLS_KEY` absolute
paths. This host defaults to its existing `ohara-wildcard` certificate; another
host must not copy certificate assumptions or private keys from the repository.
Provision DNS and a trusted certificate covering the chosen host before proxy
activation, using the target's approved TLS workflow. Do not expose a router DNS
port or create a router SSH forward. Only existing public 80/443 are needed.

The owner supplies independent literal inputs in private mode-0600 `.env`:

- `KUTT_DB_PASSWORD`: at least 16 characters.
- `KUTT_JWT_SECRET`: at least 32 characters, persisted signing secret.
Choose the owner password directly in Kutt’s UI after containers are running;
it is not a required dotenv input. No owner account is auto-created.

Do not generate values without explicit owner authorization, request them in
chat, source `.env`, reuse an Immich/other application secret, or pass the whole
file to Docker. Leading/trailing whitespace is rejected because Kutt trims file
inputs. Quoted SQL punctuation is handled by the reviewed initialization script;
credential text is never executed or interpolated into shell commands.

Only DB/JWT values are needed to prepare and start services. First start the
containers, then create the owner through the private UI/tunnel, then verify
login and activate public HTTPS. `prepare` writes only narrow private
files under `KUTT_ROOT/secrets`, not a second editable dotenv. The DB input is
read-only in the two relevant containers; JWT is read-only in Kutt only. The UI
password is not provisioned into either container or Homepage by our helpers. Existing secret
files must match private inputs; reruns refuse implicit rotation. Preserve the
same JWT when restoring state so existing sessions are not invalidated by accident.

## Fresh installation and owner onboarding

From the repository root after supported host/Docker setup:

```sh
scripts/kutt check --static
docker pull "$(sed -n 's/^KUTT_IMAGE=//p' versions.kutt.env)"
docker pull "$(sed -n 's/^KUTT_POSTGRES_IMAGE=//p' versions.kutt.env)"
sudo scripts/kutt prepare
sudo scripts/kutt up
sudo scripts/kutt status
sudo scripts/kutt-proxy --apply --onboarding-only
scripts/kutt dns
scripts/kutt homepage
```

The `sed` commands read only the versioned, validated public image pins; they do
not execute or read private dotenv contents. Preparation creates only missing
directories with exact ownership: project/secrets root:root 0700, postgres 70:70
0700. The private DB file is RUN_UID:70 mode 0440, JWT is RUN_UID:RUN_GID 0400.
There is no recursive chown or automatic existing-data cleanup. PostgreSQL's
standard first-run entrypoint sources `configs/kutt/10-kutt.sh` only for a new
empty cluster; it creates the restricted app role/database and completion marker.
Existing clusters never rerun that script. A partial initialization without the
marker remains unready for operator review; do not delete its data and retry.
App migrations run at startup using Kutt's supported release command.

The proxy helper backs up only its managed route in
`/var/backups/ohara/kutt-proxy-*`, validates TLS and Nginx, then reloads; failure
restores that route. LAN restrictions are checked before HTTP redirects as well
as on HTTPS, using actual source addresses and discarding incoming forwarding
chains. Only LAN/loopback clients can reach the entire site during onboarding.
Native owner-creation paths remain LAN-only after public activation, including
the `/api/v2` alias, so lost/reset state cannot expose public owner signup.
Nginx adds no-store and disables proxy caching to preserve mutable destinations;
no external CDN caching is configured. Public access logs are disabled for this
host so short codes/targets/tokens are not recorded as request URLs there.

Verify local DNS against the actual configured AdGuard address, both protocols:

```sh
dig @192.168.1.101 kutt.xdadwal.in A
dig +tcp @192.168.1.101 kutt.xdadwal.in A
```

Replace the address/hostname from target discovery. The DNS helper selectively
adds exactly this rewrite and refuses conflicts. It never modifies router/client
DNS or removes other rewrites. The Homepage helper selectively adds a plain link,
preserving widgets and unrelated cards and backing up YAML under ignored
`local/kutt-backups`. The initial Homepage/AdGuard seeds cover the default host;
Homepage's non-secret KUTT host variable supports configured alternatives. If a
live Homepage predates that variable, its helper stores the resolved URL. Verify
the card through the existing password-protected Homepage API; do not reset it.
No Kutt account password/API key is forwarded to Homepage.

On the real LAN, open `https://kutt.xdadwal.in` (use the chosen target hostname).
The owner creates the first administrator with their actual email and a password
chosen directly in that UI. After account creation, explicitly sign in once; do not assume the
welcome screen proves authentication. The helper does not invent emails or create
users. SMTP, OIDC, public registration and anonymous link creation stay disabled.
Without SMTP, email reset/verification/report features are unavailable; preserve
account inputs and backups rather than enabling another mail service by default.

### Remote owner creation through existing Tailscale SSH

An owner away from the LAN can bootstrap through ordinary OpenSSH over the
already enrolled private tailnet. This does not enable Tailscale SSH, Serve,
Funnel, subnet routes, DNS acceptance or a public port-22 forward. Public
first-owner creation remains blocked by Nginx. Prerequisites are the same private
DB/JWT inputs, started Kutt/Postgres backend,
existing authorized SSH keys and an enrolled owner client with permitted SSH.
A tunnel cannot make an unstarted backend available.

Discover the actual server tailnet IPv4 with `tailscale ip -4` and existing SSH
login with the target's account/session configuration. On the owner's laptop,
forward a free loopback-only local port to Kutt's loopback backend:

```sh
# Replace SSH_LOGIN and SERVER_TAILNET_IP with discovered target values.
ssh -N -o ExitOnForwardFailure=yes \
  -L 127.0.0.1:33010:127.0.0.1:3010 SSH_LOGIN@SERVER_TAILNET_IP
```

Keep that terminal open and use `http://localhost:33010/create-admin` on that
same laptop. HTTP is confined to browser/SSH loopback endpoints; the remote leg
is encrypted by SSH. No certificate warning, client DNS modification or new
public listener is needed. Create the actual owner using their real email and
a password chosen directly in the UI. Do not paste credentials into a tunnel command.
The current host values discovered on 2026-11-01 are login `akshay`, server
`100.98.112.121`; the owner Mac had an existing private SSH session. Do not assume
those identities/IPs on a fresh machine.

This loopback URL is for initial account creation. Kutt production cookies are
Secure and its initial welcome response is not proof of a usable browser login;
do not weaken cookie settings or reset the new owner if the local page does not
stay signed in. After creation, the agent runs the normal `--accounts-ready`
command below to verify native owner credentials/admin access and enable public
HTTPS. Then the owner signs in at the real `https://kutt.DOMAIN` URL from their
public network and closes the tunnel (Ctrl-C). The administrator remains native
password-protected; public registration and owner creation stay restricted.

If forwarding fails, verify the existing SSH session, permitted tailnet port-22
policy, local port availability and server backend readiness. Do not expose the
unclaimed setup endpoint publicly as a workaround. This workflow is prepared;
real owner creation/public activation remain pending private inputs and owner UI
completion. The disposable smoke already verifies loopback first-owner creation
and subsequent explicit native login, not a real remote browser/tunnel session.

Once the owner has completed that UI step:

```sh
sudo scripts/kutt-proxy --apply --accounts-ready
sudo scripts/kutt status
# Only if authenticated ntfy and its optional host alert timer are already installed:
sudo scripts/ntfy install-alerts
sudo systemctl start ohara-alerts.service
```

Public mode currently permits the login and management UI/API from the Internet,
protected by native account authentication. Only first-owner creation is always
LAN-only. This is distinct from a LAN-only administration policy.

Public activation reads the single existing verified active admin email privately
from its own database, logs in through Kutt's native API using the supplied
password, and proves admin API access. The command prompts without echo in an
interactive terminal and never saves that password. Missing/ambiguous owners or failed login
leave the public guard in place. Status showing an account merely present is not
proof of completed login. Other applications/accounts are never imported.

`KUTT_PASSWORD` is deprecated as a persistent input. Existing private files may
retain it temporarily for backward-compatible verification; it is not required
by prepare/up or new owner creation. After verifying an existing installation,
remove that line manually from private .env. Removal does not change the account
or its password hash in PostgreSQL. Future public-activation/recovery checks
prompt privately again if needed. With no legacy value and no interactive TTY,
activation fails closed with instructions to run interactively; there is no
account-presence-only bypass. Never put the password in command arguments or chat.

Before calling the deployment ready, verify LAN HTTPS, public redirect behavior
from an actually external connection, native owner login, Homepage, local DNS and
an owner-approved test link. Change the target and confirm the short code remains
the same; generate a QR and scan it, then ban that test link deliberately. Never
ban/delete owner links as a diagnostic. Updating a target cannot recall a browser
that already followed the old redirect. Android ntfy delivery is a separate test.

The alerts installer discovers the running Kutt project: adds its local HTTP
health check, both expected containers (including PostgreSQL health), and the
local trusted HTTPS route/certificate. It preserves the storage watchdog and all
other checks. Kutt API health alone is shallow; DB container health and HTTPS
route checks add independent observations. The same host cannot detect its own
complete outage in real time. See [alerts](alerts.md).

## Persistence, upgrade and existing-state recovery

Repository YAML/scripts are templates; installed state lives at KUTT_ROOT,
`/etc/nginx/conf.d/ohara-kutt.conf` and the separately installed host alert config.
`up` and `stop` preserve link/account/statistics data. Git pull alone does not
apply a proxy or refresh the optional alert worker. Record deliberate real-host
Nginx deployments under `configs/nginx/deployed/`; a pending candidate is not a
verified deployed baseline. All exact host assumptions remain documented.

Keep private `.env`, DB state, secret files, release pins and the approved host
routing together for recovery. Never mount the same PostgreSQL directory into
two running servers or share Immich's directory. Do not point PostgreSQL to USB
media mounts. Separate projects do not provide separate physical fault tolerance.

For release upgrades, back up first, review upstream migrations, update pins in a
PR and rerun tests before explicit recreation. Kutt migrates at startup; an older
app image is not automatically compatible with a migrated schema. PostgreSQL
major upgrades require a reviewed dump/restore or pg_upgrade, never changing its
major tag over an existing data directory. No automatic password or JWT rotation
is implemented; input mismatch is refused for explicit recovery planning.

## Backup and rollback

```sh
sudo scripts/kutt backup
```

This creates root-private `/var/backups/ohara/kutt-TIMESTAMP` containing a consistent
SQL dump (including owner hashes and private destinations), the matching installed
DB/JWT inputs and image pins. Contents are never printed. The backup is on the
same machine and is not independent protection: choose an owner-approved encrypted
off-host destination and retention separately. Preserve `.env` privately too.
Live backup/restore is not claimed just because this helper exists.

For a fresh-target restore, first recreate the matching private inputs/config and
verified local storage with `prepare`, then start the empty project with the
matching pins. Keep onboarding-only proxy mode. Stop only Kutt, leaving its own
Postgres available. Restore a selected trusted SQL dump through psql stdin, then
restart Kutt and verify native login, a known redirect and its stable short code.
The dump uses DROP statements: restoring over existing Kutt data is destructive
and requires explicit owner authorization. Never restore into Immich or execute
an untrusted SQL dump. Example exact flow from the repository root, after that
authorization and target discovery:

```sh
sudo python3 - /var/backups/ohara/kutt-SELECTED/database.sql <<'PYCODE'
import sys
from pathlib import Path
root = Path.cwd()
sys.path.insert(0, str(root / 'scripts/lib'))
import config, kutt
c = config.load(root / '.env')
source = Path(sys.argv[1])  # choose the actual root-private trusted backup
if source.is_symlink() or not source.is_file():
    raise SystemExit('Select a regular trusted backup file')
kutt.compose(c, root, ['stop', 'kutt'])
# No secrets or SQL text appear in argv/output.
# Use the lifecycle module's validated interpolation and stdin support below.
# The helper supplies public paths/pins only; SQL stays on stdin.
kutt.restore_sql(c, root, source.read_text())
PYCODE
sudo scripts/kutt up
sudo scripts/kutt status
```

If restore fails, leave Kutt stopped and inspect privately; do not restart over a
partial schema. Restore the prior known-good backup/pins as an explicit recovery.
An app rollback that crossed schema migrations also requires restoring the
matching database snapshot. Preserve all source data/backups until verified.

For deployment rollback without deleting data, use `sudo scripts/kutt stop`,
restore/remove only the managed Nginx route from its selected proxy backup,
`sudo nginx -t && sudo systemctl reload nginx`, and selectively restore its prior
Homepage YAML/exact AdGuard rewrite. Rerun `sudo scripts/ntfy install-alerts` after
intentionally excluding the stopped optional project. Preserve databases,
credentials, other routes and services; never blanket-prune Docker resources.

## Verification and current rollout status

Required checks:

```sh
python3 -m unittest discover -s tests -v
tests/test_setup.sh
tests/test_cli.sh
tests/static.sh
python3 tests/smoke_kutt.py
tests/smoke.sh
```

The dedicated CI job prepares Kutt/Postgres/Nginx pins without deployment secrets.
The disposable smoke test uses a randomly named isolated project and fresh volume,
fixture accounts/inputs, and removes only its own resources. It verifies non-root
read-only startup, quoted DB input handling, restricted role/network superuser
password removal, owner/login boundary, disabled anonymous/signup flows, runtime
target edit, persistence after app recreation, SQL dump/restore into a fresh
disposable database, native QR UI/assets, ban without
record deletion, TLS/forwarded-header source restrictions, public transition and
no-store. It does not establish a real phone QR scan or fresh bare-metal setup.

As prepared on 2026-11-01: public DNS wildcard resolves the default host to the
current server, port 3010 is available, and the isolated feature smoke passed.
The owner requested a plain Utility link without a widget; it was selectively
merged into the live Homepage and verified through its authenticated services
API on 2026-11-01. Existing cards/widgets were preserved, with the prior YAML
backed up under ignored local/kutt-backups. The link does not establish Kutt
backend readiness. Private Kutt inputs have been requested; real startup/proxy
application, owner onboarding, live DNS/alerts, actual public reachability and QR
scanning remain pending until those inputs/onboarding are supplied and verified. No live
Kutt account or production secret has been generated. Keep this section aligned
with verified rollout rather than interpreting test fixtures as owner setup.

The default hostname was changed from go.DOMAIN to kutt.DOMAIN at the owner's
request before any production Kutt account/link existed. The private KUTT_HOST
setting and live Utility link were updated to kutt.xdadwal.in; its public DNS and
existing wildcard certificate coverage were verified. The Homepage helper can
selectively migrate the former go.DOMAIN link, preserving its other fields and
unrelated cards with a private YAML backup. Existing deployments with published
short links must retain their original hostname explicitly or plan a separate
domain/QR migration; changing a hostname does not update printed QR codes.
