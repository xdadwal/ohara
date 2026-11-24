# This host: home network and homelab architecture

State on 2026-11-24. This page describes the owner's actual network around the
Ohara server so another agent can understand, verify and rebuild it. It is
host-specific: addresses, device models and choices here must not be copied to
another target. The repository manages only the server; the ISP router and the
OpenWrt device are configured by the owner and recorded here.

## Topology

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
   fallback when Unbound does not answer: the owner's chosen resolver (private
   ADGUARD_PRIMARY_DNS in the server's .env records the same address)
```

- AdGuard accepts only 192.168.1.0/24 clients. Its dashboard is
  `http://192.168.1.105:3000`; the login stays with the owner.
- The eighteen `*.xdadwal.in` rewrites to 192.168.1.101 for
  [LAN-only routes](lan-services.md) live in that AdGuard.
- Because the ISP router forwards for every device, AdGuard sees one client
  (192.168.1.1) and has no per-device statistics.
- The bundled AdGuard project on the server is stopped; see
  [adguard.md](adguard.md), "This host". The server's alert monitor probes the
  external one through private `ADGUARD_EXTERNAL_IP`.

## Server

Unchanged by the network move and described in [stack](stack.md),
[deployment layout](deployment-layout.md) and [operations](operations.md):

- Host Nginx (Debian package, security floor in `scripts/lib/host.py`) is the only
  public listener, on TCP 80/443, with Certbot certificates. Every application
  backend binds to loopback. SSH is key-only on 22. There is no host firewall.
- Compose projects: `ohara` (eleven applications), `ohara-immich`, `ohara-kutt`,
  `ohara-ntfy`, `ohara-bambuddy`, `ohara-orcaslicer`, `ohara-maintainerr`, and the
  stopped `ohara-dns`.
- Media lives on the mergerfs pool at `/ohara/mnt` over two USB drives; see
  [storage pool](storage-pool.md). The storage watchdog stops media applications
  and Homepage when a branch disappears.
- Remote administration is ordinary SSH over the host Tailscale client; see
  [tailscale.md](tailscale.md).

## OpenWrt device configuration

Applied over SSH on 2026-11-24. Backups of the replaced files are on the device in
`/root/backup-pre-ap/` and beside `/etc/adguardhome/adguardhome.yaml`
(`.pre-migration`, `.pre-unbound`).

Access point role (no routing, no address management):

```sh
uci set network.lan.proto='static'
uci set network.lan.ipaddr='192.168.1.105'
uci set network.lan.netmask='255.255.255.0'
uci set network.lan.gateway='192.168.1.1'
uci add_list network.lan.dns='192.168.1.1'
uci set dhcp.lan.ignore='1'
uci set dhcp.lan.dhcpv4='disabled'
uci set dhcp.lan.dhcpv6='disabled'
uci set dhcp.lan.ra='disabled'
uci commit && /etc/init.d/network restart
apk del dnsmasq odhcpd-ipv6only      # after AdGuard and Unbound were verified
```

The ISP router cable is in lan1 and the WAN port is empty. The stock firewall
package is loaded but filters nothing, because all traffic is bridged inside its
`lan` zone.

DNS services:

```sh
apk update && apk add adguardhome unbound-daemon unbound-control
uci set unbound.ub_main.listen_port='5335'
uci set unbound.ub_main.protocol='ip4_only'
uci set unbound.ub_main.validator='1'
uci set unbound.ub_main.query_minimize='1'
uci set unbound.ub_main.add_local_fqdn='0'
uci set unbound.ub_main.unbound_control='1'
uci set unbound.ub_main.ttl_min='0'
uci commit unbound
/etc/init.d/unbound enable && /etc/init.d/unbound restart
/etc/init.d/adguardhome enable && /etc/init.d/adguardhome start
```

The owner completed AdGuard's first-run wizard at port 3000 (DNS on port 53,
dashboard kept on 3000 because the OpenWrt UI uses 80/443). Its
`/etc/adguardhome/adguardhome.yaml` was then edited with the service stopped:
`upstream_dns: [127.0.0.1:5335]`, `fallback_dns` set to the owner's resolver,
`allowed_clients: [192.168.1.0/24]`, the rewrites copied from the bundled AdGuard,
`querylog.interval: 1d`, and `hostsfile_enabled` and `use_private_ptr_resolvers`
off. With dnsmasq removed, the device resolves its own names through
`/tmp/resolv.conf -> /tmp/resolv.conf.d/resolv.conf.auto`, which
`/etc/init.d/boot` recreates at start.

Wi-Fi, set by the owner in the OpenWrt UI: the same name, WPA2 passphrase and
security mode as the ISP router so devices roam between the two, on different
channels. The passphrase is not recorded anywhere in this repository.

Administration:

```sh
uci set dropbear.main.PasswordAuth='off'
uci set dropbear.main.RootPasswordAuth='off'
uci commit dropbear && /etc/init.d/dropbear restart
uci set system.@system[0].zonename='Asia/Kolkata'
uci set system.@system[0].timezone='IST-5:30'
uci commit system && /etc/init.d/system reload
```

The only authorized SSH key is the server account's
(`/etc/dropbear/authorized_keys`); further keys are added in the OpenWrt UI under
System, Administration, SSH-Keys. The UI itself still accepts the root password.

## Verification

From the server:

```bash
ping -c 3 192.168.1.1                                   # gateway through the OpenWrt bridge
dig +short example.org @192.168.1.1                      # resolves through AdGuard and Unbound
dig +short doubleclick.net @192.168.1.1                  # 0.0.0.0 (filtered)
dig +short ohara.xdadwal.in @192.168.1.1                 # 192.168.1.101 (rewrite)
dig @192.168.1.105 dnssec-failed.org | grep status       # SERVFAIL (validation)
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

- The OpenWrt device is a single point of failure for LAN DNS, its Wi-Fi and the
  server's Internet path. Its restart costs about one minute of outage.
- The ISP router exposes telnet, SSH and UPnP on the LAN; disabling them is an
  owner task in its UI.
- Unbound answers any LAN device on port 5335, which bypasses filtering for a
  device that asks it directly. The OpenWrt UI is also served over plain HTTP.
- The network is flat: no guest or IoT separation, and no firewall between LAN
  devices and the server.
- The OpenWrt device has pending package updates and no automatic updates.
- Pending on the server, needs sudo: `sudo scripts/ntfy install-alerts`, and the
  `https://adguard.DOMAIN` LAN route, which still points at the stopped bundled
  dashboard.
- Storage on 2026-11-24: the two USB media drives disconnected and reappeared
  intermittently during the day, and the Crucial SSD once identified itself as a
  1 GB `SM2259AB` device. The pool was unmounted and the media applications and
  Homepage were stopped by the watchdog. Not diagnosed or repaired.

## Rollback

- DNS: on the server run `scripts/adguard up`, verify with `scripts/adguard
  status`, set the ISP router's DNS back to 192.168.1.101, then reinstall alerts.
- OpenWrt as a router again: `apk add dnsmasq odhcpd-ipv6only`, restore
  `/root/backup-pre-ap/network` and `dhcp` into `/etc/config/`, and restart the
  network. Do this only with its LAN cable removed from the ISP router, because
  its stock address and DHCP server conflict with the ISP router's.
- Cabling: the server can be plugged straight into the ISP router at any time; its
  address and the port forwards do not change.
