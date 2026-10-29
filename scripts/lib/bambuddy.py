"""Optional Bambuddy lifecycle. Printer access and owner setup stay in its UI."""
import base64
import datetime
import json
import os
from pathlib import Path
import re

import adguard
import config
import host
import jellyfin_theme
import media
import runtime


def settings(c):
    base = Path(c.get('BAMBUDDY_ROOT', str(Path(c['DATA_ROOT'])/'bambuddy')))
    expected = Path(c.get('BAMBUDDY_MOUNT', '/'))
    for path in (base, expected):
        if (str(path) != '/' and not config.PATH.fullmatch(str(path))) or '..' in path.parts:
            raise ValueError('Bambuddy requires safe absolute storage paths')
        if any(p.is_symlink() for p in (path, *path.parents)):
            raise ValueError('Bambuddy storage must not use symlinks')
    if base == Path('/') or expected not in base.parents:
        raise ValueError('BAMBUDDY_ROOT must be below BAMBUDDY_MOUNT')
    protected = [Path(c['MEDIA_ROOT']), Path(c['DATA_ROOT'])/'media'] + [Path(c['DATA_ROOT'])/n for n in
        ('jellyfin', 'jellyfin-cache', 'homepage', 'seerr', 'immich', 'radarr', 'sonarr', 'lidarr', 'bazarr', 'prowlarr', 'navidrome', 'qbittorrent', 'adguard', 'maintainerr')]
    if any(base == p or base in p.parents or p in base.parents for p in protected):
        raise ValueError('Bambuddy storage must be separate from other applications and media')
    return base, expected


def images(root):
    values = config.parse(root/'versions.bambuddy.env', {'BAMBUDDY_IMAGE'})
    if not re.fullmatch(r'ghcr.io/maziggy/bambuddy:[0-9.]+@sha256:[a-f0-9]{64}', values['BAMBUDDY_IMAGE']):
        raise ValueError('Bambuddy requires an official immutable release image')
    return values


def require_storage(c, *, directories=True):
    base, expected = settings(c)
    existing = base
    while not existing.exists():
        existing = existing.parent
    result = json.loads(runtime.run(['findmnt', '--json', '--target', str(existing),
                                     '-o', 'TARGET,FSTYPE'], capture=True))['filesystems'][0]
    if result['target'] != str(expected) or result['fstype'] not in {'ext4', 'xfs', 'btrfs', 'zfs'}:
        raise ValueError('Bambuddy storage is not on the expected local Linux filesystem')
    if directories:
        for p in (base/'data', base/'logs'):
            if p.is_symlink() or not p.is_dir() or not config.directory_writable(p, int(c['RUN_UID']), int(c['RUN_GID'])):
                raise ValueError('Run scripts/bambuddy prepare; review existing storage ownership manually')


def compose(c, root, args, *, capture=False, timeout=60):
    if any(a in {'up', 'start', 'restart', 'create', 'run'} for a in args):
        require_storage(c)
    base, _ = settings(c)
    values = {k: c[k] for k in ('RUN_UID', 'RUN_GID', 'TZ')}
    values.update(BAMBUDDY_ROOT=str(base), COMPOSE_DISABLE_ENV_FILE='1')
    values.update(images(root))
    env = {k: v for k, v in os.environ.items() if k in
           {'PATH', 'HOME', 'USER', 'XDG_RUNTIME_DIR', 'DOCKER_CONFIG', 'DOCKER_HOST', 'DOCKER_CONTEXT', 'SSH_AUTH_SOCK'}}
    env.update(values)
    prefix = ['docker'] if args[0] == 'config' else runtime.docker_prefix()
    if prefix[:2] == ['sudo', '-n']:
        prefix = prefix[:2]+['--preserve-env='+','.join(sorted(values))]+prefix[2:]
    return runtime.run(prefix+['compose', '--project-directory', str(root), '--env-file', '/dev/null',
                              '-f', str(root/'compose.bambuddy.yaml'), *args], env=env, capture=capture, timeout=timeout)


