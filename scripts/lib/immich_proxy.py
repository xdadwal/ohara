"""Immich HTTPS route on the existing xdadwal.in wildcard Nginx host."""

import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import urllib.request

import config
import runtime

CERTIFICATE = '/etc/letsencrypt/live/ohara-wildcard/fullchain.pem'
KEY = '/etc/letsencrypt/live/ohara-wildcard/privkey.pem'


def render(root, *, onboarding_only=False):
    text = (root / 'configs/nginx/immich.template').read_text()
    for key, value in {
        'IMMICH_HOST': 'immich.xdadwal.in',
        'CERTIFICATE': CERTIFICATE,
        'CERTIFICATE_KEY': KEY,
    }.items():
        text = text.replace('${' + key + '}', value)
    candidate = (
        '# Managed by scripts/immich-proxy; independent of the main Ohara routes.\n'
        'server {\n    listen 80;\n    listen [::]:80;\n'
        '    server_name immich.xdadwal.in;\n'
        '    location ^~ /.well-known/acme-challenge/ {\n'
        '        root /var/lib/ohara/acme;\n        default_type text/plain;\n'
        '        try_files $uri =404;\n    }\n'
        '    location / { return 301 https://$host$request_uri; }\n}\n' + text
    )
    if onboarding_only:
        guard = '\n    if ($ohara_immich_onboarding_allowed = 0) { return 403; }'
        candidate = candidate.replace(
            'server_name immich.xdadwal.in;', 'server_name immich.xdadwal.in;' + guard
        )
        candidate = (
            '# Managed by scripts/immich-proxy; LAN-only owner onboarding.\n'
            'geo $ohara_immich_onboarding_allowed {\n'
            '    default 0;\n    127.0.0.1/32 1;\n    ::1/128 1;\n    192.168.1.0/24 1;\n}\n'
            + candidate
        )
    return candidate


def apply(root, *, onboarding_only=False, accounts_ready=False):
    """Back up, install, test and reload the route; restore the previous file on failure."""
    if not accounts_ready and not onboarding_only:
        raise ValueError('Verify private owner login first, then use --accounts-ready')
    if os.geteuid() != 0:
        raise ValueError(
            'Administrator access is required: sudo scripts/immich-proxy --apply '
            + ('--onboarding-only' if onboarding_only else '--accounts-ready')
        )
    if config.load(root / '.env')['DOMAIN'] != 'xdadwal.in':
        raise ValueError('This installer is specific to the existing xdadwal.in host')
    for path in (CERTIFICATE, KEY, '/etc/nginx/conf.d/ohara.conf'):
        if not Path(path).is_file():
            raise ValueError('Existing wildcard certificate and Ohara Nginx host are required')
    runtime.run(
        [
            'openssl',
            'verify',
            '-CApath',
            '/etc/ssl/certs',
            '-untrusted',
            CERTIFICATE,
            '-verify_hostname',
            'immich.xdadwal.in',
            CERTIFICATE,
        ]
    )
    runtime.run(['openssl', 'x509', '-in', CERTIFICATE, '-noout', '-checkend', '86400'])
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open('http://127.0.0.1:2283/api/server/config', timeout=10) as response:
        if json.load(response).get('isInitialized') is not True and not onboarding_only:
            raise ValueError('Immich owner onboarding is incomplete; public activation refused')
    with opener.open('http://127.0.0.1:2283/api/server/features', timeout=10) as response:
        features = json.load(response)
        if any(features.get(name) for name in ('smartSearch', 'facialRecognition', 'ocr')):
            raise ValueError('Immich machine learning must remain disabled')
    target = Path('/etc/nginx/conf.d/ohara-immich.conf')
    if target.is_symlink():
        raise ValueError('Refusing to replace a symlink Nginx configuration')
    for path in target.parent.glob('*.conf'):
        if path == target:
            continue
        names = re.findall(r'\bserver_name\s+([^;]+);', path.read_text())
        if any('immich.xdadwal.in' in nameset.split() for nameset in names):
            raise ValueError(
                'Another Nginx file already defines immich.xdadwal.in; review it first'
            )
    nginx = '/usr/sbin/nginx'
    runtime.run([nginx, '-t'])
    previous = target.read_bytes() if target.exists() else None
    if previous is not None and not previous.startswith(b'# Managed by scripts/immich-proxy;'):
        raise ValueError('Existing Immich Nginx configuration is unmanaged; review it first')
    mode = target.stat().st_mode & 0o777 if target.exists() else 0o644
    owner = (target.stat().st_uid, target.stat().st_gid) if target.exists() else (0, 0)
    if previous is not None:
        backup_dir = Path('/var/backups/ohara')
        backup_dir.mkdir(mode=0o700, exist_ok=True)
        descriptor, backup = tempfile.mkstemp(prefix='ohara-immich-', dir=backup_dir)
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(previous)
        print('Previous Immich route backed up to ' + backup)

    def replace(data, permissions):
        descriptor, temporary = tempfile.mkstemp(prefix='.ohara-immich-', dir=target.parent)
        try:
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary, permissions)
            os.chown(temporary, *owner)
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    try:
        replace(render(root, onboarding_only=onboarding_only).encode(), 0o644)
        runtime.run([nginx, '-t'])
        runtime.run(['systemctl', 'reload', 'nginx'])
    except (OSError, RuntimeError, subprocess.TimeoutExpired):
        if previous is None:
            target.unlink(missing_ok=True)
        else:
            replace(previous, mode)
        runtime.run([nginx, '-t'])
        runtime.run(['systemctl', 'reload', 'nginx'])
        raise RuntimeError(
            'Immich route activation failed; previous Nginx configuration restored'
        ) from None
    print(
        ('LAN-only Immich onboarding' if onboarding_only else 'Public Immich')
        + ' HTTPS activated; other routes and certificates preserved.'
    )
