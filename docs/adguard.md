# AdGuard Home LAN DNS

> **This host (xdadwal.in) since 2026-11-24:** the bundled project described
> below is stopped. LAN DNS is an owner-run AdGuard Home with Unbound on a
> separate OpenWrt device. Read ["This host"](#this-host-bundled-adguard-retired-for-an-external-one-2026-11-24)
> and [network.md](network.md) before using any command on this page here. The
> rest of this page remains the procedure for a fresh or other target.

AdGuard is optional and runs in the separate `ohara-dns` Compose project defined
by `compose/adguard.yaml`. Starting it does not restart the eleven application
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

The only upstream is Cloudflare DNS over HTTPS
(`https://dns.cloudflare.com/dns-query`), with 1.1.1.1/1.0.0.1 used only for
bootstrap resolution of that hostname, no fallback and no plaintext upstream. A
fresh setup writes this policy into the initial configuration. An existing
installation keeps its own settings on `up`; apply the policy to a running
resolver, without restarting DNS, with:

```sh
scripts/adguard upstreams
scripts/adguard status
```

The command reads the private ADGUARD_PASSWORD, uses the loopback API and tests
the resulting lists first, changing nothing if any entry fails. It sets
`upstream_dns`, `fallback_dns` and `bootstrap_dns` exactly and prints what it
replaced, so upstreams added by hand in the dashboard are removed; accounts,
rewrites, filters and other DNS settings are preserved. A second run reports no
change. Verify afterwards with UDP and TCP queries to ADGUARD_BIND_IP, a local
rewrite, a blocked name and DNSSEC failure handling. A different upstream is an
owner choice made in the dashboard, which this command would replace. The AdGuard DNS
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

AdGuard is active LAN DNS. Its default stop command refuses an outage. Do not stop
it as part of an unrelated update batch. First deploy and verify a fallback
resolver, obtain owner approval for the interruption window, announce it to LAN
users, and stop only AdGuard with:

```sh
scripts/adguard stop --allow-dns-outage
```

Before resuming updates, restore immediately with `scripts/adguard up`, then verify
UDP/TCP queries from a separate LAN client. Back up conf and work privately with
the service stopped during that approved window for a consistent copy;
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

AdGuard image pins live independently in `versions/adguard.env`, paired with
`compose/adguard.yaml`; the main stack no longer carries the optional DNS pin.
See [deployment layout](deployment-layout.md).

## This host: bundled AdGuard retired for an external one (2026-11-24)

By owner decision the bundled project is **stopped** on this host. LAN DNS is
served by an AdGuard Home the owner runs on a separate OpenWrt device at
192.168.1.105 (AdGuard on port 53, dashboard on port 3000, Unbound on port 5335
as its upstream, the owner's chosen plain resolver as fallback). That device is
not managed by this repository; its login stays with the owner.
Its configuration and the whole topology are recorded in [network.md](network.md).

- Stop, only after the router forwards to the other resolver and the bundled
  query log shows no router queries: `scripts/adguard stop --allow-dns-outage`.
  `restart: unless-stopped` keeps it stopped across reboots. Its configuration and
  data stay in `DATA_ROOT/adguard`.
- Record the other resolver in private `.env` as `DNS_IP` (a private
  LAN IPv4 of another device). It is used only by the alert DNS probe while the
  bundled project is not running; reinstall alerts afterwards with
  `sudo scripts/ntfy install-alerts`, which also drops the bundled container and
  dashboard checks. The device itself is set up with `configs/openwrt/setup.sh`;
  see [network.md](network.md).
- Settings were copied once by editing the other AdGuard's configuration while it
  was stopped: rewrites, client allowlist, query-log retention and the
  private-PTR/hosts-file switches. Blocklists and rules already matched. Query
  history was not moved. Later changes must be made on that device.
- Homepage: the widget URL is the variable `HOMEPAGE_VAR_ADGUARD_URL`, which
  `compose/stack.yaml` sets to `http://DNS_IP:3000` when `DNS_IP` is set and to
  the bundled `http://adguard:3000` otherwise; the template and the installed
  `DATA_ROOT/homepage/services.yaml` both use it. `scripts/up` recreates only
  Homepage after a change. Test a changed `ADGUARD_PASSWORD` once with
  `scripts/adguard status` before reloading Homepage: the device blocks an
  address for 15 minutes after five failed logins, and the server's address is
  also the one its LAN route uses.
- LAN route: `configs/nginx/deployed/ohara-lan.conf` proxies
  `https://adguard.DOMAIN` to `http://192.168.1.105:3000`, keeping the wildcard
  certificate and the LAN-only source rule. Apply with
  `sudo scripts/lan-proxy --apply`. The hop from the server to that device is
  plain HTTP on the LAN. To roll back, restore `proxy_pass http://127.0.0.1:3003;`
  and apply again.
- Resolution on that device is AdGuard to Unbound (recursive, DNSSEC-validating,
  plain DNS to authoritative servers), with the owner's plain resolver as
  `fallback_dns`. No Cloudflare or Quad9 resolver is in the path, and
  `scripts/adguard upstreams` has no effect on it. The ISP can see lookups; no resolver company does.
- With `DNS_IP` set, `scripts/adguard status` and the rewrite steps of
  `scripts/bambuddy`, `scripts/maintainerr` and `scripts/ntfy` use
  the external dashboard (`http://DNS_IP:3000`) with username `admin` and
  `ADGUARD_PASSWORD`, which is now that device's login. `scripts/adguard up` and
  `upstreams` refuse to run, because they would restart the bundled project or
  replace the Unbound upstream with the bundled policy. Other rewrites and
  filters are changed in the dashboard; verify with `dig NAME @192.168.1.1`. The
  bundled account's previous password is in the ignored
  `local/env.20261124-pre-key-cleanup`.
- Rollback: `scripts/adguard up`, verify with `scripts/adguard status`, point the
  router's DNS back to `ADGUARD_BIND_IP`, restore `proxy_pass http://127.0.0.1:3003;`
  in the LAN route and apply it, remove `DNS_IP` and set `ADGUARD_PASSWORD` back,
  run `scripts/up`, then reinstall alerts. Rewrites or filters added
  on the external device since the cutover must be copied back by hand.

