"""Conservative Debian/Ubuntu bootstrap. No network/SSH/resolver reconfiguration."""
import os
from pathlib import Path
import socket

import config
import credentials as credential_files
from runtime import run


def require_root():
    if os.geteuid() != 0:
        raise RuntimeError('Host preparation requires sudo scripts/setup (no Docker-group changes)')


def os_info(text):
    values = dict(line.split('=', 1) for line in text.splitlines() if '=' in line)
    identity = values.get('ID', '').strip('"')
    version = values.get('VERSION_ID', '').strip('"')
    supported = {('ubuntu', '24.04'): 'noble', ('debian', '13'): 'trixie'}
    if (identity, version) not in supported:
        raise ValueError('Bootstrap supports Ubuntu 24.04 and Debian 13 only')
    return identity, supported[(identity, version)]


def installed(package):
    try:
        return run(['dpkg-query', '-W', '-f=${Status}', package], capture=True).strip() == 'install ok installed'
    except RuntimeError:
        return False


def ensure_packages(packages):
    missing = [p for p in packages if not installed(p)]
    if missing:
        run(['apt-get', 'update'], timeout=600)
        run(['apt-get', 'install', '-y'] + missing, timeout=900,
            env=dict(os.environ, DEBIAN_FRONTEND='noninteractive'))


def reject_conflicts():
    for package in ['docker.io', 'docker-compose', 'docker-compose-v2', 'podman-docker', 'containerd', 'runc']:
        if installed(package):
            raise RuntimeError(f'Conflicting package {package}; review the official Docker migration instructions')


def ensure_directory(path, uid, gid, mode=0o750):
    path = Path(path)
    # Existing storage may be a mountpoint, but not a symlink, file, or missing mount.
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
        raise ValueError(f'Symlink storage is unsupported: {path}')
    if path.exists():
        if not path.is_dir():
            raise ValueError(f'Storage is not a directory: {path}')
        return
    if not path.parent.is_dir():
        raise ValueError(f'Storage parent is missing; mount or create it deliberately first: {path.parent}')
    path.mkdir(mode=mode)
    if os.geteuid() == 0:
        os.chown(path, uid, gid)


def prepare_storage(c, root):
    credential_files.load(root)
    owner = int(os.environ.get('SUDO_UID', os.getuid()))
    group = int(os.environ.get('SUDO_GID', os.getgid()))
    local = root / 'local'
    ensure_directory(local, owner, group, 0o700)
    uid, gid = int(c['RUN_UID']), int(c['RUN_GID'])
    ensure_directory(c['DATA_ROOT'], owner, group)
    for name, user, grp in [('seerr', 1000, 1000), ('homepage', uid, gid)]:
        ensure_directory(Path(c['DATA_ROOT']) / name, user, grp)
    def create_owned(path, content, user, grp, mode=0o600):
        if not config.create_file(path, content, mode):
            return
        if os.geteuid() == 0:
            os.chown(path, user, grp)

    for template in (root / 'configs/homepage').glob('*.yaml'):
        destination = Path(c['DATA_ROOT']) / 'homepage' / template.name
        if destination.is_symlink():
            raise ValueError('Symlink Homepage configuration is unsupported')
        create_owned(destination, template.read_text(), uid, gid, 0o640)
    from media import prepare
    prepare(c, root, create_owned, ensure_directory, owner, group)
    print('Storage ready; user-supplied credential files preserved (values not printed).')


def preflight(c):
    os_info(Path('/etc/os-release').read_text())
    architecture = run(['dpkg', '--print-architecture'], capture=True).strip()
    if architecture not in ('amd64', 'arm64'):
        raise ValueError('Bootstrap supports amd64 and arm64 only')
    if not Path('/run/systemd/system').is_dir():
        raise ValueError('Bootstrap requires a running systemd host; use a VM, not a plain container')
    check_web_ports()
    for name in ['download.docker.com', 'registry-1.docker.io']:
        run(['getent', 'ahosts', name], capture=True, timeout=15)
    return architecture


def check_web_ports():
    import shutil
    if shutil.which('ss'):
        listeners = run(['ss', '-H', '-ltnp'], capture=True)
        for line in listeners.splitlines():
            if any(part.rsplit(':', 1)[-1] in ('80', '443') for part in line.split()[:4]):
                if 'nginx' not in line:
                    raise ValueError('Host port 80/443 is occupied by another process; inspect ss -lntup')
        return
    # Minimal hosts may not have iproute2 until the package phase. Socket probes
    # allow a fresh host through without mutating anything during dry-run.
    for port in (80, 443):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                probe.bind(('0.0.0.0', port))
        except OSError:
            raise ValueError('Host port 80/443 is occupied; install iproute2 to inspect listeners before retrying') from None


def prepare(c, root, dry_run=False):
    require_root()
    credential_files.load(root)
    architecture = preflight(c)
    identity, codename = os_info(Path('/etc/os-release').read_text())
    reject_conflicts()
    if dry_run:
        print('Preflight passed. Would install missing Docker/Nginx/Certbot packages and prepare storage; no changes made.')
        return
    ensure_packages(['ca-certificates', 'curl', 'gnupg', 'python3', 'python3-minimal', 'iproute2'])
    if not installed('docker-ce'):
        # A custom/binary Docker install must be reviewed, not overwritten.
        import shutil
        if shutil.which('docker'):
            raise RuntimeError('Existing non-package Docker installation; review it before setup')
        key = Path('/etc/apt/keyrings/docker.asc')
        key.parent.mkdir(parents=True, exist_ok=True)
        source = Path('/etc/apt/sources.list.d/ohara-docker.sources')
        expected = (f'Types: deb\nURIs: https://download.docker.com/linux/{identity}\n'
                    f'Suites: {codename}\nComponents: stable\nArchitectures: {architecture}\nSigned-By: {key}\n')
        if source.exists() and source.read_text() != expected:
            raise ValueError('Existing Ohara Docker apt source differs; inspect manually')
        # Refuse competing Docker repository declarations to avoid Signed-By conflicts.
        for candidate in Path('/etc/apt/sources.list.d').glob('*'):
            if candidate != source and candidate.is_file() and 'download.docker.com' in candidate.read_text():
                raise ValueError('Docker apt source already exists; reconcile it before setup')
        if not key.exists():
            run(['curl', '--fail', '--silent', '--show-error', '--max-time', '60',
                 f'https://download.docker.com/linux/{identity}/gpg', '-o', str(key)], timeout=70)
            key.chmod(0o644)
        config.create_file(source, expected, 0o644)
    ensure_packages(['docker-ce', 'docker-ce-cli', 'containerd.io', 'docker-buildx-plugin', 'docker-compose-plugin'])
    run(['systemctl', 'enable', '--now', 'docker'], timeout=60)
    run(['docker', 'info', '--format', '{{.ServerVersion}}'], capture=True, timeout=30)
    run(['docker', 'compose', 'version'], capture=True)
    new_nginx = not installed('nginx')
    ensure_packages(['nginx', 'certbot'])
    if new_nginx:
        # Only a default site just installed by us may be disabled automatically.
        default = Path('/etc/nginx/sites-enabled/default')
        if default.is_symlink() and str(default.resolve()) == '/etc/nginx/sites-available/default':
            default.unlink()
    prepare_storage(c, root)
    from proxy import bootstrap
    bootstrap(c, root)
    run(['systemctl', 'enable', '--now', 'nginx'], timeout=60)
    print('Host prepared. Run scripts/check and scripts/up; no public application routes were enabled.')
