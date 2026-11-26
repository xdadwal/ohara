# This host: home network and homelab architecture

State on 2026-11-24. This page describes the owner's actual network around the
Ohara server so another agent can understand, verify and rebuild it. It is
host-specific: addresses, device models and choices here must not be copied to
another target. The repository manages only the server; the ISP router and the
OpenWrt device are configured by the owner and recorded here.

## Topology

A rendered diagram of the same layout is in the [README](../README.md#network-of-the-xdadwalin-host); keep both in step when the layout changes.

```
Internet
   |
ISP router  192.168.1.1   gateway, NAT, DHCP server, port forwards 80/443
   |  Wi-Fi "ohara" (2.4 GHz ch 3, 5 GHz ch 157)
   |
   | cable to OpenWrt lan1
OpenWrt device  192.168.1.105   switch + Wi-Fi access point + LAN DNS
   |  Wi-Fi "ohara" (2.4 GHz ch 11, 5 GHz ch 40), bridged to the LAN
   |
   | cable from OpenWrt lan2
Ohara server  192.168.1.101   Docker applications, host Nginx, Tailscale
```

One flat network, 192.168.1.0/24. Everything behind the OpenWrt device, including
the server, reaches the Internet through it and then through the ISP router.

| Device | Address | Role | Managed by |
|---|---|---|---|
| ISP router | 192.168.1.1 | Gateway, NAT, the only DHCP server, forwards TCP 80/443 to the server, hands out itself as DNS and forwards lookups to 192.168.1.105 | Owner, router UI |
| OpenWrt device (JioRouter AX6000, OpenWrt 25.12.6) | 192.168.1.105, static | Bridge of lan1-lan4 and both radios; AdGuard Home and Unbound | Owner; key-only SSH as root |
| Ohara server (Debian 13) | 192.168.1.101, DHCP lease from the ISP router | All applications; see [stack](stack.md) | This repository |

Address reservations belong on the ISP router. The server's is relied on. The
OpenWrt address is set on the device and sits inside the ISP router's DHCP range;
reserving or excluding it there is an open owner task.

## DNS path

```
LAN device -> ISP router (192.168.1.1)
           -> AdGuard Home on OpenWrt (192.168.1.105:53, filtering, local rewrites)
           -> Unbound on OpenWrt (127.0.0.1:5335, recursive, DNSSEC validation, IPv4 only)
           -> authoritative servers
   fallback when Unbound does not answer: the owner's chosen plain resolver
   (163.53.87.74, set as fallback_dns in that AdGuard)
```

- AdGuard accepts only 192.168.1.0/24 clients. Its dashboard is
  `http://192.168.1.105:3000`, also proxied by the server's LAN-only route
  `https://adguard.DOMAIN` ([lan-services.md](lan-services.md)). Its login is
  the owner's; the server holds it only as `ADGUARD_PASSWORD` for the Homepage
  widget, which reads that dashboard directly.
- Seventeen exact rewrites to 192.168.1.101: the apex and `adguard`, `bambuddy`,
  `bazarr`, `immich`, `lidarr`, `maintainerr`, `music`, `ntfy`, `ohara`,
  `prowlarr`, `qbittorrent`, `radarr`, `seerr`, `sonarr`, `speed` and `tv` under
  the domain. They serve
  [LAN-only routes](lan-services.md) live in that AdGuard.
  The `kutt` rewrite was deleted on 2026-11-26 by owner request, after Kutt was
  retired.
- No third-party resolver answers lookups. Unbound has no forwarders and speaks
  plain DNS to the root, TLD and authoritative servers, so the ISP can read the
  names; `fallback_dns` (one plain resolver) is used only when Unbound fails, and
  `bootstrap_dns` is unused because no upstream is a hostname.
  AdGuard downloads its filter list from `adguardteam.github.io`. Browsing
  Security and Parental Control must stay off to keep this true: when on, AdGuard
  holds an HTTPS connection to AdGuard's own service (94.140.14.15:443) and
  sends it short hash prefixes of looked-up names. Browsing Security was found
  enabled on 2026-11-24 and the owner switched it off the same day; check with
  `grep -E 'safebrowsing_enabled|parental_enabled' /etc/adguardhome/adguardhome.yaml`.
- Connection tracking on the device shows only its own traffic, because bridged
  LAN traffic is not tracked: lookups arriving from the ISP router on port 53,
  AdGuard to Unbound on loopback 5335, Unbound to many authoritative servers on
  UDP/TCP 53, NTP, and SSH, dashboard and probe
  traffic from the server. Broadcasts from other LAN devices also appear.
- The server's only direct queries to 192.168.1.105 are the alert probe for
  `example.org` once a minute; its ordinary lookups go through the ISP router.
- Because the ISP router forwards for every device, AdGuard sees one client
  (192.168.1.1) and has no per-device statistics.
- The bundled AdGuard project on the server is stopped; see
  [adguard.md](adguard.md), "This host". The server's alert monitor probes the
  external one through `DNS_IP` in the private `.env`.

## Server

Unchanged by the network move and described in [stack](stack.md),
[deployment layout](deployment-layout.md) and [operations](operations.md):

- Host Nginx (Debian package, security floor in `scripts/lib/host.py`) is the only
  public listener, on TCP 80/443, with Certbot certificates. Every application
  backend binds to loopback. SSH is key-only on 22. There is no host firewall.
- Compose projects: `ohara` (eleven applications), `ohara-immich`,
  `ohara-ntfy`, `ohara-bambuddy`, `ohara-orcaslicer`, `ohara-maintainerr`, and the
  stopped `ohara-dns`.
- Media lives on the mergerfs pool at `/ohara/mnt` over an internal directory and
  two USB drives; see
  [storage pool](storage-pool.md). The storage watchdog stops media applications
  and Homepage when a branch disappears.
- Remote administration is ordinary SSH over the host Tailscale client; see
  [tailscale.md](tailscale.md).

## OpenWrt device setup

The device is set up with `configs/openwrt/setup.sh`, which holds the commands
first applied by hand on 2026-11-24. It runs on the device itself (BusyBox `ash`,
apk-based OpenWrt 25.12 or later), is fed over SSH from the repository, and every
phase can be repeated. It does not depend on a backup.

Prerequisites: OpenWrt already installed on the device (how this JioRouter AX6000
was flashed is not recorded), a root password set in its UI, and a free LAN
address outside the ISP router's DHCP range, reserved there.

1. **Network role.** A stock OpenWrt device uses 192.168.1.1 and runs DHCP, which
   clash with the ISP router. Connect a computer to the device alone, with no
   cable to the ISP router, and run:

   ```sh
   ssh root@192.168.1.1 'LAN_IP=192.168.1.105 GATEWAY=192.168.1.1 sh -s network' < configs/openwrt/setup.sh
   ```

   It sets the static address, gateway and DNS, turns off DHCP, DHCPv6 and router
   advertisements, and restarts the network; the session drops. Then cable the
   ISP router to a **LAN** port of the device (WAN stays empty) and the server to
   another LAN port.
2. **DNS services.** From the server:

   ```sh
   ssh root@192.168.1.105 'sh -s dns' < configs/openwrt/setup.sh
   ```

   It installs `adguardhome`, `unbound-daemon` and `unbound-control`; configures
   Unbound on loopback port 5335 only (IPv4 only, DNSSEC validation, query
   minimisation; `interface_auto=0`, so LAN devices cannot bypass AdGuard);
   removes `dnsmasq` and `odhcpd` to free port 53; points the device's own
   resolver at the ISP router; enables and starts both services; and checks that
   Unbound resolves. A failed package download is transient: run it again.
3. **Manual, in a browser** (owner-chosen secrets and values):
   - AdGuard wizard at `http://192.168.1.105:3000`: admin interface on all
     interfaces port 3000, DNS on 192.168.1.105 port 53, username `admin`, and a
     password the owner chooses. Put that password in the server's private `.env`
     as `ADGUARD_PASSWORD`.
   - AdGuard, Settings, DNS settings: upstream `127.0.0.1:5335`; fallback the
     owner's chosen plain resolver; allowed clients `192.168.1.0/24`; private
     reverse resolvers off. General settings: query log retention 24 hours.
   - AdGuard, Filters, DNS rewrites: the seventeen names listed under "DNS path",
     each answering 192.168.1.101. The server's service scripts add their own
     name when they run (`scripts/bambuddy`, `scripts/maintainerr`,
     `scripts/ntfy`), because `DNS_IP` points them at this dashboard.
   - OpenWrt UI, Network, Wireless: the same network name, WPA2 passphrase and
     security mode as the ISP router on both radios, on different channels (11
     and 40 here against the ISP router's 3 and 157). Then set the radio
     standards and country (2.4 GHz `HE20`, both radios `IN`):

     ```sh
     ssh root@192.168.1.105 'COUNTRY=IN sh -s wifi' < configs/openwrt/setup.sh
     ```

     The 5 GHz radio here uses `HE80`. Before 2026-11-24 the 2.4 GHz radio had no
     `htmode` and ran legacy 802.11g, and no country was set (world domain `00`).
   - OpenWrt UI, System, Administration, SSH-Keys: add the server account's public
     key and any owner device keys.
   - ISP router UI: forward DNS to 192.168.1.105 and reserve that address.
4. **Hardening**, only after a key login works:

   ```sh
   ssh root@192.168.1.105 'ZONENAME=Asia/Kolkata TIMEZONE=IST-5:30 sh -s harden' < configs/openwrt/setup.sh
   ```

   It refuses when no key is installed, turns off SSH password login and sets the
   timezone. The OpenWrt UI keeps accepting the root password.
5. **Server side:** set `DNS_IP=192.168.1.105` in `.env`, follow
   [adguard.md](adguard.md) "This host" to stop the bundled AdGuard once the
   router's queries have moved, then `sudo scripts/lan-proxy --apply`,
   `sudo scripts/ntfy install-alerts` and `scripts/up`.

The script keeps the first copy of each file it changes in `/root/ohara-backup/`
on the device. The stock firewall package stays loaded but filters nothing,
because all traffic is bridged inside its `lan` zone.

An OpenWrt configuration archive (`ssh root@192.168.1.105 'sysupgrade -b -'`) is
an optional convenience, not part of this procedure. One taken on 2026-11-24 is
in the ignored `local/` directory; it contains the Wi-Fi passphrase and account
hashes, so never commit, print or upload it.

## Verification

From the server:

```sh
ping -c 3 192.168.1.1                                   # gateway through the OpenWrt bridge
dig +short example.org @192.168.1.1                      # resolves through AdGuard and Unbound
dig +short doubleclick.net @192.168.1.1                  # 0.0.0.0 (filtered)
dig +short ohara.xdadwal.in @192.168.1.1                 # 192.168.1.101 (rewrite)
dig @192.168.1.105 dnssec-failed.org | grep status       # SERVFAIL (validation)
dig +tries=1 example.org @192.168.1.105 -p 5335          # connection refused (Unbound loopback-only)
ssh root@192.168.1.105 'iw reg get | sed -n 2p; grep -h ieee80211ax= /var/run/hostapd-phy*.conf'  # country IN; ax=1 twice
nmcli -t -f DHCP4.OPTION dev show | grep server_identifier   # 192.168.1.1
ssh root@192.168.1.105 'for s in adguardhome unbound; do /etc/init.d/$s status; done'
curl -s -o /dev/null -w '%{http_code}\n' https://xdadwal.in/     # 200
```

Verified on 2026-11-24: all of the above; AdGuard answering from the fallback
while Unbound was stopped; and a reboot of the OpenWrt device, after which the
network, both DNS services, key-only SSH and the clock returned unaided within
about one minute. Not verified: lookups from a separate LAN client, roaming
between the two access points, and reachability from outside the LAN.

## Known limits and open items

- Not replicable from this repository: the ISP router's settings, the first
  OpenWrt installation on the device, and every password. The AdGuard settings in
  step 3 of the setup are manual.
- The `network` phase of `configs/openwrt/setup.sh` has not been run end to end on
  a stock device; its validation, and the `dns` and `harden` phases, were run on
  the configured device.
- The OpenWrt device is a single point of failure for LAN DNS, its Wi-Fi and the
  server's Internet path. Its restart costs about one minute of outage.
- The ISP router exposes telnet, SSH and UPnP on the LAN; disabling them is an
  owner task in its UI.
- The OpenWrt UI is served over plain HTTP as well as HTTPS, without a redirect.
  (Unbound was open to the LAN on port 5335 until 2026-11-24; it is now
  loopback-only.)
- The network is flat: no guest or IoT separation, and no firewall between LAN
  devices and the server.
- The OpenWrt device has pending package updates and no automatic updates.
- The server-to-OpenWrt hop of `https://adguard.DOMAIN` is plain HTTP on the LAN.
- Storage on 2026-11-24: the two USB media drives disconnected and reappeared
  intermittently during the day, and the Crucial SSD once identified itself as a
  1 GB `SM2259AB` device. The pool was unmounted and the media applications and
  Homepage were stopped by the watchdog, which remounted the pool and restarted
  them at 15:58 IST once both drives stayed detected. The cause of the
  disconnects was not diagnosed; the WD adapter had re-enumerated about 42 times
  in five days. See [storage pool](storage-pool.md).

## Rollback

- DNS: on the server first remove `DNS_IP` from private `.env` and restore the
  bundled account's `ADGUARD_PASSWORD` (`scripts/adguard up` refuses to run while
  `DNS_IP` is set). Then run `scripts/adguard up`, verify with `scripts/adguard
  status`, set the ISP router's DNS back to 192.168.1.101, then reinstall alerts.
  [adguard.md](adguard.md#this-host-bundled-adguard-retired-for-an-external-one-2026-11-24)
  has the full rollback, including the LAN route and Homepage.
- OpenWrt as a router again: `apk add dnsmasq odhcpd-ipv6only`, restore the
  original `network` and `dhcp` files (`/root/backup-pre-ap/` on this device,
  `/root/ohara-backup/` after a scripted setup) into `/etc/config/`, and restart the
  network. Do this only with its LAN cable removed from the ISP router, because
  its stock address and DHCP server conflict with the ISP router's.
- Cabling: the server can be plugged straight into the ISP router at any time; its
  address and the port forwards do not change.
