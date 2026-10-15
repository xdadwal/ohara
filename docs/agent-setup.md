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
watch.xdadwal.in for Seerr, files.xdadwal.in for Copyparty, speed.xdadwal.in for
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
| External media setup | Seerr needs a media-server endpoint/account and, for automated fulfillment, external acquisition services. Ask whether those exist when configuring Seerr; never invent endpoints or silently restore removed services. |
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
| Seerr | The current setup does not create its owner. Complete the supported first-run UI/API flow using the user's supplied identity/media account; generate any new local password securely. If interaction requires the user, explain the exact step and resume after completion. |
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

## Finish with verified outcomes

Run configuration checks, start the local stack only within the user's requested
scope, and verify each service. Complete required accounts before enabling public
application routes. Read and satisfy the --accounts-ready attestation; do not
set it solely because containers are running.

Report which accounts were created versus reused, private credential retrieval
paths, reachable URLs, pending integrations/user steps, and the exact verification
scope. Distinguish local success from public DNS/HTTPS and LAN-client verification.
