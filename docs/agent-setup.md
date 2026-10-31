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
OpenSpeedTest, and immich.xdadwal.in for the optional same-host Immich project.
Navidrome uses configurable NAVIDROME_HOST; music.xdadwal.in is the default; verify the hostname and public DNS before activation.
Public DNS is managed at GoDaddy. Do not ask the user to choose these again
unless the target's existing configuration conflicts with them.

Detect facts that the machine can establish. Populate non-secret deployment
settings from verified facts and install authorized missing dependencies rather
than asking the user to repeat discoverable details. The user still supplies all
passwords, API keys and session secrets privately as described below.

## Ask only for missing inputs

| Input | When user input is needed |
|---|---|
| Target access | No authorized target/session is available, or the operator must complete SSH/sudo authentication. Use the environment's secure authentication flow; do not request passwords in chat. |
| LAN address | Multiple candidate interfaces exist, the intended interface is unclear, or a stable router reservation/static address must be chosen. Never treat the example address as confirmed. |
| Storage | The dedicated file/data directories or disk selection are unknown. Present detected mounted disks and a suggested path; wait for the choice before creating storage on that disk. Do not format disks, migrate existing data, or change mounts without an explicit request. |
| ACME email | No actual certificate-contact email has been supplied. The example email is not a confirmed identity. This blocks certificate issuance, not independent local checks. |
| Application owner identity | A selected application requires an owner email/name or existing media account. Reuse supplied identity details; otherwise ask for missing fields. Follow the application's supported onboarding; never reuse its database password as an owner password. |
| Media setup | The local stack includes Jellyfin and acquisition services. Confirm media mount/capacity and real owner email, then use scripts/media-setup. Ask for indexer/source choices and any external credentials; never invent them. |
| DNS/router access | Public DNS or forwarding cannot be inspected/configured through authorized tools. Give exact records/ports and request completion, then verify externally. Keep public activation pending until prerequisites work. |
| Immich storage/backups | For a selected Immich deployment, confirm storage/capacity and the owner's backup policy. On this host the owner accepted current single-user capacity and explicitly deferred independent backups/restore testing; preserve that decision without treating it as a release blocker or claiming backups exist. |

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

## Public DNS, local DNS and LAN administration

GoDaddy manages public domain records. Verify the apex and service A records
resolve to the actual public IPv4 address before TLS activation. Router forwarding
still requires TCP 80/443 to Ohara. Optional AdGuard Home provides approved LAN
DNS/filtering through its separate project; follow [adguard.md](adguard.md).
Inspect and preserve existing accounts, allowlists and exact rewrites. Test UDP
and TCP DNS from a separate LAN client before any separately authorized DHCP
cutover. Do not change the host resolver or router/client DNS by inference.
If removing a previously deployed Pi-hole, follow the migration note in operations.md
and verify clients have a working replacement resolver before stopping it.

Follow [lan-services.md](lan-services.md) for the approved private HTTPS admin
routes. Keep backend ports loopback-only and enforce LAN restrictions on every
HTTP/HTTPS path; a local DNS rewrite alone is not access control. Test the same
public hostname against local and public DNS separately when diagnosing access.
Browser Secure DNS, VPNs, guest networks and router hairpin routing can produce
different results; obtain an affected client's URL/error rather than declaring
all client access healthy from server-local checks.

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
Do not add node orchestration, shared authentication or unapproved infrastructure;
the optional AdGuard deployment above is explicitly approved.

For the approved optional Jellyfin theme/plugin workflow, follow
[jellyfin-theme.md](jellyfin-theme.md) and [jellyfin-enhanced.md](jellyfin-enhanced.md)
after media account setup. Install the reviewed Enhanced plugin, then explicitly
run `scripts/jellyfin-theme install` and `scripts/jellyfin-enhanced setup`.
The synced profile includes automatic next-season requests and Seerr user import;
review these on a new target. Preserve other user preferences and configure
Intro Skipper detection separately; setup does not launch library analysis.
For approved LetterboxdSync, follow [jellyfin-letterboxd.md](jellyfin-letterboxd.md):
verify the reviewed artifact, restart only with playback idle, and leave external
account linking in its HTTPS UI. Preserve existing accounts and integrations.

