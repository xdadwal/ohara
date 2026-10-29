"""Host-specific Bambuddy public activation with LAN-only first-owner mode."""
import datetime
import os
from pathlib import Path
import re
import socket
import subprocess
import tempfile

import bambuddy
import config
import runtime

MARKER = '# Managed by scripts/bambuddy-proxy;'
HOSTNAME = 'bambuddy.xdadwal.in'
CERTIFICATE = '/etc/letsencrypt/live/ohara-wildcard/fullchain.pem'
KEY = '/etc/letsencrypt/live/ohara-wildcard/privkey.pem'


def render(root, *, public=False):
    text = (root/'configs/nginx/deployed/ohara-bambuddy.conf').read_text()
    if public:
        return text
    guard = '\n    if ($ohara_bambuddy_allowed = 0) { return 403; }'
    text = text.replace('    server_name '+HOSTNAME+';', '    server_name '+HOSTNAME+';'+guard)
    return ('# Managed by scripts/bambuddy-proxy; LAN-only owner onboarding.\n'
            'geo $ohara_bambuddy_allowed {\n    default 0;\n    127.0.0.1/32 1;\n'
            '    ::1/128 1;\n    192.168.1.0/24 1;\n}\n'+text)


def require_accounts():
    state = bambuddy.client().call('/api/v1/auth/status')
    if state.get('requires_setup') is not False or state.get('auth_enabled') is not True:
        raise ValueError('Native owner authentication must be configured before public activation')


def without_legacy_route(text):
    parts = text.split('\nserver {\n')
    output = [parts[0]]
    for part in parts[1:]:
        if re.search(r'\bserver_name\s+bambuddy\.xdadwal\.in;', part):
            continue
        output.append(part.replace(' bambuddy.xdadwal.in;', ';'))
    return '\nserver {\n'.join(output).strip()


def replace(path, data, mode, owner):
    fd, temporary = tempfile.mkstemp(prefix='.bambuddy-proxy-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        if os.geteuid() == 0:
            os.chown(temporary, *owner)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def deploy(candidates, backup, *, runner=runtime.run):
    previous = {}
    for path in candidates:
        if path.is_symlink():
            raise ValueError('Refusing to replace symlink Nginx configuration')
        st = path.stat() if path.exists() else None
        previous[path] = (path.read_bytes() if st else None,
                          st.st_mode & 0o777 if st else 0o644,
                          (st.st_uid, st.st_gid) if st else (0, 0))
    backup.mkdir(parents=True, mode=0o700)
    for path, (data, _, _) in previous.items():
        if data is not None:
            config.create_file(backup/path.name, data.decode(), 0o600)
    runner(['/usr/sbin/nginx', '-t'])
    try:
        for path, data in candidates.items():
            _, mode, owner = previous[path]
            replace(path, data, mode, owner)
        runner(['/usr/sbin/nginx', '-t'])
        runner(['systemctl', 'reload', 'nginx'])
    except (OSError, RuntimeError, subprocess.TimeoutExpired):
        for path, (data, mode, owner) in previous.items():
            if data is None:
                path.unlink(missing_ok=True)
            else:
                replace(path, data, mode, owner)
        runner(['/usr/sbin/nginx', '-t'])
        runner(['systemctl', 'reload', 'nginx'])
        raise RuntimeError('Bambuddy proxy deployment failed; previous route files restored') from None
    print('Previous route files backed up to '+str(backup))


def apply(c, root, *, public=False):
    if os.geteuid() != 0:
        raise ValueError('Run sudo scripts/bambuddy-proxy --apply with the chosen access mode')
    if c['DOMAIN'] != 'xdadwal.in':
        raise ValueError('This installer is specific to the verified xdadwal.in host')
    with socket.socket() as probe:
        probe.bind(('192.168.1.101', 0))
    for path in (CERTIFICATE, KEY, '/etc/nginx/conf.d/ohara.conf'):
        if not Path(path).is_file():
            raise ValueError('Existing wildcard certificate and Ohara host are required')
    runtime.run(['openssl', 'verify', '-CApath', '/etc/ssl/certs', '-untrusted', CERTIFICATE,
                 '-verify_hostname', HOSTNAME, CERTIFICATE])
    runtime.run(['openssl', 'x509', '-in', CERTIFICATE, '-noout', '-checkend', '86400'])
    if public:
        require_accounts()
    else:
        bambuddy.client().call('/health')
    directory = Path('/etc/nginx/conf.d')
    lan = directory/'ohara-lan.conf'
    target = directory/'ohara-bambuddy.conf'
    desired_lan = (root/'configs/nginx/deployed/ohara-lan.conf').read_text()
    if lan.is_symlink() or not lan.is_file() or without_legacy_route(lan.read_text()) != desired_lan.strip():
        raise ValueError('Existing LAN routes differ beyond the Bambuddy migration; preserve/review first')
    if target.is_symlink() or (target.exists() and not target.read_text().startswith(MARKER)):
        raise ValueError('Existing Bambuddy proxy file is unmanaged; preserve/review first')
    for path in directory.glob('*.conf'):
        if path in (lan, target):
            continue
        if any(HOSTNAME in names.split() for names in re.findall(r'\bserver_name\s+([^;]+);', path.read_text())):
            raise ValueError('Another Nginx site defines Bambuddy; preserve/review first')
    backup = Path('/var/backups/ohara')/('bambuddy-proxy-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    deploy({lan: desired_lan.encode(), target: render(root, public=public).encode()}, backup)
    print(('Public Bambuddy' if public else 'LAN-only Bambuddy onboarding')+' HTTPS enabled; other admin routes remain LAN-only')
