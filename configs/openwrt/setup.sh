#!/bin/sh
# Ohara: turn a stock OpenWrt router into a LAN access point that also runs
# AdGuard Home with a recursive Unbound. Runs ON the OpenWrt device (BusyBox ash).
#
# These are the commands applied by hand to the xdadwal.in owner's device on
# 2026-11-24, kept as a script so the setup does not depend on a backup.
# See docs/network.md for the order, prerequisites and the manual steps.
#
#   ssh root@DEVICE 'LAN_IP=192.168.1.105 GATEWAY=192.168.1.1 sh -s network' < configs/openwrt/setup.sh
#   ssh root@LAN_IP 'sh -s dns'    < configs/openwrt/setup.sh
#   ssh root@LAN_IP 'sh -s harden' < configs/openwrt/setup.sh
#   ssh root@LAN_IP 'COUNTRY=IN sh -s wifi' < configs/openwrt/setup.sh
#
# Every phase is safe to repeat. Nothing here sets a password, a Wi-Fi name or
# passphrase, an AdGuard account, rewrites or upstreams: those stay manual.
set -eu

phase=${1:-}
UNBOUND_PORT=5335
BACKUP=/root/ohara-backup

say() { echo "ohara-openwrt: $*"; }
die() { echo "ohara-openwrt: $*" >&2; exit 1; }

[ -f /etc/openwrt_release ] || die 'this script runs on the OpenWrt device, not on the server'
command -v uci >/dev/null || die 'uci is missing'
command -v apk >/dev/null || die 'this script supports apk-based OpenWrt releases (25.12 and later)'

keep() {
    # Keep the first copy of a file this script is about to change.
    mkdir -p "$BACKUP"
    [ -e "$BACKUP/$(basename "$1")" ] || cp -p "$1" "$BACKUP/" 2>/dev/null || true
}

ipv4() {
    echo "$1" | grep -Eq '^([0-9]{1,3}\.){3}[0-9]{1,3}$' || die "not an IPv4 address: $1"
}

network() {
    # Access point role: fixed LAN address, upstream router as gateway and DNS,
    # no DHCP and no IPv6 router advertisements on the shared LAN.
    : "${LAN_IP:?set LAN_IP to a free address outside the upstream router DHCP range}"
    : "${GATEWAY:?set GATEWAY to the upstream router address}"
    NETMASK=${NETMASK:-255.255.255.0}
    ipv4 "$LAN_IP"; ipv4 "$GATEWAY"; ipv4 "$NETMASK"
    [ "$LAN_IP" != "$GATEWAY" ] || die 'LAN_IP must differ from GATEWAY'
    keep /etc/config/network
    keep /etc/config/dhcp
    uci set network.lan.proto='static'
    uci set network.lan.ipaddr="$LAN_IP"
    uci set network.lan.netmask="$NETMASK"
    uci set network.lan.gateway="$GATEWAY"
    uci -q delete network.lan.dns || true
    uci add_list network.lan.dns="$GATEWAY"
    if uci -q get dhcp.lan >/dev/null; then
        uci set dhcp.lan.ignore='1'
        uci set dhcp.lan.dhcpv4='disabled'
        uci set dhcp.lan.dhcpv6='disabled'
        uci set dhcp.lan.ra='disabled'
        uci -q delete dhcp.lan.ndp || true
        uci commit dhcp
    fi
    uci commit network
    say "configured $LAN_IP via $GATEWAY; restarting the network in 2 seconds (this session will drop)"
    say "cable: upstream router to a LAN port of this device, WAN port empty; then continue at root@$LAN_IP"
    ( sleep 2
      [ -x /etc/init.d/odhcpd ] && /etc/init.d/odhcpd restart
      [ -x /etc/init.d/dnsmasq ] && /etc/init.d/dnsmasq restart
      /etc/init.d/network restart ) >/dev/null 2>&1 &
}