On existing installations, use `scripts/media-setup --storage-only` to apply the
storage policy without logging into or initializing Jellyfin/Seerr owners. Run
host setup first to prepare recycle directories. See media.md for deletion
recovery and verification; cached availability and completed API jobs are not
proof of a playable file. Never remove a movie, its files, or setup journal as
an integration repair.

## Optional media-pool recovery and HDD standby

When the owner authorizes a mergerfs pool with watchdog recovery/HDD standby,
complete [storage-pool.md](storage-pool.md) after the approved disk mounts and
guarded `ohara-media.service` are in place. Ordinary `scripts/setup` does not
configure disks or enable the watchdog. Preserve existing host settings; do not
format, move data, or modify mounts without authorization.

Discover the real filesystem UUIDs with `lsblk -f` and `/dev/disk/by-uuid`, verify
their mountpoints against `/etc/fstab`, and identify the actual rotational HDD's
ATA serial using `udevadm info` or a supported identification query. Use those
facts to create ignored `local/storage-watchdog.json` with the schema in
`configs/storage/watchdog.example.json`. The example contains xdadwal.in host
identities, not portable defaults. Never guess identities, substitute unstable
`/dev/sdX` letters, or apply the HDD setting to an SSD. Ask only if the intended
disk selection cannot be inferred from the approved pool. The current worker
supports `/ohara/mnt`, external ext4 branches under `/mnt/disks/`, and one HDD;
do not silently adapt an incompatible topology.

Install the distribution `hdparm` package and the verified host configuration:

```sh
sudo apt-get install --no-install-recommends hdparm
sudo scripts/storage-watchdog install --config local/storage-watchdog.json
sudo cmp local/storage-watchdog.json /etc/ohara/storage-watchdog.json
systemctl is-enabled ohara-storage-watchdog.timer
systemctl list-timers ohara-storage-watchdog.timer
sudo journalctl -u ohara-storage-watchdog.service -n 30 --no-pager
```

The installer normalizes JSON formatting; if `cmp` differs, compare parsed JSON
objects privately to verify the values match. The installed worker reads
`/etc/ohara/storage-watchdog.json`, not the example or editable local input.
Preserve existing installed configuration; differing contents require deliberate
backup/reconciliation rather than replacement. Explain the 30-second checks,
60-second settling period, five-minute backoff and three-attempt hourly limit.
Stop the timer and worker before planned storage maintenance.

Verify the timer runs, the intended HDD accepts its standby timeout, and healthy
services remain running. An absent disk should leave consumers stopped until
both expected disks return. Do not unplug an in-use disk or force standby merely
to demonstrate recovery; use mocked tests and observe real reconnects when
available. Distinguish command acceptance from an observed idle spindown/wake,
and distinguish a configured recovery policy from a verified live recovery.

## Optional Tailscale

If remote SSH is requested, follow [tailscale.md](tailscale.md). Inspect existing
client/container roles, Linux SSH account/key readiness and tailnet policy first.
Ask only for missing account/device/SSH user choices; the owner completes browser
login privately. No generated credentials or new .env values are needed. Install
with scripts/tailscale only on an authorized host; verify remote key login and
SSH-only network grants independently of public service checks.

Optional Maintainerr is approved for media administration: follow
[maintainerr.md](maintainerr.md) after main media startup. Complete the independent
service, Homepage and AdGuard integration and LAN-only proxy. No native account
onboarding exists; no cleanup rules are seeded without an owner retention policy.

## Optional Immich and Bambuddy

