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
write .env, supply randomly generated passwords, install discoverable missing
dependencies, or provide user/group IDs you can inspect.

## Ask only for missing inputs

| Input | When user input is needed |
|---|---|
| Target access | No authorized target/session is available, or the operator must complete SSH/sudo authentication. Use the environment's secure authentication flow; do not request passwords in chat. |
| LAN address | Multiple candidate interfaces exist, the intended interface is unclear, or a stable router reservation/static address must be chosen. Never treat the example address as confirmed. |
| Storage | The dedicated file/data directories or disk selection are unknown. Present detected mounted disks and a suggested path; wait for the choice before creating storage on that disk. Do not format disks, migrate existing data, or change mounts without an explicit request. |
| ACME email | No actual certificate-contact email has been supplied. The example email is not a confirmed identity. This blocks certificate issuance, not independent local checks. |
| Application owner identity | Seerr, or later Immich, requires an owner email/name or an existing media account. Reuse supplied identity details; otherwise ask for the missing fields. Generate a new password locally when creating a local account. |
| Media setup | The local stack includes Jellyfin and acquisition services. Confirm media mount/capacity and real owner email, then use scripts/media-setup. Ask for indexer/source choices and any external credentials; never invent them. |
| DNS/router access | Public DNS or forwarding cannot be inspected/configured through authorized tools. Give exact records/ports and request completion, then verify externally. Keep public activation pending until prerequisites work. |
| Immich storage/backups | When implementing Immich, confirm media/database paths, capacity, and backup destination. Inspect hardware where possible. Do not block the utility stack on a future Immich decision. |

Group closely related missing facts into a short question, offering detected
options and a recommendation when useful. Avoid an upfront questionnaire for
facts already available. Continue work that does not depend on an answer while
waiting. For required choices, wait rather than substituting guessed values.
Unattended execution must fail clearly with the missing fields/next action;
it must not hang waiting for terminal input or invent answers.

## Generate and preserve credentials

Use a cryptographically secure generator and unique values per service. Use the
existing setup generator where supported; do not reset or rotate an existing
account merely because the agent does not know its password.

| Service | Current automation and agent responsibility |
|---|---|
| Homepage | Setup generates its password and session secret in local/homepage.env. |
| Copyparty | Setup generates its admin password in local/credentials and writes a salted password hash to local/copyparty.conf. |
| Pi-hole | Setup generates its admin password in local/credentials and supplies it through local/pihole.env. |
| Jellyfin and Seerr | scripts/media-setup creates the Jellyfin admin and Seerr owner through supported APIs using generated credentials and the supplied owner email. See media.md for connections, indexers and playback acceptance. |
| Immich | Not implemented yet. Include account/bootstrap support in its own deployment work; do not claim its credentials or owner already exist. |
| OpenSpeedTest | Has no application account; no credential needs generating. |

Keep generated credentials in private local files with restrictive permissions,
excluded from Git. For any newly automated account flow, document its private
credential-file path. Never put passwords in CLI arguments, ordinary logs, PR
text, or chat; report the retrieval path instead. Tell the user when a service
uses an existing account rather than a newly generated password.

Credential generation is not proof that an account exists. Verify the actual
login, ownership, and expected permissions. Preserve existing .env values and
configuration edits on reruns. Request a deliberate recovery/rotation decision
when existing credentials are missing or fail, rather than silently replacing them.

## Pi-hole configuration and LAN cutover

When tasked with initial Pi-hole setup, the agent can configure the service;
container startup and password generation are only the first steps. Inspect
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
and any required external account/API credentials. Generate local passwords
automatically. Never choose a source or create an external account by inference.
Run scripts/media-setup after scripts/up; then verify private logins, both
download-client tests, Prowlarr application sync, Seerr default profiles/root
folders, Jellyfin libraries and external URL. Keep admin UIs private. Before
public activation, set Jellyfin Known Proxies to the actual host gateway and
check permissions with an ordinary viewing account. A healthy empty stack does
not prove request fulfillment: require a permitted movie/episode import and
HTTPS playback plus Seerr availability sync.
