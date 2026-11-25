# LAN-only service administration

The operator approved local HTTPS administration on 2026-10-22; Maintainerr
was added on 2026-10-23. These routes use existing host Nginx and the existing wildcard
certificate; no shared authentication service or public DNS record is added.

| URL | Loopback backend |
|---|---|
| https://adguard.xdadwal.in | 192.168.1.105:3000 (AdGuard on the owner's OpenWrt device since 2026-11-24; the bundled one used 127.0.0.1:3003) |
| https://radarr.xdadwal.in | 127.0.0.1:7878 |
| https://sonarr.xdadwal.in | 127.0.0.1:8989 |
| https://prowlarr.xdadwal.in | 127.0.0.1:9696 |
| https://qbittorrent.xdadwal.in | 127.0.0.1:8081 |
| https://lidarr.xdadwal.in | 127.0.0.1:8686 |
| https://bazarr.xdadwal.in | 127.0.0.1:6767 |
| https://maintainerr.xdadwal.in | 127.0.0.1:6246 |

Fresh AdGuard setup seeds these eight exact names under DOMAIN, pointing to
ADGUARD_BIND_IP (192.168.1.101 here). Existing installations retain their settings;
setup does not overwrite or automatically reconcile existing records. Preserve existing
rewrites, especially records the operator added; do not replace the entire list or
use a wildcard. On this host the records live in the owner's external AdGuard
([network.md](network.md)); the service scripts' rewrite steps reach it through
`DNS_IP`, and other names are added in its dashboard. Only clients querying AdGuard receive these local records. A
rewrite is not a web route or access control; Nginx enforces the latter separately.

The reviewed host-specific configuration is
`configs/nginx/deployed/ohara-lan.conf`. It permits 192.168.1.0/24 and loopback,
rejects all other source addresses on both HTTP and HTTPS, and redirects permitted
HTTP requests to HTTPS. It uses the connection source address, never a caller's
X-Forwarded-For/X-Real-IP headers. No real-IP trust is configured on this host.
If introducing another proxy later, review the client-address trust model first.
Other private networks, Tailscale and IPv6 LAN clients are not implicitly allowed.
Existing public portfolio/media/dashboard routes keep their current behavior.

Review the file and apply on **this existing xdadwal.in host only**:

```sh
scripts/lan-proxy
sudo scripts/lan-proxy --apply
```

The command requires root, verifies the host's address/certificate/main Nginx
configuration, backs up any previous LAN configuration under `/var/backups/ohara`,
installs only `ohara-lan.conf`, runs `nginx -t` and reloads. Validation/reload errors
restore the prior LAN file. It preserves unrelated sites, certificates, networking
and Docker bindings. Generic fresh-host setup does not install this baseline.

The Homepage template uses DOMAIN for the local links. Existing dashboards need a
selective merge into DATA_ROOT/homepage/services.yaml; preserve custom cards and
widget credentials. A plain link needs no API key and does not bypass app logins. Selected native
widgets use private internal Docker URLs and narrowly forwarded credentials; see
[Homepage widgets](homepage-widgets.md).

Verify from another LAN device using AdGuard: each name resolves to 192.168.1.101,
HTTPS has a trusted certificate, and the native service login works. Do not disable
native authentication or qBittorrent's host/CSRF protections. If qBittorrent rejects
the new host, add only this hostname to its existing allowlist rather than disable
validation. Confirm media/dashboard public routes separately. From outside the
allowed network, explicit connections to these virtual hosts must return 403 even
if someone supplies a matching Host/SNI or forged forwarding headers. This does
not require publishing their names in public DNS or forwarding additional ports.

Disposable check: `python3 tests/smoke_lan_proxy.py` runs both actual baseline
files against fixture backends/certificates, checks all eight LAN-only routes and the
LAN-only Seerr route, HTTP-to-HTTPS redirects, rejected sources and spoofed headers,
plus the six public routes. It does not certify a real LAN client's routing or public reachability.

For rollback, restore the previous LAN file (or move the newly introduced file
outside `/etc/nginx/conf.d`), then `sudo nginx -t` and reload Nginx. Keep Homepage
cards/DNS rewrites aligned manually. SSH tunnels to loopback backends remain
available. Never expose backend ports or DNS directly to the Internet.

## Seerr (LAN-only since 2026-11-18)

The owner restricted `https://seerr.xdadwal.in` to the same LAN sources because
Seerr stays on an image affected by an unauthenticated image-proxy flaw. Unlike
the eight admin hosts, its route lives in `configs/nginx/deployed/ohara.conf`
and reuses `$ohara_lan_allowed` from `ohara-lan.conf`; both files must be
installed. The `/imageproxy` denial is kept for LAN clients. The reusable
template for other hosts is unchanged and still public.

Remote users keep requesting through Jellyfin: Jellyfin Enhanced and the
Homepage widget reach Seerr server-side at `http://seerr:5055`, not through this
route. Direct browser links to the Seerr site only work on the LAN. LAN clients
need `seerr.DOMAIN` to resolve to the host's LAN address; this host's AdGuard
already returns 192.168.1.101 for it. Tailscale and IPv6 LAN clients are not
allowed, as with the admin hosts.

Apply on this host as root, from the repository root:

```sh
sudo install -d -m 700 /var/backups/ohara
backup=/var/backups/ohara/ohara.conf.$(date +%Y%m%d-%H%M%S)
sudo cp -p /etc/nginx/conf.d/ohara.conf "$backup"
sudo cmp configs/nginx/deployed/ohara-lan.conf /etc/nginx/conf.d/ohara-lan.conf
sudo install -m 644 -o root -g root configs/nginx/deployed/ohara.conf /etc/nginx/conf.d/ohara.conf
sudo nginx -t && sudo systemctl reload nginx
```

If `nginx -t` fails, restore before doing anything else:

```sh
sudo cp -p "$backup" /etc/nginx/conf.d/ohara.conf
sudo nginx -t && sudo systemctl reload nginx
```

Verify from a LAN device that the Seerr site loads and logs in; from a device on
mobile data that `https://seerr.xdadwal.in/` returns 403 and that a request made
inside Jellyfin still reaches Seerr; and on the host that
`cmp configs/nginx/deployed/ohara.conf /etc/nginx/conf.d/ohara.conf` is silent.
Disposable coverage is `python3 tests/smoke_lan_proxy.py`. To make Seerr public
again, restore the backup (or revert this change in the baseline and reinstall),
then test and reload; keep the `/imageproxy` denial while the image is unchanged.

Maintainerr has no native login; its entire UI/API is administrator access. The
LAN source restriction is required on every path, including database downloads.
See [maintainerr.md](maintainerr.md).

Bambuddy was promoted to public HTTPS on 2026-10-30 with the owner's explicit
approval. Its independent `ohara-bambuddy.conf` is managed by
`scripts/bambuddy-proxy`; initial onboarding is LAN-only until native owner login
is verified. The public route does not relax these eight admin hosts. Its exact
AdGuard rewrite stays so LAN clients use the same name. See [Bambuddy](bambuddy.md).
