"""Reviewed xdadwal.in LAN-only Nginx baseline for its existing host."""

import datetime
import os
from pathlib import Path
import socket
import subprocess
import tempfile

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
    nginx = '/usr/sbin/nginx'
    runtime.run([nginx, '-t'])
    previous = target.read_bytes() if target.exists() else None
    mode = target.stat().st_mode & 0o777 if target.exists() else 0o644
    owner = (target.stat().st_uid, target.stat().st_gid) if target.exists() else (0, 0)
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

    def replace(data, permissions):
        descriptor, temporary = tempfile.mkstemp(prefix='.ohara-lan-', dir=target.parent)
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
        replace(candidate(root).read_bytes(), 0o644)
        runtime.run([nginx, '-t'])
        runtime.run(['systemctl', 'reload', 'nginx'])
    except (OSError, RuntimeError, subprocess.TimeoutExpired):
        if previous is None:
            target.unlink(missing_ok=True)
        else:
            replace(previous, mode)
        runtime.run([nginx, '-t'])
        runtime.run(['systemctl', 'reload', 'nginx'])
        raise RuntimeError('LAN route deployment failed; previous configuration restored') from None
    print(
        'LAN-only routes installed and Nginx reloaded; public routes and backend bindings preserved.'
    )
