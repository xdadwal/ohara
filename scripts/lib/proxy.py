"""Managed Nginx bootstrap, explicit ACME activation, rollback-safe config updates."""
import fcntl
import os
import re
from pathlib import Path
import tempfile

from runtime import run

TARGET = Path('/etc/nginx/conf.d/ohara.conf')
RENEW_HOOK = '#!/bin/sh\n/usr/sbin/nginx -t && /usr/bin/systemctl reload nginx\n'


def render(c, root, https=False):
    text = (root / 'configs/nginx' / ('https.template' if https else 'http.template')).read_text()
    if https and int(c.get('PORTFOLIO_PORT', '0')):
        text += '\n' + (root / 'configs/nginx/portfolio.template').read_text()
    for key in ['DOMAIN', 'REQUESTS_HOST', 'FILES_HOST', 'SPEED_HOST', 'JELLYFIN_HOST', 'HOMEPAGE_HOST']:
        text = text.replace('@' + key + '@', c[key])
    text = text.replace('@HOSTS@', ' '.join(dict.fromkeys(c[k] for k in ['DOMAIN', 'REQUESTS_HOST', 'FILES_HOST', 'SPEED_HOST', 'JELLYFIN_HOST', 'HOMEPAGE_HOST'])))
    text = text.replace('@PORTFOLIO_PORT@', c.get('PORTFOLIO_PORT', '0'))
    # Keep header rules visible in rendered output for audits/tests.
    headers = (root / 'configs/nginx/proxy-headers.conf').read_text()
    return text.replace('include /etc/nginx/ohara-proxy-headers.conf;', headers)


def atomic_write(path, text, mode=0o644):
    descriptor, name = tempfile.mkstemp(prefix='.ohara-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w') as stream:
            stream.write(text)
        os.chmod(name, mode)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def apply_config(text, *, target=TARGET, runner=run):
    if target.is_symlink():
        raise ValueError('Managed Nginx target must not be a symlink')
    old = target.read_text() if target.exists() else None
    if old is not None and not old.startswith('# Managed by Ohara\n'):
        raise ValueError('Existing ohara.conf is not managed by Ohara; inspect manually')
    if old == text:
        runner(['nginx', '-t'])
        return
    atomic_write(target, text)
    reloading = False
    try:
        runner(['nginx', '-t'])
        reloading = True
        runner(['systemctl', 'reload', 'nginx'])
    except Exception:
        if old is None:
            target.unlink()
        else:
            atomic_write(target, old)
        if reloading:
            runner(['nginx', '-t'])
            runner(['systemctl', 'reload', 'nginx'])
        raise


def bootstrap(c, root):
    Path('/var/lib/ohara/acme').mkdir(parents=True, exist_ok=True, mode=0o755)
    if TARGET.exists() and '# HTTPS active:' in TARGET.read_text():
        run(['nginx', '-t'])
        print('Existing HTTPS configuration preserved. Use scripts/tls for deliberate domain changes.')
        return
    # Nginx must be running for a reload; empty managed config is valid on first start.
    run(['systemctl', 'start', 'nginx'], timeout=60)
    apply_config(render(c, root))


def configured_names(text):
    names = set()
    for group in re.findall(r'^\s*server_name\s+([^;]+);', text, re.MULTILINE):
        names.update(n for n in group.split() if n != '_')
    return names


def challenge_config(old, c):
    names = {c[k] for k in ['DOMAIN', 'REQUESTS_HOST', 'FILES_HOST', 'SPEED_HOST', 'JELLYFIN_HOST', 'HOMEPAGE_HOST']}
    missing = sorted(names - configured_names(old))
    if not missing:
        return old
    return old + ("\n# Temporary ACME routes for new names; existing HTTPS stays active.\n"
                  "server {\n    listen 80;\n    server_name " + ' '.join(missing) + ";\n"
                  "    location ^~ /.well-known/acme-challenge/ {\n"
                  "        root /var/lib/ohara/acme;\n        default_type text/plain;\n"
                  "        try_files $uri =404;\n    }\n"
                  "    location / { return 503; }\n}\n")


def activate(c, root, *, staging=False, accounts_ready=False, agree=False):
    if c['HOMEPAGE_HOST'] != c['DOMAIN']:
        raise ValueError('Use --dns-provider godaddy when a separate portfolio serves DOMAIN; existing routes must be preserved')
    if not agree:
        raise ValueError('Supply --agree-tos after reviewing the ACME subscriber agreement')
    if not staging and not accounts_ready:
        raise ValueError('Complete local owner/authentication setup, then supply --accounts-ready')
    if not TARGET.exists() or not TARGET.read_text().startswith('# Managed by Ohara\n'):
        raise ValueError('Run scripts/setup first to install the managed HTTP bootstrap')
    previous = TARGET.read_text()
    challenge = challenge_config(previous, c)
    # Retain old names in the certificate during cutover so restoring the previous
    # HTTPS config still serves a certificate covering its original names.
    names = sorted(configured_names(previous) | {c[k] for k in ['DOMAIN', 'REQUESTS_HOST', 'FILES_HOST', 'SPEED_HOST', 'JELLYFIN_HOST', 'HOMEPAGE_HOST']})
    args = ['certbot', 'certonly', '--webroot', '-w', '/var/lib/ohara/acme',
            '--non-interactive', '--agree-tos', '--email', c['ACME_EMAIL'],
            '--cert-name', 'ohara', '--keep-until-expiring', '--expand']
    for name in names:
        args.extend(['-d', name])
    if staging:
        # Staging certificates never replace production state or activate routes.
        args += ['--staging', '--config-dir', '/etc/letsencrypt-staging',
                 '--work-dir', '/var/lib/letsencrypt-staging', '--logs-dir', '/var/log/letsencrypt-staging']
        if challenge != previous:
            apply_config(challenge)
        try:
            run(args, timeout=300)
        finally:
            if challenge != previous:
                apply_config(previous)
        print('ACME staging succeeded. Production HTTPS remains unchanged.')
        return
    if challenge != previous:
        apply_config(challenge)
    try:
        run(args, timeout=300)
    except Exception:
        if challenge != previous:
            apply_config(previous)
        raise
    for name in ['fullchain.pem', 'privkey.pem']:
        if not (Path('/etc/letsencrypt/live/ohara') / name).is_file():
            if challenge != previous:
                apply_config(previous)
            raise ValueError('Production certificate files are missing; current Nginx configuration preserved')
    hook = Path('/etc/letsencrypt/renewal-hooks/deploy/ohara-nginx')
    hook.parent.mkdir(parents=True, exist_ok=True)
    if hook.exists() and hook.read_text() != RENEW_HOOK:
        raise ValueError('Existing renewal hook differs; inspect manually')
    atomic_write(hook, RENEW_HOOK, 0o755)
    apply_config(render(c, root, https=True))
    run(['systemctl', 'enable', '--now', 'certbot.timer'])
    run(['certbot', 'renew', '--cert-name', 'ohara', '--dry-run', '--run-deploy-hooks'], timeout=300)
    print('HTTPS routes activated; renewal dry run passed. Verify from an external network.')


def lock():
    stream = open('/run/lock/ohara-proxy.lock', 'a')
    try:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        stream.close()
        raise RuntimeError('Another Ohara host/proxy operation is running') from None
    return stream
