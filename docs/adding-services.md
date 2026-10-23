# Adding a service to Ohara

Use this workflow for future service additions. It records lessons from Immich's
implementation and deployment on 2026-10-22. The operator expects an authorized
service setup to include the server, hostname, Homepage card and local DNS, with
user-account creation handled at the appropriate onboarding stage. A code-only
request still does not authorize live deployment.

## Inspect and reuse settled choices

Read AGENTS.md, stack/operations documentation and the service's current upstream
installation, proxy and backup instructions. Inspect existing containers, ports,
mounted storage, hardware capacity, private-input validity, live Homepage,
Nginx routes/certificates and AdGuard rewrites. Keep secrets out of output.

Reuse verified facts and prior decisions. Detect paths, IDs, LAN address, DNS and
certificate coverage rather than asking the operator to supply them again.
Ask early only for genuinely missing inputs; continue independent preparation
while waiting. Do not keep repeating a request already answered or authorized.

## Deliver all integration points

For an authorized live addition, track these together:

- An independently operable service lifecycle, using a separate Compose project
  where its database, storage or upgrade lifecycle warrants it. Pin official
  release-matched images and retain required dependencies. Pair each independent
  `compose.SERVICE.yaml` project with `versions.SERVICE.env`; main-stack pins stay
  in `versions.env`. Overrides inherit their parent project's pins rather than
  creating a separate version source.
- Dedicated persistent storage with validation of the actual mounted filesystem,
  space and ownership. Keep database/originals separate from unrelated services;
  never recursively change existing ownership or remove data.
- Host Nginx HTTPS using a verified existing certificate when it covers the new
  hostname. Keep backend ports on loopback; preserve other routes and ACLs.
  Check upload limits, streaming timeouts, WebSockets, discovery endpoints and
  trusted forwarding headers against upstream requirements.
- A selective merge of the Homepage card into the live services.yaml, with a
  private backup and existing widgets/customizations preserved. Update the seed
  as well. A plain card needs no API key or shared Docker network. Verify the
  card through the authenticated Homepage response after reload/restart.
- An exact AdGuard rewrite to the verified LAN address when local access is
  requested or part of the service integration. Use its authenticated API,
  preserve existing rewrites, update initial seeds if appropriate, and test UDP
  and TCP DNS. Public DNS and AdGuard local DNS are separate responsibilities.
- Updated deployment baselines, operations/replication notes and an accurate
  account of what is live versus pending. Commit/push the feature work and
  update the existing PR for continuing work on that feature.

Do not stop after creating Compose files when startup and integration were
requested. Conversely, a healthy test instance is not the production instance.

## Credentials and administrator access

Use the single private `.env` and supported application APIs. Never generate,
invent or reuse service passwords by inference, source dotenv contents, pass the
whole file to containers, or reveal values in diagnostics. Validate only the
inputs needed by the target service; optional service credentials should not
block unrelated lifecycle commands.

When the operator explicitly accepts a value outside a repository preference,
check the actual application's constraints. Support a narrowly scoped, explicit
exception where technically valid; retain the normal default and reject empty
or unsupported values. Preserve the supplied value and existing account state.
Do not ask for approval again for the exception already authorized.

Test `sudo -n` before assuming privileged access. `sudo -v` in the operator's
terminal may not authenticate the agent's separate terminal/session; do not send
someone through repeated refreshes that cannot work. Prepare and test the exact
privileged command, then let the operator run it in their authenticated terminal
if needed. Use the environment's secure interactive authentication where
available. Never request a sudo password in chat or persist one in repository
files, memory notes, scripts, command history or logs. Do not bypass sudo through
Docker or change sudoers to avoid authentication.

## Complete setup before owner signup where possible

Do not block independent host, storage, proxy, Homepage and DNS work merely
because a first owner has not been created. If public onboarding would expose an
unclaimed administrator account, prepare a temporary LAN-only HTTPS mode using
the verified LAN and loopback source addresses. Enforce restrictions on HTTP and
HTTPS before redirects, and reject forged forwarding headers. Keep other sources
denied while the operator creates the owner through the intended hostname.

For Immich this is `scripts/immich-proxy --apply --onboarding-only`. Once owner
login is verified, `--apply --accounts-ready` enables public access. Never attest
to account readiness solely because containers are healthy or the initialized
flag is true. Do not invent owner details or create a test account in production.

## Verify and report each layer

Run the required repository checks and focused disposable runtime checks for the
changed behavior. Verify the real containers/API separately, then trusted HTTPS,
HTTP redirects, source restrictions, authenticated Homepage card and UDP/TCP DNS.
Verify existing routes still work. Track deliberate live Nginx changes exactly
under configs/nginx/deployed/.

Report local readiness, LAN access, public access, owner login, actual
upload/playback, backups and restore testing separately. LAN HTTPS is not proof
of Internet reachability. A ready onboarding page is not a completed account;
a successful database dump is not an independent backup or a proven restore.
Keep archive-readiness claims pending real backup/restore evidence.

End with what works, its URL, and only the specific remaining action. Avoid
calling the whole task complete while requested integration is still pending.
