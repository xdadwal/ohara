# Agent-led initial setup

Use this workflow when the user asks you to prepare or deploy Ohara on the target
machine. Repository editing alone does not authorize live deployment. A shared
authentication service is deferred; keep independent service credentials.

## Inspect before asking

Read AGENTS.md, docs/operations.md, .env.example, and any existing local
configuration. Inspect the authorized target's OS, architecture, CPU/RAM, network
interfaces, mounted disks, free space, user/group IDs, installed dependencies, and
port conflicts. Avoid exposing private configuration while inspecting it.

Reuse settled choices: Asia/Kolkata timezone, xdadwal.in for Homepage,
watch.xdadwal.in for Seerr, jellyfin.xdadwal.in for playback, files.xdadwal.in for Copyparty, speed.xdadwal.in for
OpenSpeedTest, and immich.xdadwal.in for the future same-host Immich project.
Pi-hole administration remains private. Do not ask the user to choose these again
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
local/credentials, local/homepage.env and local/media-credentials, mode 0600.
Never invent or generate passwords, API keys or Homepage session secrets. If an
input file/key is missing or invalid, report its path/key and ask the user to
complete it privately; never ask for the value in chat. Do not copy test fixtures
or install filled example credentials. Inspect file validity without printing values.

Setup derives service configuration from those inputs and preserves existing
files. It does not rotate accounts. Use the supported first-run media APIs with
the supplied credentials and real owner email. Keep the setup journal. If existing
accounts reject credentials, stop for a deliberate recovery/rotation decision.
Verify login, ownership and expected permissions; reading a file is not proof an
account exists. Password hashing salts and application-issued session/integration
tokens remain normal application internals, not agent-chosen credentials.

## Pi-hole configuration and LAN cutover

When tasked with initial Pi-hole setup, the agent can configure the service;
container startup and credential loading are only the first steps. Inspect
existing settings and preserve custom records, lists, and allow/block rules.
Use the installed version's supported UI/API/CLI and keep configuration consistent
with the Compose environment. The current upstream defaults are 1.1.1.1/1.0.0.1;
ask about alternate resolvers or custom filtering only when those choices matter.
Do not silently add aggressive third-party blocklists or replace existing lists.

If local resolution is needed, map the deployed Ohara hostnames to the confirmed
LAN IP and verify each record. Do not advertise Immich as available before its
separate project is deployed. Local records do not replace public provider DNS.
Test ordinary lookups over UDP and TCP and verify an expected blocked-domain
case against the configured lists before changing client DNS.

If router access is authorized and available, configure its DHCP DNS setting for
the reserved Pi-hole LAN address within the deployment task. Otherwise provide
the exact address/setting and identify this as a user step. Preserve a working
host resolver and fallback recovery path. Verify resolution from a second LAN
client after the change; a DNS query inside the container alone does not establish
that clients are using Pi-hole. Keep DNS and administration off public forwarding.

## Finish with verified outcomes

Run configuration checks, start the local stack only within the user's requested
scope, and verify each service. Complete required accounts before enabling public
application routes. Read and satisfy the --accounts-ready attestation; do not
set it solely because containers are running.

Report which accounts were created versus reused, private credential retrieval
paths, reachable URLs, pending integrations/user steps, and the exact verification
scope. Distinguish local success from public DNS/HTTPS and LAN-client verification.

## Media stack inputs and setup

Jellyfin, Radarr, Sonarr, Prowlarr and qBittorrent are now included. Follow
[media.md](media.md). Inspect media mounts/capacity, RUN_UID/RUN_GID and existing
state first. Ask for the actual Seerr owner email if unknown, chosen indexers,
and any required external account/API credentials. Read passwords/API keys from the user-created private input files. Never choose a source or create an external account by inference.
Run scripts/media-setup after scripts/up; then verify private logins, both
download-client tests, Prowlarr application sync, Seerr default profiles/root
folders, Jellyfin libraries and external URL. Keep admin UIs private. Before
public activation, set Jellyfin Known Proxies to the actual host gateway and
check permissions with an ordinary viewing account. A healthy empty stack does
not prove request fulfillment: require a permitted movie/episode import and
HTTPS playback plus Seerr availability sync.
