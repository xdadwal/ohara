# Stable xdadwal.in Nginx baseline

These non-secret files track `/etc/nginx/conf.d/` on the xdadwal.in server after
the authorized music/subtitles deployment on 2026-10-17. The Jellyfin hostname
cutover to `tv.xdadwal.in` and Navidrome activation have been applied. They contain
public routes and certificate paths, never private keys or application credentials.
Bambuddy was promoted from LAN-only to public native-auth HTTPS on 2026-10-30;
other LAN routes retain their existing restrictions.

- `ohara.conf`: wildcard HTTPS, portfolio apex, Homepage at ohara.xdadwal.in,
  Seerr/Jellyfin/OpenSpeedTest/Navidrome, IPv4/IPv6, localhost redirects and local TLS.
  Jellyfin is at tv.xdadwal.in; Navidrome is at music.xdadwal.in. The dedicated
  music HTTP redirect and HTTPS route suppress URL-bearing access/error logs.
- `ohara-immich.conf`: separate public photo HTTPS route, promoted from LAN-only
  onboarding on 2026-10-22 after the operator confirmed owner setup and the API
  reported initialized/onboarded. Uses the existing wildcard certificate and
  loopback 2283, with large uploads, WebSockets and mobile discovery routing.
  The previous LAN-only route is backed up privately under /var/backups/ohara.
- `ohara-public-ip-test.conf`: HTTP-only reachability probe for 45.120.160.21.
  It returns a fixed message and exposes no application data.
- `ohara-bambuddy.conf`: public Bambuddy HTTPS and HTTP redirect, with native
  owner authentication. Use `scripts/bambuddy-proxy --apply --onboarding-only`
  for fresh LAN-only signup, then `--accounts-ready` after owner login. The helper
  migrates the legacy Bambuddy LAN block and validates/reloads both files with
  rollback. Other LAN hosts retain their source guards.
- `ohara-lan.conf`: separately approved on 2026-10-22; eight LAN-only administration
  HTTPS routes with source-address restrictions and loopback backends. Apply with
  `sudo scripts/lan-proxy --apply` after review; see [LAN services](../../../docs/lan-services.md).

The generic `../http.template`, `../https.template`, `../portfolio.template` and
`../proxy-headers.conf` remain the fresh-host rendering sources. Their shared
IPv6 listeners and Jellyfin policy match this deployment. This baseline also
captures host-specific additions; generic setup does not install these files
automatically or assume another host owns this IP/domain or has local CA keys.

Compare against the running host without changing anything:

```sh
cmp configs/nginx/deployed/ohara.conf /etc/nginx/conf.d/ohara.conf
cmp configs/nginx/deployed/ohara-public-ip-test.conf /etc/nginx/conf.d/ohara-public-ip-test.conf
```

To apply this reference configuration, restore/issue the wildcard certificate at
`/etc/letsencrypt/live/ohara-wildcard/{fullchain,privkey}.pem` and restore the local
certificate/key at `/etc/ohara/tls/server.{crt,key}` privately first. Also prepare
the documented loopback services and `/var/lib/ohara/acme`. Review these public
names and the IP probe for the target machine before installing either file.
Back up existing Nginx configuration, test the candidate with `nginx -t`, and
reload only after validation. Do not overwrite unrelated sites or replace a
working certificate. DNS renewal remains a separate operation.

This stable baseline intentionally keeps Jellyfin's currently deployed defaults:
300-second proxy read timeout, default response buffering/body-size limit and
inherited access logging. Disabling token-bearing URL logs or changing streaming
timeouts should be a separate deliberate change to both the live configuration
and the repository, followed by playback verification.

`files.xdadwal.in` appears only in the old HTTP ACME/redirect host list; there is
no HTTPS file service. Localhost redirects to the apex portfolio. Keep these
details when comparing/restoring this baseline, rather than inferring new routes.
