# AdGuard Home LAN DNS

AdGuard is optional and runs in the separate `ohara-dns` Compose project defined
by `compose.adguard.yaml`. Starting it does not restart the eleven application
containers. Public DNS stays at GoDaddy and host Nginx continues serving HTTPS.
There is no Unbound dependency. Router DHCP remains enabled; AdGuard DHCP is off.

## Configure and start

Reserve the server's real IPv4 address in router DHCP before relying on it for DNS.
Check TCP and UDP port 53 are free. Install the distribution `python3-bcrypt`
package if unavailable; it is used only to hash the operator-supplied initial
password. Add these literal entries privately to the single mode-0600 `.env`:

```dotenv
# Replace with the real LAN address and subnet, not an example on another host.
ADGUARD_BIND_IP=192.168.1.101
ADGUARD_NETWORK=192.168.1.0/24
# Add ADGUARD_PASSWORD with your independent chosen nonempty password,
# at most 72 UTF-8 bytes. Never paste it into chat or shell command arguments.
```

```sh
scripts/adguard check
scripts/adguard up
scripts/adguard status
```

Commands resolve their checkout directory themselves. `check` validates the
optional Compose model and LAN settings; it does not establish DNS availability.
`status` checks the authenticated API and the application's reported DNS state;
perform the direct DNS checks below separately. Normal `scripts/check`, `up`
and `status` continue managing the eleven applications, not this optional project.

The official digest-pinned image runs as RUN_UID/RUN_GID, without host networking,
Docker socket or privileged mode. Its executable carries file capabilities and
needs NET_BIND_SERVICE/NET_RAW in the bounding set even with internal port 1053;
all other capabilities are dropped and no-new-privileges is enabled.
Host port 53 TCP/UDP binds only ADGUARD_BIND_IP; the DNS client allowlist is
ADGUARD_NETWORK. No DHCP, DoH/DoT listener or public dashboard is published.

The dashboard backend binds `127.0.0.1:3003`. On this host, the approved
[LAN-only Nginx route](lan-services.md) provides `https://adguard.xdadwal.in`
without a tunnel once applied. SSH forwarding remains an alternative:

```sh
ssh -N -L 3003:127.0.0.1:3003 akshay@192.168.1.101
```

Open `http://localhost:3003`, username **admin**, using the supplied password.
Use the actual SSH username/address for another host.

Initial settings use Cloudflare DNS over HTTPS, with 1.1.1.1/1.0.0.1 only for
bootstrap name resolution and no plaintext fallback upstream. The AdGuard DNS
filter is enabled; Safe Search and parental controls are not imposed. Query logs
and statistics retain one day initially. Verify filter download success in the
dashboard. Review these privacy/provider choices there if desired.

Initial DNS rewrites cover DOMAIN, HOMEPAGE_HOST, REQUESTS_HOST, SPEED_HOST,
JELLYFIN_HOST and NAVIDROME_HOST, plus adguard, radarr, sonarr, prowlarr, qbittorrent,
lidarr, bazarr and immich subdomains of DOMAIN, all pointing to ADGUARD_BIND_IP. They do not
import the host's loopback entries, retired Pi-hole/files names, or a wildcard. On this
host those are xdadwal.in, ohara.xdadwal.in, seerr.xdadwal.in, speed.xdadwal.in,
tv.xdadwal.in and music.xdadwal.in, plus the seven administration names documented
in [LAN services](lan-services.md), and immich.xdadwal.in for photo onboarding.
The Immich rewrite was added to this existing host through the authenticated API,
preserving all prior rules; UDP and TCP queries return 192.168.1.101. The latter still require the separate LAN-only
Nginx configuration. Existing public services retain the same HTTPS names locally
and publicly; administration routes remain LAN-only.

## Verify and switch clients

From a **different LAN device**, with `dig` installed:

```sh
dig @192.168.1.101 tv.xdadwal.in A
dig +tcp @192.168.1.101 tv.xdadwal.in A
dig @192.168.1.101 tv.xdadwal.in AAAA
dig @192.168.1.101 example.org A
```

Expect the local IPv4 for A over both transports, no public IPv6 answer for the
rewritten name, and a successful external lookup. Verify all configured rewrites, filter
status, an allowed site and a blocked domain before cutover. Check trusted HTTPS
for the services from that client. A query made on the server itself is not proof
that another LAN device can reach it. Docker bridge/proxy source rewriting can
affect client allowlists; inspect query logs locally rather than opening access
to every source. Do not forward router TCP/UDP 53 to this server.

Once verified, set the router's **LAN DHCP DNS server** to the reserved server IP,
or pilot by setting DNS on one client. Router WAN DNS is a different setting.
Renew leases/reconnect devices. Avoid a public secondary DNS: clients can use it
and bypass filtering/local rewrites. IPv6 RDNSS/DHCPv6 and browser DoH/Android
Private DNS need separate client/router review so they do not silently bypass it.
No scripts modify router/client DNS, host resolv.conf/hosts, NetworkManager,
Tailscale settings, public records or Nginx. Router-specific steps require its
model and access. The server must stay on while clients depend on this resolver.

## Preserve, back up and roll back

State lives in DATA_ROOT/adguard/{conf,work}. Initial setup writes a private
AdGuardHome.yaml (JSON is valid YAML) with a bcrypt password hash, never plaintext.
AdGuard may rewrite it into YAML during operation. Subsequent `up` calls preserve
all existing accounts/settings/filter choices; changing `.env` alone does not
rotate the password or change existing rewrites. Use the dashboard for changes,
including Filters → DNS rewrites. Update the private `.env` after password changes.
An IP/subnet change also requires reviewing dashboard allowlists and rewrites.

Back up conf and work privately with the service stopped for a consistent copy;
include the private credential input in the existing encrypted backup procedure.
Do not commit configuration or query logs. For rollback, first restore the prior
DHCP/client DNS settings and renew leases, then `scripts/adguard stop`.
The command preserves all data. Do not stop a resolver clients still depend on.

References: [official Docker guidance](https://adguard-dns.io/kb/adguard-home/docker/)
and [configuration reference](https://adguard-dns.io/kb/adguard-home/configuration/).

The disposable DNS smoke test additionally needs `dig` (distribution package
`dnsutils`) and `python3-bcrypt` available to its Python interpreter. Run it alone
with `python3 tests/smoke_adguard.py`, or as part of `tests/smoke.sh`.

Homepage DNS statistics use the existing media network: AdGuard additionally joins
`ohara_default`, retaining its separate DNS network and all port bindings. On a
fresh host, start the main stack first so that shared network exists. Only the
selected dashboard credentials reach Homepage; AdGuard receives no media/Homepage
credentials in its environment. See [Homepage widgets](homepage-widgets.md).
