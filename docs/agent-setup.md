# Agent-led initial setup

Use this workflow when the user asks you to prepare or deploy Ohara on the target
machine. Repository editing alone does not authorize live deployment. A shared
authentication service is deferred; keep independent service credentials.

For a new service addition, also follow [adding-services.md](adding-services.md).
Prepare independent host/proxy/dashboard/DNS work before owner signup where
possible; use LAN-only onboarding when the owner account is still unclaimed.
Do not assume sudo authentication in another terminal transfers to this session.

## Inspect before asking

Read AGENTS.md, docs/operations.md, .env.example, and any existing local
configuration. Inspect the authorized target's OS, architecture, CPU/RAM, network
interfaces, mounted disks, free space, user/group IDs, installed dependencies, and
port conflicts. Avoid exposing private configuration while inspecting it.

Reuse settled choices: Asia/Kolkata timezone; HOMEPAGE_HOST for Homepage (default apex, or
ohara.xdadwal.in with the separate apex portfolio profile);
seerr.xdadwal.in for Seerr, tv.xdadwal.in for playback, speed.xdadwal.in for
OpenSpeedTest, and immich.xdadwal.in for the future same-host Immich project.
Navidrome uses configurable NAVIDROME_HOST; music.xdadwal.in is the default; verify the hostname and public DNS before activation.
Public DNS is managed at GoDaddy. Do not ask the user to choose these again
unless the target's existing configuration conflicts with them.

Detect facts that the machine can establish. Do not ask the user to manually
write .env, install discoverable missing
dependencies, or provide user/group IDs you can inspect.

## Ask only for missing inputs

| Input | When user input is needed |
|---|---|
| Target access | No authorized target/session is available, or the operator must complete SSH/sudo authentication. Use the environment's secure authentication flow; do not request passwords in chat. |
| LAN address | Multiple candidate interfaces exist, the intended interface is unclear, or a stable router reservation/static address must be chosen. Never treat the example address as confirmed. |
| Storage | The dedicated file/data directories or disk selection are unknown. Present detected mounted disks and a suggested path; wait for the choice before creating storage on that disk. Do not format disks, migrate existing data, or change mounts without an explicit request. |
| ACME email | No actual certificate-contact email has been supplied. The example email is not a confirmed identity. This blocks certificate issuance, not independent local checks. |
| Application owner identity | Seerr, or later Immich, requires an owner email/name or an existing media account. Reuse supplied identity details; otherwise ask for the missing fields. Read the user-supplied password from the private credential file. |
| Media setup | The local stack includes Jellyfin and acquisition services. Confirm media mount/capacity and real owner email, then use scripts/media-setup. Ask for indexer/source choices and any external credentials; never invent them. |
| DNS/router access | Public DNS or forwarding cannot be inspected/configured through authorized tools. Give exact records/ports and request completion, then verify externally. Keep public activation pending until prerequisites work. |
| Immich storage/backups | When implementing Immich, confirm media/database paths, capacity, and backup destination. Inspect hardware where possible. Do not block the utility stack on a future Immich decision. |

Group closely related missing facts into a short question, offering detected
options and a recommendation when useful. Avoid an upfront questionnaire for
facts already available. Continue work that does not depend on an answer while
waiting. For required choices, wait rather than substituting guessed values.
Unattended execution must fail clearly with the missing fields/next action;
it must not hang waiting for terminal input or invent answers.

## Read user-managed credentials

Follow [credentials.md](credentials.md). The user must create and fill
.env, mode 0600.
Never invent or generate passwords, API keys or Homepage session secrets. If an
input file/key is missing or invalid, report its path/key and ask the user to
complete it privately; never ask for the value in chat. Do not copy test fixtures
or install filled example credentials. Inspect file validity without printing values.

For Homepage media widgets, request actual Jellyfin/Seerr API keys in
.env only after account setup. These optional inputs do not block
bootstrap; do not invent them or ask for values in chat. Weather uses browser
location permission; ask for a city/coordinates only if fixed weather is desired.
Explain container resource limits and verify sensors on Linux; see homepage-widgets.md.

