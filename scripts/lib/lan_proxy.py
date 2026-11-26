"""Reviewed xdadwal.in LAN-only Nginx baseline for its existing host."""

import datetime
import os
from pathlib import Path
import socket
import tempfile

import nginx_site
import runtime


def candidate(root):
    return root / 'configs/nginx/deployed/ohara-lan.conf'


def apply(root):
    """Back up, install, test and reload the routes; restore the previous file on failure."""
    if os.geteuid() != 0:
        raise RuntimeError('Administrator access is required: sudo scripts/lan-proxy --apply')
    # This is deliberately not a fresh-host or arbitrary-domain installer.
    with socket.socket() as probe:
        probe.bind(('192.168.1.101', 0))
    for required in (
        '/etc/letsencrypt/live/ohara-wildcard/fullchain.pem',
        '/etc/letsencrypt/live/ohara-wildcard/privkey.pem',
        '/etc/nginx/conf.d/ohara.conf',
    ):
        if not Path(required).is_file():
            raise RuntimeError('Existing host certificate and Nginx baseline are required')
    target = Path('/etc/nginx/conf.d/ohara-lan.conf')
    if target.is_symlink():
        raise RuntimeError('Refusing to replace a symlink Nginx configuration')
    runtime.run([nginx_site.NGINX, '-t'])
    previous, mode, owner = nginx_site.existing(target)
    backup_dir = Path('/var/backups/ohara')
    backup_dir.mkdir(mode=0o700, exist_ok=True)
    if previous is not None:
        descriptor, backup = tempfile.mkstemp(
            prefix='ohara-lan-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S') + '-',
            dir=backup_dir,
        )
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(previous)
        print('Previous LAN configuration backed up to ' + backup)
    nginx_site.install(
        target,
        lambda: candidate(root).read_bytes(),
        previous,
        mode,
        owner,
        prefix='.ohara-lan-',
        failure='LAN route deployment failed; previous configuration restored',
    )
    print(
        'LAN-only routes installed and Nginx reloaded; public routes and backend bindings preserved.'
    )
