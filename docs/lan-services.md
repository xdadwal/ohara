# LAN-only service administration

The operator approved local HTTPS access to the seven administration services on
2026-10-22. These routes use existing host Nginx and the existing wildcard
certificate; no shared authentication service or public DNS record is added.

| URL | Loopback backend |
|---|---|
| https://adguard.xdadwal.in | 127.0.0.1:3003 |
| https://radarr.xdadwal.in | 127.0.0.1:7878 |
| https://sonarr.xdadwal.in | 127.0.0.1:8989 |
| https://prowlarr.xdadwal.in | 127.0.0.1:9696 |
| https://qbittorrent.xdadwal.in | 127.0.0.1:8081 |
| https://lidarr.xdadwal.in | 127.0.0.1:8686 |
| https://bazarr.xdadwal.in | 127.0.0.1:6767 |

AdGuard DNS rewrites map these exact names to 192.168.1.101. Preserve existing
rewrites, especially records the operator added; do not replace the entire list or
use a wildcard. Only clients querying AdGuard receive these local records. A
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
widget credentials. A plain link needs no API key and does not bypass app logins.

Verify from another LAN device using AdGuard: each name resolves to 192.168.1.101,
HTTPS has a trusted certificate, and the native service login works. Do not disable
native authentication or qBittorrent's host/CSRF protections. If qBittorrent rejects
the new host, add only this hostname to its existing allowlist rather than disable
validation. Confirm media/dashboard public routes separately. From outside the
allowed network, explicit connections to these virtual hosts must return 403 even
if someone supplies a matching Host/SNI or forged forwarding headers. This does
not require publishing their names in public DNS or forwarding additional ports.

Disposable check: `python3 tests/smoke_lan_proxy.py` runs both actual baseline
files against fixture backends/certificates, checks all seven routes, HTTP-to-HTTPS
redirects, rejected sources and spoofed headers, plus all six existing public
routes. It does not certify a real LAN client's routing or public reachability.

For rollback, restore the previous LAN file (or move the newly introduced file
outside `/etc/nginx/conf.d`), then `sudo nginx -t` and reload Nginx. Keep Homepage
cards/DNS rewrites aligned manually. SSH tunnels to loopback backends remain
available. Never expose backend ports or DNS directly to the Internet.