Use [immich.md](immich.md) and `scripts/immich` for the independent Immich project,
database/cache and stable `/data` path. Keep machine learning disabled. Follow
[immich-google-oauth.md](immich-google-oauth.md) for the approved Google-only,
invite-only policy: `autoRegister=false`, password login disabled, approved users
pre-created by exact Google email with empty password fields and no forced
password change. Read actual OAuth client inputs only from private `.env`; never
put them in the versioned JSON or Homepage. Preserve existing owner accounts.
On a new target, complete owner onboarding and verify actual Google sign-in
before attesting readiness. The current host's Google sign-in is owner-verified;
independent backups/restore testing remain explicitly deferred.

For Bambuddy, follow [bambuddy.md](bambuddy.md) and `scripts/bambuddy`. Complete
LAN-only first-owner onboarding before using `scripts/bambuddy-proxy` to activate
the owner-approved public route with native password login and no added MFA.
Keep its backend loopback-only and use bridge networking with the real manual
printer IP. Printer codes and owner signup stay in its UI; never start a print
or enable virtual-printer/slicer sidecars as part of setup.

## Optional laptop lid-close policy

For a laptop intended to remain a server with its lid shut, inspect the current
logind configuration, desktop idle policy and inhibitors first. This host's
approved policy ignores lid-close events on battery, AC and while docked; do not
silently impose that policy on an unrelated laptop. To reproduce it deliberately:

```sh
sudo install -D -m 644 configs/logind/90-ohara-lid.conf /etc/systemd/logind.conf.d/90-ohara-lid.conf
sudo systemctl reload systemd-logind
systemd-analyze cat-config systemd/logind.conf
```

Verify runtime `HandleLidSwitch`, `HandleLidSwitchExternalPower` and
`HandleLidSwitchDocked` properties through `org.freedesktop.login1`. Report a
physical lid-close/network test separately; setting these values does not
disable desktop idle suspension or low-battery actions. Preserve other power
settings, and do not globally mask sleep targets.

## Setup completion and persistence checklist

The main setup installs host dependencies (including bpytop), prepares storage
and seeds missing files. It does not deploy every optional project or replace
existing service configuration. For each authorized optional component, follow
its helper and linked operations guide, merge its live Homepage card/widget and
exact AdGuard rewrite where applicable, and verify its source restrictions.
Check that systemd units/timers and mount-dependent startup are enabled for the
selected topology; do not assume a container's restart policy supplies storage
ordering. Verify TLS renewal timer/configuration independently; certificate
existence alone is not a successful unattended renewal test. Preserve the current
manual-renewal caveat until a real renewal dry run succeeds.

For every selected component, report separately: static/disposable tests, live
service health, LAN client access, independent public access, owner onboarding,
application functionality and reboot persistence. Do not reboot a live server
merely to complete this checklist; obtain a maintenance window if one is needed.
Record explicit owner deferrals and the exact remaining actions.

## Optional ntfy notifications

Follow [ntfy.md](ntfy.md) and `scripts/ntfy` for the independently pinned server,
local storage outside the media pool, native deny-by-default topic authentication,
HTTPS, Homepage and exact AdGuard rewrite. The owner supplies NTFY_PASSWORD in
private .env. Ask whether the phone is Android or iPhone; enable the ntfy.sh iOS
wake-up relay only with explicit approval. No notification text is forwarded to
that relay. Verify the real supplied account before public proxy activation.
Install the host alert timer with `sudo scripts/ntfy install-alerts` after server
readiness; it reads the actual configured storage UUIDs and preserves the existing
storage watchdog. Run `scripts/ntfy test` and obtain owner confirmation of phone
delivery. Local publish success is not phone delivery or independent outage
detection; same-host monitoring cannot report a complete host/network outage.
Keep credentials out of Homepage, command arguments and logs.

For optional ntfy event monitoring and Seerr new-request notifications, follow
[host and application alerts](alerts.md). Reinstall the host worker after alert
changes and configure Seerr separately; preserve private inputs and alert state.
