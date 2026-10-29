# Bambuddy for the A1 mini

Optional independent project `ohara-bambuddy`, using official `1.2.5.7` pinned by
multi-architecture digest in `versions.bambuddy.env`. The owner's A1 mini is in
LAN-only mode and was confirmed connected through manual IP/bridge networking.

## Storage and startup

The owner selected internal ext4 storage, `/ohara/bambuddy` on this host.
`data/` holds SQLite, archives and application-managed keys; `logs/` is separate.
State is private (0700), UID/GID match Ohara, and existing files/ownership are
preserved. No data was moved into mergerfs or Immich. New hosts must confirm
storage; optional overrides belong in the private `.env`:

```dotenv
BAMBUDDY_ROOT=/ohara/bambuddy
BAMBUDDY_MOUNT=/
```

```sh
scripts/bambuddy check --static
scripts/bambuddy prepare
scripts/bambuddy up
scripts/bambuddy status
```

The helper rejects symlinks, overlapping paths, missing/wrong mounts and network
or FUSE storage. Docker never auto-creates bind sources. The default assumes
internal storage; external storage needs mount-dependent boot ordering reviewed
before activation. Only `127.0.0.1:8008` is published, forwarding to container 8000.

The official image runs non-root with no-new-privileges and capabilities dropped
except the Python binary's NET_BIND_SERVICE bounding requirement. No unrelated
host files, devices or Docker/Tailscale sockets are mounted. The application
creates normal internal keys in persistent state; the helper creates no account,
password, API key or session secret. Host setup supplies `python3-yaml` for the
selective Homepage integration; CI declares PyYAML explicitly.

## Proxy trust and public access

The owner approved Internet access with native password login and explicitly
without adding MFA. Public DNS already aliases `bambuddy.xdadwal.in` to the apex,
which resolves to this host's public IPv4. The existing wildcard certificate and
router 80/443 forwarding are reused. No additional ports are forwarded; actual
printer MQTT/FTPS/camera ports stay private.

At startup the helper inspects its owned Compose bridge and derives only its
verified private IPv4 host gateway. If absent, it creates only that project bridge
with Compose ownership labels. It rejects an unrelated network or public gateway.
The derived value supplies both `TRUSTED_PROXY_IPS` and `FORWARDED_ALLOW_IPS`;
ambient environment values are not accepted and no wildcard proxy trust is used.
Static rendering uses a loopback placeholder and does not require Docker network
access. Run `scripts/bambuddy up` after network/configuration changes so containers
are recreated with the current gateway; `docker compose restart` alone does not
apply changed environment variables.

Nginx discards incoming forwarding chains and supplies the actual client IP, so
native per-user/per-IP login limits work behind the proxy. The dedicated
`ohara-bambuddy.conf` supports WebSockets, unbuffered streams, 24-hour stream
timeouts and a 1 GiB upload ceiling. It is independent of the eight LAN-only
admin routes, which retain their guards on both HTTP and HTTPS.

### Fresh owner onboarding

Use LAN-only mode before the first owner exists:

```sh
sudo scripts/bambuddy-proxy --apply --onboarding-only
scripts/bambuddy homepage
scripts/bambuddy dns
```

The proxy installer is deliberately specific to the existing xdadwal.in host,
verified LAN address and wildcard certificate. It preserves unrelated sites and
migrates only the old Bambuddy block out of the managed LAN file. Both route files
are privately backed up, atomically written, validated and reloaded together;
errors restore both previous files. Unexpected other edits are rejected for review.
The default rendered route is LAN-only; public mode requires explicit selection.

Open https://bambuddy.xdadwal.in from an allowed LAN client, enable native
authentication and create the owner privately. Verify owner login, then promote:

```sh
sudo scripts/bambuddy-proxy --apply --accounts-ready
```

This flag attests owner-login verification. The installer also independently
refuses public activation if the API reports setup pending or auth disabled.
It does not require or alter MFA. Native authentication must stay enabled while
the route is public. Roll back to LAN-only mode with `--onboarding-only`, without
removing accounts/data or changing other admin routes.

Homepage adds one 3D Print card without forwarding credentials, preserving
existing cards/widgets. DNS adds only the exact AdGuard rewrite to the verified
LAN address, rejecting conflicts and preserving other records. Keep that rewrite
for same-name LAN access; do not change router/client DNS. Fresh seeds include
both integrations. The public DNS alias needs no update for LAN clients.

## Printer setup

1. Add the **A1 mini** by its real reserved LAN IP, serial number and access code,
   entered only in the authenticated UI. Do not send credentials in chat.
2. Full local control requires the appropriate LAN-only/Developer Mode for its
   firmware. The owner confirmed LAN-only mode; do not alter cloud/printer modes
   by inference or promise full cloud and local-control compatibility.
3. Verify connected status and camera where supported. The diagnostic bridge
   warning is automatic for discovery/Virtual Printer features; it does not mean
   a working manual-IP connection is broken. No host networking, Virtual Printer
   listeners or server-side slicer sidecars are enabled by this setup.
4. For archive metadata, verify a microSD card and the current upstream A1-family
   file-on-card workflow. Missing printer-side files can leave thumbnails or
   filament metadata unavailable. Printing, heating/motion and automation are
   separate owner actions; deployment does not test them.

## Verification and recovery

```sh
scripts/bambuddy check
scripts/bambuddy status
python3 tests/smoke_bambuddy.py
python3 tests/smoke_lan_proxy.py
scripts/bambuddy stop
```

Disposable tests cover the pinned image's non-root readiness, SQLite/state
preservation after recreation, exact proxy trust and spoof rejection, unclaimed
owner blocking, both access modes and rollback of both route files. They create
no production account, printer or print job. Real checks confirmed internal ext4,
private state, loopback backend, trusted HTTPS, HTTP redirect, authenticated
Homepage card and AdGuard UDP/TCP rewrite. Native auth is enabled; the owner
confirmed the printer is connected. No account/password/MFA settings were changed
when promoting public access.

On promotion, public-IP HTTPS returned 200 and unauthenticated printer API calls
returned 401. All other eight admin hosts still returned 403 from disallowed
sources, including forged headers. The owner subsequently confirmed access from a public network. Local and public
access use the same Bambuddy application and account permissions; there is no
separate remote/read-only mode. LAN DNS points to the private address, while public
DNS points to the WAN address. Camera and actual printing remain separately
unverified by deployment.

Stop Bambuddy before copying its entire state (including SQLite, keys and
archives), or use its supported in-app backup. A local backup is not an
independent backup or proven restore. No external backup destination/restore test
is implemented. To retire the service, stop it and deliberately remove only its
proxy/card/rewrite, preserving data. Do not delete state to repair a connection.

References: [release](https://github.com/maziggy/bambuddy/releases/tag/v1.2.5.7),
[release Compose](https://github.com/maziggy/bambuddy/blob/v1.2.5.7/docker-compose.yml),
[proxy-aware login limiter](https://github.com/maziggy/bambuddy/blob/v1.2.5.7/backend/app/api/routes/auth.py).