Setup derives service configuration from those inputs and preserves existing
files. It does not rotate accounts. Use the supported first-run media APIs with
the supplied credentials and real owner email. Keep the setup journal. If existing
accounts reject credentials, stop for a deliberate recovery/rotation decision.
Verify login, ownership and expected permissions; reading a file is not proof an
account exists. Password hashing salts and application-issued session/integration
tokens remain normal application internals, not agent-chosen credentials.

## Public DNS and retired local DNS

GoDaddy manages public domain records. Verify the apex and service A records
resolve to the actual public IPv4 address before TLS activation. Router forwarding
still requires TCP 80/443 to Ohara. No local DNS server or DHCP change is needed
for this project. Do not change the host resolver or router/client DNS by inference.
If removing a previously deployed Pi-hole, follow the migration note in operations.md
and verify clients have a working replacement resolver before stopping it.

## Finish with verified outcomes

Run configuration checks, start the local stack only within the user's requested
scope, and verify each service. Complete required accounts before enabling public
application routes. Read and satisfy the --accounts-ready attestation; do not
set it solely because containers are running.

Report which accounts were created versus reused, private credential retrieval
paths, reachable URLs, pending integrations/user steps, and the exact verification
scope. Distinguish local success from public DNS/HTTPS and access from other devices.

## Media stack inputs and setup

Jellyfin, Navidrome, Radarr, Sonarr, Lidarr, Bazarr, Prowlarr and qBittorrent are included. Follow
[media.md](media.md). Inspect media mounts/capacity, RUN_UID/RUN_GID and existing
state first. Ask for the actual Seerr owner email if unknown, chosen indexers,
and any required external account/API credentials. Read passwords/API keys from the user-created private root `.env`. Never choose a source or create an external account by inference.
Run scripts/media-setup after scripts/up; then verify private logins, the
movie/TV/music download-client tests, Prowlarr application sync, Seerr default profiles/root
folders, Jellyfin libraries and external URL. Keep admin UIs private. Before
public activation, set Jellyfin Known Proxies to the actual host gateway and
check permissions with an ordinary viewing account. A healthy empty stack does
not prove request fulfillment: require a permitted movie/episode import and
HTTPS playback plus Seerr availability sync. Verify music imports through
Lidarr → shared music library → Navidrome scan/playback; Seerr does not request
music. Verify Navidrome admin login using supplied NAVIDROME_PASSWORD. Its supported
first-run API creates the account; existing accounts require successful login and
are never reset. Fresh Jellyfin setup seeds only Movies and TV Shows. Preserve
existing Jellyfin Music libraries; manually hide/remove only the library definition
if desired, without deleting files. Ask the operator
for subtitle languages, providers and any required provider credentials. Preserve
existing Bazarr configuration and manually verify Radarr/Sonarr connections, path
access, and subtitle writes. Keep Lidarr/Bazarr private on loopback 8686/6767; do
not create public admin subdomains. On existing installations, have the operator
append missing Lidarr/Bazarr credentials and NAVIDROME_PASSWORD to `.env` privately without
replacing existing values. Navidrome needs no additional API key.

The discussed NAS/multiple-node topology is future work. These services currently
run in this Compose stack; their intended future home is the acquisition node.
Do not add node orchestration, shared authentication or local DNS infrastructure.

On existing installations, use `scripts/media-setup --storage-only` to apply the
storage policy without logging into or initializing Jellyfin/Seerr owners. Run
host setup first to prepare recycle directories. See media.md for deletion
recovery and verification; cached availability and completed API jobs are not
proof of a playable file. Never remove a movie, its files, or setup journal as
an integration repair.

## Optional Tailscale

If remote SSH is requested, follow [tailscale.md](tailscale.md). Inspect existing
client/container roles, Linux SSH account/key readiness and tailnet policy first.
Ask only for missing account/device/SSH user choices; the owner completes browser
login privately. No generated credentials or new .env values are needed. Install
with scripts/tailscale only on an authorized host; verify remote key login and
SSH-only network grants independently of public service checks.
