"""Read-only host diagnostics and opt-in terminal packages. Never display child errors."""
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess

import config
import host
import runtime

PACKAGES = ['tmux', 'bpytop']


def terminal_tools(install=False):
    if not install:
        for package in PACKAGES:
            print(f'{package}: {"available" if shutil.which(package) else "missing"}')
        print('Would install missing tmux/bpytop packages with --install; no changes made.')
        return 0
    if os.geteuid() != 0:
        raise ValueError('Run sudo scripts/ohara tools --install')
    host.os_info(Path('/etc/os-release').read_text())
    host.ensure_packages(PACKAGES)
    print('Terminal tools ready: tmux and bpytop. Shell configuration preserved.')
    return 0


def pressure(stats):
    disk = 100 * (1 - stats.f_bavail / stats.f_blocks) if stats.f_blocks else 0
    inode = 100 * (1 - stats.f_favail / stats.f_files) if stats.f_files else None
    state = 'fail' if disk >= 95 or (inode is not None and inode >= 95) else (
        'warn' if disk >= 85 or (inode is not None and inode >= 85) else 'ok')
    return state, disk, inode


def collect(root):
    rows = []

    def add(name, state, detail):
        rows.append(dict(check=name, status=state, detail=detail))

    def command(name, args, success, failure, optional=False):
        if not shutil.which(args[0]):
            add(name, 'warn', f'{args[0]} unavailable; check not performed')
            return
        try:
            runtime.run(args, capture=True, timeout=15)
            add(name, 'ok', success)
        except (OSError, RuntimeError, subprocess.TimeoutExpired):
            add(name, 'warn' if optional else 'fail', failure)

    c = None
    try:
        c = config.load(root / '.env')
        add('configuration', 'ok', 'Configuration valid; values omitted')
    except (OSError, ValueError):
        add('configuration', 'fail', 'Missing/invalid .env; run scripts/check privately for details')

    command('systemd', ['systemctl', 'is-system-running', '--quiet'],
            'System running without failed units',
            'System not healthy or inaccessible; inspect systemctl --failed locally')
    command('nginx', ['systemctl', 'is-active', '--quiet', 'nginx'],
            'Nginx active', 'Nginx inactive or inaccessible')
    command('nginx-config', ['nginx', '-t'], 'Nginx configuration valid',
            'Configuration invalid or insufficient permissions; run sudo nginx -t', optional=os.geteuid() != 0)
    command('certificate-timer', ['systemctl', 'is-active', '--quiet', 'certbot.timer'],
            'Certbot timer active; this does not verify renewal', 'Certbot timer inactive or inaccessible')
    if shutil.which('tailscale'):
        try:
            state = json.loads(runtime.run(['tailscale', 'status', '--json'], capture=True, timeout=15))
            online = state.get('BackendState') == 'Running' and state.get('Self', {}).get('Online') is True
            add('tailscale', 'ok' if online else 'warn',
                'Client online; SSH policy/login unverified' if online else 'Client not online; inspect privately')
        except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired):
            add('tailscale', 'warn', 'Client state unavailable; inspect locally')
    else:
        add('tailscale', 'skip', 'Optional client not installed')
    for tool in PACKAGES:
        add(tool, 'ok' if shutil.which(tool) else 'skip',
            'Available' if shutil.which(tool) else 'Optional tool not installed')

    if c:
        for label in ('DATA_ROOT', 'MEDIA_ROOT'):
            path = Path(c[label])
            try:
                if not path.is_dir():
                    raise OSError('missing directory')
                stats = os.statvfs(path)
                state, disk, inode = pressure(stats)
                total = stats.f_blocks * stats.f_frsize / 1024**3
                add(label + '-capacity', state, f'{total:.1f} GiB filesystem; {disk:.1f}% used; '
                    + (f'{inode:.1f}% inodes used' if inode is not None else 'inode count unavailable'))
                # Show containing mount, not source/device IDs or all filesystem metadata.
                mount = path.resolve()
                while not os.path.ismount(mount) and mount != mount.parent:
                    mount = mount.parent
                add(label + '-mount', 'warn' if mount == Path('/') else 'ok',
                    f'Containing mount: {mount}; verify against intended storage layout')
            except OSError:
                add(label + '-storage', 'fail', 'Directory missing or unreadable; verify mounts before startup')
        for name in ('downloads', 'library/music'):
            path = Path(c['MEDIA_ROOT']) / name
            try:
                ready = path.is_dir() and config.directory_writable(path, int(c['RUN_UID']), int(c['RUN_GID']))
                add('permissions-' + name, 'ok' if ready else 'fail',
                    'Mode bits permit configured media UID/GID' if ready else 'Missing path or media UID/GID lacks write access')
            except OSError:
                add('permissions-' + name, 'fail', 'Unable to inspect path permissions')
        try:
            # Existing status function emits only fixed service names and bounded HTTP health.
            with contextlib.redirect_stdout(io.StringIO()):
                result = runtime.status(c, root)
            add('applications', 'ok' if result == 0 else 'fail',
                'Container/HTTP checks passed' if result == 0 else 'Unhealthy services; run scripts/status')
        except (OSError, RuntimeError, ValueError, KeyError, subprocess.TimeoutExpired):
            add('applications', 'fail', 'Container checks unavailable; verify Docker access and run scripts/status')
        certificates = [Path('/etc/letsencrypt/live') / name / 'cert.pem' for name in ('ohara', 'ohara-wildcard')]
        found = False
        for cert in certificates:
            try:
                present = cert.is_file()
            except OSError:
                add('certificate-' + cert.parent.name, 'warn', 'Certificate inaccessible; expiry unverified')
                continue
            if present:
                found = True
                command('certificate-' + cert.parent.name,
                        ['openssl', 'x509', '-in', str(cert), '-noout', '-checkend', '2592000'],
                        'Certificate expires in more than 30 days; hostname/renewal unverified',
                        'Expires within 30 days or unreadable; inspect certificate locally', optional=True)
        if not found:
            add('certificates', 'warn', 'Managed certificates absent or inaccessible; HTTPS expiry unverified')
    return rows


def doctor(root, as_json=False):
    rows = collect(root)
    code = 1 if any(row['status'] == 'fail' for row in rows) else 0
    if as_json:
        print(json.dumps({'checks': rows, 'exit_code': code}))
    else:
        for row in rows:
            print(f'{row["status"].upper():4} {row["check"]}: {row["detail"]}')
        print('Read-only checks; no repairs. Public reachability, backups and real application workflows are unverified.')
    return code
