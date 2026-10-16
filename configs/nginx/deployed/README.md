# Stable xdadwal.in Nginx baseline

These two non-secret files are exact copies of `/etc/nginx/conf.d/` on the
xdadwal.in server, captured on 2026-10-16 at the owner's request. They contain
public routes and certificate paths, never private keys or application credentials.

- `ohara.conf`: wildcard HTTPS, portfolio apex, Homepage at ohara.xdadwal.in,
  Seerr/Jellyfin/OpenSpeedTest, IPv4/IPv6, localhost redirects and local TLS.
- `ohara-public-ip-test.conf`: HTTP-only reachability probe for 45.120.160.21.
  It returns a fixed message and exposes no application data.

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

To reproduce this exact deployment, restore/issue the wildcard certificate at
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