dns() {
    # Needs Internet access through the upstream router (run "network" first).
    ping -c 1 -W 3 downloads.openwrt.org >/dev/null 2>&1 || die 'no Internet/DNS from this device yet'
    apk update >/dev/null
    apk add adguardhome unbound-daemon unbound-control

    # Unbound: validating recursive resolver for AdGuard only. IPv4 only, because
    # an access point has no IPv6 route to the Internet. interface_auto=0 leaves
    # Unbound on its default loopback address, so LAN devices cannot query it
    # directly and skip AdGuard's filtering.
    keep /etc/config/unbound
    uci set unbound.ub_main.listen_port="$UNBOUND_PORT"
    uci set unbound.ub_main.interface_auto='0'
    uci set unbound.ub_main.protocol='ip4_only'
    uci set unbound.ub_main.validator='1'
    uci set unbound.ub_main.query_minimize='1'
    uci set unbound.ub_main.add_local_fqdn='0'
    uci set unbound.ub_main.unbound_control='1'
    uci set unbound.ub_main.ttl_min='0'
    uci commit unbound
    /etc/init.d/unbound enable
    /etc/init.d/unbound restart

    # Free port 53 for AdGuard: this device hands out no addresses, so the stock
    # DHCP/DNS services are not needed.
    for service in dnsmasq odhcpd; do
        [ -x "/etc/init.d/$service" ] || continue
        /etc/init.d/$service stop || true
        /etc/init.d/$service disable || true
    done
    keep /etc/config/dhcp
    apk del dnsmasq odhcpd-ipv6only 2>/dev/null || apk del dnsmasq odhcpd 2>/dev/null || true
    # Without dnsmasq the device resolves its own names through the upstream router.
    ln -sf /tmp/resolv.conf.d/resolv.conf.auto /tmp/resolv.conf

    /etc/init.d/adguardhome enable
    /etc/init.d/adguardhome start || /etc/init.d/adguardhome restart
    sleep 5
    nslookup -port="$UNBOUND_PORT" openwrt.org 127.0.0.1 >/dev/null 2>&1 || die 'Unbound does not resolve; inspect logread'
    address=$(uci -q get network.lan.ipaddr | cut -d/ -f1)
    say "Unbound answers on 127.0.0.1:$UNBOUND_PORT"
    if [ -s /etc/adguardhome/adguardhome.yaml ]; then
        say "AdGuard Home is already configured; dashboard http://$address:3000"
    else
        say "finish AdGuard Home in a browser: http://$address:3000 (see docs/network.md for the values)"
    fi
}

harden() {
    # Key-only SSH, and only when a key is already installed.
    [ -s /etc/dropbear/authorized_keys ] || die 'add an SSH key first (System, Administration, SSH-Keys); refusing to lock out root'
    keep /etc/config/dropbear
    uci set dropbear.main.PasswordAuth='off'
    uci set dropbear.main.RootPasswordAuth='off'
    uci commit dropbear
    /etc/init.d/dropbear restart
    if [ -n "${ZONENAME:-}" ] && [ -n "${TIMEZONE:-}" ]; then
        uci set system.@system[0].zonename="$ZONENAME"
        uci set system.@system[0].timezone="$TIMEZONE"
        uci commit system
        /etc/init.d/system reload
    fi
    say 'SSH accepts keys only; verify a new key login before closing this session'
}

wifi_phase() {
    # Radio standards and regulatory country only. The network name, passphrase,
    # encryption and channels stay manual in the OpenWrt UI.
    : "${COUNTRY:?set COUNTRY to the two-letter country code, for example IN}"
    echo "$COUNTRY" | grep -Eq '^[A-Z]{2}$' || die "not a two-letter country code: $COUNTRY"
    keep /etc/config/wireless
    radios=$(uci show wireless | sed -n "s/^wireless\.\([^.=]*\)=wifi-device$/\1/p")
    [ -n "$radios" ] || die 'no wifi-device sections in /etc/config/wireless'
    for radio in $radios; do
        uci set "wireless.$radio.country=$COUNTRY"
        # Without htmode a 2.4 GHz radio runs legacy 802.11g (54 Mbit/s at most).
        if [ "$(uci -q get "wireless.$radio.band")" = '2g' ]; then
            uci set "wireless.$radio.htmode=HE20"
        fi
    done
    uci commit wireless
    /sbin/wifi reload </dev/null >/dev/null 2>&1
    say "radios set to country $COUNTRY, 2.4 GHz HE20; Wi-Fi clients reconnect within seconds"
}

case "$phase" in
    network) network ;;
    dns) dns ;;
    harden) harden ;;
    wifi) wifi_phase ;;
    *) die 'usage: sh -s network|dns|harden|wifi  (see the header of this script)' ;;
esac