def check(c, root, *, static=False):
    base, _ = settings(c)
    model = json.loads(compose(c, root, ['config', '--format', 'json'], capture=True))
    if model.get('name') != 'ohara-bambuddy' or set(model['services']) != {'bambuddy'}:
        raise ValueError('Unexpected Bambuddy project inventory')
    s = model['services']['bambuddy']
    mounts = {(v.get('source'), v['target'], v.get('read_only', False)) for v in s.get('volumes', [])}
    ports = {(p.get('host_ip'), int(p['published']), int(p['target'])) for p in s.get('ports', [])}
    if (s['image'] != images(root)['BAMBUDDY_IMAGE'] or s.get('user') != c['RUN_UID']+':'+c['RUN_GID']
            or s.get('privileged') or s.get('network_mode') == 'host'
            or ports != {('127.0.0.1', 8008, 8000)}
            or mounts != {(str(base/'data'), '/app/data', False), (str(base/'logs'), '/app/logs', False)}
            or set(s.get('environment', {})) != {'TZ', 'HOST', 'PORT', 'DATA_DIR', 'LOG_DIR', 'DEBUG', 'LOG_LEVEL'}
            or s.get('cap_drop') != ['ALL'] or s.get('cap_add') != ['NET_BIND_SERVICE']
            or 'no-new-privileges:true' not in s.get('security_opt', [])):
        raise ValueError('Bambuddy must keep dedicated state, non-root execution and only its loopback web port')
    if any(v.get('bind', {}).get('create_host_path', False) for v in s['volumes']):
        raise ValueError('Bambuddy must not auto-create storage')
    if not static:
        require_storage(c)
    print('Bambuddy configuration valid'+(' (static only)' if static else ''))


def prepare(c, root):
    check(c, root, static=True)
    require_storage(c, directories=False)
    base, _ = settings(c)
    for p in (base, base/'data', base/'logs'):
        host.ensure_directory(p, int(c['RUN_UID']), int(c['RUN_GID']), 0o700)
    check(c, root)


def client():
    return media.Client('http://127.0.0.1:8008')


def status():
    api = client()
    if api.call('/health').get('status') != 'healthy':
        raise ValueError('Bambuddy health check failed')
    state = api.call('/api/v1/auth/status')
    print('Bambuddy healthy; owner setup '+('pending' if state['requires_setup'] else 'completed')+
          '; authentication '+('enabled' if state['auth_enabled'] else 'disabled'))
    print('Printer connection, camera and real printing require owner UI verification.')


def homepage(c, root):
    import yaml
    path = Path(c['DATA_ROOT'])/'homepage/services.yaml'
    jellyfin_theme.safe(path)
    before = path.read_text()
    data = yaml.safe_load(before)
    if any('Bambuddy' in entry for group in data for rows in group.values() for entry in rows):
        print('Existing Bambuddy Homepage card preserved')
        return
    group = next((g['Utility'] for g in data if 'Utility' in g), None)
    if group is None:
        group = []
        data.append({'Utility': group})
    group.append({'Bambuddy': {'icon': 'mdi-printer-3d', 'href': 'https://bambuddy.'+c['DOMAIN'],
                              'description': 'Bambu Lab A1 mini (local network)'}})
    backup = root/'local/bambuddy-backups'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S-homepage')
    backup.mkdir(parents=True, mode=0o700)
    config.create_file(backup/'services.yaml', before)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))
    print('Bambuddy Homepage card merged; existing cards and widgets preserved')


def dns(c, root):
    name = 'bambuddy.'+c['DOMAIN']
    address, _ = adguard.settings(c)
    api = media.Client('http://127.0.0.1:3003')
    api.headers['Authorization'] = 'Basic '+base64.b64encode(('admin:'+adguard.password(root)).encode()).decode()
    matches = [r for r in api.call('/control/rewrite/list') if r['domain'] == name]
    if matches:
        if not all(r['answer'] == address and r.get('enabled', True) for r in matches):
            raise ValueError('Conflicting Bambuddy DNS rewrite; preserve and review')
    else:
        api.call('/control/rewrite/add', {'domain': name, 'answer': address})
    print('Exact Bambuddy LAN DNS rewrite present; other records preserved')
