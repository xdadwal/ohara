"""Explicit DNS certificate setup, preserving live routes during renewal migration."""
import json
from pathlib import Path
import re

import dns_godaddy
import proxy
from runtime import run

HOOK = Path('/usr/local/lib/ohara/dns_godaddy.py')
CERT_NAME = 'ohara-wildcard'
CERT_DIR = Path('/etc/letsencrypt/live') / CERT_NAME


def installed_paths(staging=False):
    return ((HOOK.with_name('dns_godaddy_staging.py'), dns_godaddy.CREDENTIALS.with_name('dns-godaddy-staging.json'))
            if staging else (HOOK, dns_godaddy.CREDENTIALS))


def install(root, data, staging=False):
    hook, credential = installed_paths(staging)
    for directory in (hook.parent, credential.parent):
        if directory.is_symlink():
            raise ValueError('Installed DNS directory must not be a symlink')
        directory.mkdir(parents=True, exist_ok=True)
        if directory.stat().st_uid != 0 or directory.stat().st_mode & 0o022:
            raise ValueError('Installed DNS directory must be root-owned and not writable by others')
    # Installed copies survive checkout moves; tokens never enter command args.
    for path in (hook, credential):
        if path.is_symlink():
            raise ValueError('Installed DNS file must not be a symlink')
    source = (root / 'scripts/lib/dns_godaddy.py').read_text()
    if staging:
        source = source.replace(str(dns_godaddy.CREDENTIALS), str(credential))
        source = source.replace(str(dns_godaddy.STATE), str(dns_godaddy.STATE) + '-staging')
    proxy.atomic_write(hook, source, 0o700)
    proxy.atomic_write(credential, json.dumps(data), 0o600)


def options(staging=False):
    hook, _ = installed_paths(staging)
    return ['--authenticator', 'manual', '--preferred-challenges', 'dns',
            '--manual-auth-hook', '/usr/bin/python3 ' + str(hook) + ' auth',
            '--manual-cleanup-hook', '/usr/bin/python3 ' + str(hook) + ' cleanup',
            '--non-interactive']


def nginx_config(old, c, root):
    # Preserve existing private/admin ACLs and localhost certificates. A fresh
    # HTTP bootstrap uses the normal public application template.
    if 'ssl_certificate ' not in old:
        return proxy.render(c, root, https=True).replace('/live/ohara/', '/live/' + CERT_NAME + '/')
    changed = set()
    def update(match):
        block = match.group(0)
        names = re.search(r'^\s*server_name\s+([^;]+);', block, re.M)
        if not names or 'ssl_certificate ' not in block:
            return block
        hosts = names.group(1).split()
        if all(n == c['DOMAIN'] or (n.endswith('.' + c['DOMAIN'])
                                   and n.count('.') == c['DOMAIN'].count('.') + 1) for n in hosts):
            changed.update(hosts)
            block = re.sub(r'(?m)^(\s*ssl_certificate)\s+[^;]+;',
                           r'\1 ' + str(CERT_DIR / 'fullchain.pem') + ';', block)
            block = re.sub(r'(?m)^(\s*ssl_certificate_key)\s+[^;]+;',
                           r'\1 ' + str(CERT_DIR / 'privkey.pem') + ';', block)
        return block
    result = re.sub(r'(?ms)^server \{\n.*?^\}', update, old)
    required = {c[k] for k in ('DOMAIN', 'REQUESTS_HOST', 'FILES_HOST', 'SPEED_HOST', 'JELLYFIN_HOST')}
    if not required <= changed:
        raise ValueError('Existing HTTPS routes are missing configured names; inspect before DNS activation')
    return result


def activate(c, root, credential_path, *, staging=False, renewal_only=False,
             accounts_ready=False, agree=False):
    if not agree:
        raise ValueError('Supply --agree-tos after reviewing the ACME subscriber agreement')
    if not staging and not renewal_only and not accounts_ready:
        raise ValueError('Complete local owner setup, then supply --accounts-ready')
    data = dns_godaddy.credentials(credential_path)
    if data['domain'] != c['DOMAIN']:
        raise ValueError('DNS credential zone must match DOMAIN')
    for key in ('REQUESTS_HOST', 'FILES_HOST', 'SPEED_HOST', 'JELLYFIN_HOST'):
        name = c[key]
        if not name.endswith('.' + c['DOMAIN']) or name.count('.') != c['DOMAIN'].count('.') + 1:
            raise ValueError('Wildcard DNS mode requires direct subdomains of DOMAIN')
    # Read-only API preflight before installing credentials or touching Certbot.
    dns_godaddy.GoDaddy(data).records('_acme-challenge')
    if not proxy.TARGET.exists() or not proxy.TARGET.read_text().startswith('# Managed by Ohara\n'):
        raise ValueError('Managed Nginx configuration is missing; run scripts/setup first')
    old = proxy.TARGET.read_text()
    candidate = nginx_config(old, c, root)
    if renewal_only and not (CERT_DIR / 'fullchain.pem').is_file():
        raise ValueError('Existing ohara-wildcard certificate required for --configure-renewal')
    hook = Path('/etc/letsencrypt/renewal-hooks/deploy/ohara-nginx')
    if hook.exists() and hook.read_text() != proxy.RENEW_HOOK:
        raise ValueError('Existing Nginx renewal hook differs; inspect before replacing')
    install(root, data, staging)
    if renewal_only:
        # Certbot tests staging validation before saving the new renewal options.
        run(['certbot', 'reconfigure', '--cert-name', CERT_NAME] + options(), timeout=15000)
    else:
        args = ['certbot', 'certonly', '--cert-name', CERT_NAME, '--agree-tos',
                '--email', c['ACME_EMAIL'],
                '--force-renewal' if staging else '--keep-until-expiring'] + options(staging)
        args += ['-d', c['DOMAIN'], '-d', '*.' + c['DOMAIN']]
        if staging:
            args += ['--staging', '--config-dir', '/etc/letsencrypt-staging',
                     '--work-dir', '/var/lib/letsencrypt-staging', '--logs-dir', '/var/log/letsencrypt-staging']
        run(args, timeout=15000)
        if staging:
            print('DNS staging issuance passed; production certificate and Nginx routes unchanged.')
            return
        if not all((CERT_DIR / n).is_file() for n in ('fullchain.pem', 'privkey.pem')):
            raise ValueError('Production certificate files are missing; existing Nginx routes preserved')
        run(['certbot', 'reconfigure', '--cert-name', CERT_NAME] + options(), timeout=15000)
    hook.parent.mkdir(parents=True, exist_ok=True)
    proxy.atomic_write(hook, proxy.RENEW_HOOK, 0o755)
    if not renewal_only:
        proxy.apply_config(candidate)
    run(['systemctl', 'enable', '--now', 'certbot.timer'])
    run(['certbot', 'renew', '--cert-name', CERT_NAME, '--dry-run', '--run-deploy-hooks'], timeout=15000)
    print('DNS renewal configured and dry run passed; verify HTTPS externally.')
