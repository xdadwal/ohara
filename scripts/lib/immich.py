"""Isolated Immich lifecycle with literal inputs and stable container paths."""
import json
import os
from pathlib import Path
import re
import shutil
import urllib.request

import config
import credentials
import runtime

IMAGE_KEYS = {'IMMICH_SERVER_IMAGE', 'IMMICH_CACHE_IMAGE', 'IMMICH_DATABASE_IMAGE'}


def settings(c):
    values = {key: c.get(key, default) for key, default in {
        'IMMICH_LIBRARY_ROOT': '/ohara/immich/library',
        'IMMICH_DATABASE_ROOT': '/ohara/immich/postgres',
        'IMMICH_LIBRARY_MOUNT': '/', 'IMMICH_DATABASE_MOUNT': '/',
    }.items()}
    for key, value in values.items():
        path = Path(value)
        if ((value != '/' and not config.PATH.fullmatch(value)) or '..' in path.parts or '//' in value
                or (value == '/' and key.endswith('_ROOT'))):
            raise ValueError(f'{key}: require a safe absolute path')
        if any(p.is_symlink() for p in (path, *path.parents)):
            raise ValueError(f'{key}: symlink storage paths are unsupported')
    roots = [Path(values[k]) for k in ('IMMICH_LIBRARY_ROOT', 'IMMICH_DATABASE_ROOT')]
    def overlaps(a, b):
        return a == b or a in b.parents or b in a.parents
    if overlaps(*roots):
        raise ValueError('Immich library and database paths must be separate and non-nested')
    protected = [Path(c['MEDIA_ROOT'])] + [Path(c['DATA_ROOT']) / name for name in
        ('homepage', 'seerr', 'jellyfin', 'jellyfin-cache', 'navidrome', 'radarr',
         'sonarr', 'lidarr', 'bazarr', 'prowlarr', 'qbittorrent', 'adguard')]
    if any(overlaps(path, other) for path in roots for other in protected):
        raise ValueError('Immich storage must not overlap existing application/media storage')
    for kind, path in zip(('LIBRARY', 'DATABASE'), roots):
        mount = Path(values[f'IMMICH_{kind}_MOUNT'])
        if mount not in path.parents:
            raise ValueError(f'IMMICH_{kind}_ROOT must be below its expected mount')
    return values


def images(root):
    values = config.parse(root / 'versions.immich.env', IMAGE_KEYS)
    if any(not re.fullmatch(r'[a-z0-9./:_-]+@sha256:[a-f0-9]{64}', v) for v in values.values()):
        raise ValueError('Immich images must have immutable digest pins')
    return values


def password(root, *, allow_short=False):
    value = credentials.read(root / '.env', credentials.IMMICH_KEYS,
        ignored=config.KEYS | (credentials.ALL_KEYS - credentials.IMMICH_KEYS),
        minimum_lengths={'IMMICH_DB_PASSWORD': 1} if allow_short else None)['IMMICH_DB_PASSWORD']
    if not re.fullmatch(r'[A-Za-z0-9]+', value) or (len(value) < 16 and not allow_short):
        raise ValueError('IMMICH_DB_PASSWORD: supply at least 16 ASCII letters/digits privately in .env')
    return value


def compose(c, root, args, *, static=False, capture=False, timeout=60, allow_short=False):
    values = settings(c) | images(root) | {
        'TZ': c['TZ'], 'IMMICH_CONFIG_PATH': str(root / 'configs/immich/immich.json'),
        'COMPOSE_DISABLE_ENV_FILE': '1',
        # Static/status/stop operations never need the real credential.
        'IMMICH_DB_PASSWORD': '' if static else password(root, allow_short=allow_short),
    }
    env = {k: v for k, v in os.environ.items() if k in {
        'PATH', 'HOME', 'USER', 'XDG_RUNTIME_DIR', 'DOCKER_CONFIG', 'DOCKER_HOST',
        'DOCKER_CONTEXT', 'SSH_AUTH_SOCK'}}
    env.update(values)
    prefix = ['docker'] if args[0] == 'config' else runtime.docker_prefix()
    if prefix[:2] == ['sudo', '-n']:
        prefix = prefix[:2] + ['--preserve-env=' + ','.join(sorted(values))] + prefix[2:]
    return runtime.run(prefix + ['compose', '--project-directory', str(root),
        '--env-file', '/dev/null', '-f', str(root / 'compose.immich.yaml')] + args,
        env=env, capture=capture, timeout=timeout)


def validate_model(model, c, root):
    values, pins = settings(c), images(root)
    if model.get('name') != 'ohara-immich' or set(model['services']) != {'immich-server', 'redis', 'database'}:
        raise ValueError('Unexpected Immich project/services; machine learning must stay absent')
    expected_images = dict(zip(('immich-server', 'redis', 'database'),
                              (pins[k] for k in ('IMMICH_SERVER_IMAGE', 'IMMICH_CACHE_IMAGE', 'IMMICH_DATABASE_IMAGE'))))
    expected_mounts = {
        'immich-server': {(values['IMMICH_LIBRARY_ROOT'], '/data', False),
            (str(root / 'configs/immich/immich.json'), '/etc/immich/immich.json', True),
            ('/etc/localtime', '/etc/localtime', True)},
        'database': {(values['IMMICH_DATABASE_ROOT'], '/var/lib/postgresql/data', False)},
        'redis': set(),
    }
    allowed_env = {
        'immich-server': {'TZ', 'DB_HOSTNAME', 'DB_USERNAME', 'DB_DATABASE_NAME',
                         'DB_PASSWORD', 'REDIS_HOSTNAME', 'IMMICH_CONFIG_FILE'},
        'database': {'POSTGRES_PASSWORD', 'POSTGRES_USER', 'POSTGRES_DB', 'POSTGRES_INITDB_ARGS'},
        'redis': set(),
    }
    for name, service in model['services'].items():
        ports = {(p.get('host_ip'), int(p['published']), int(p['target']), p.get('protocol', 'tcp'))
                 for p in service.get('ports', [])}
        if ports != ({('127.0.0.1', 2283, 2283, 'tcp')} if name == 'immich-server' else set()):
            raise ValueError('Unexpected Immich port exposure')
        if (service.get('privileged') or service.get('network_mode') or service.get('devices')
                or service.get('cap_add') or service['image'] != expected_images[name]):
            raise ValueError('Unexpected Immich runtime privileges or image')
        mounts = {(v.get('source'), v['target'], v.get('read_only', False)) for v in service.get('volumes', [])}
        if mounts != expected_mounts[name] or set(service.get('environment', {})) != allowed_env[name]:
            raise ValueError('Unexpected Immich mounts or credential environment')
        if service.get('env_file'):
            raise ValueError('Immich must not consume dotenv files')
        for mount in service.get('volumes', []):
            if mount['target'] in ('/data', '/var/lib/postgresql/data') and mount.get('bind', {}).get('create_host_path', True):
                raise ValueError('Immich must not auto-create storage paths')
    policy = json.loads((root / 'configs/immich/immich.json').read_text())
    if policy.get('machineLearning', {}).get('enabled') is not False:
        raise ValueError('Immich machine learning must be disabled')


def check(c, root, *, static=False, allow_short=False):
    model = json.loads(compose(c, root, ['config', '--format', 'json'], static=True, capture=True))
    validate_model(model, c, root)
    if not static:
        password(root, allow_short=allow_short)
        storage(c, require_directories=True)
    print('Immich configuration valid; machine learning disabled; web port loopback-only.')


def storage(c, *, require_directories=False):
    values = settings(c)
    for kind in ('LIBRARY', 'DATABASE'):
        path = Path(values[f'IMMICH_{kind}_ROOT'])
        expected = Path(values[f'IMMICH_{kind}_MOUNT'])
        if not expected.is_mount():
            raise ValueError(f'IMMICH_{kind}_MOUNT is not mounted; mount the intended disk first')
        existing = path
        while not existing.exists():
            existing = existing.parent
        info = json.loads(runtime.run(['findmnt', '--json', '--target', str(existing),
                                      '--output', 'TARGET,FSTYPE'], capture=True))['filesystems'][0]
        if Path(info['target']) != expected:
            raise ValueError(f'IMMICH_{kind}_ROOT is on a different mount than configured')
        if kind == 'DATABASE' and info['fstype'] not in {'ext4', 'xfs', 'btrfs', 'zfs'}:
            raise ValueError('Immich PostgreSQL requires supported local Linux storage, never a network share')
        if path.exists() and not path.is_dir():
            raise ValueError(f'IMMICH_{kind}_ROOT must be a directory')
        if require_directories and not path.is_dir():
            raise ValueError('Missing Immich storage directories; run scripts/immich prepare')
        free = shutil.disk_usage(existing).free
        if free < 2 * 1024**3:
            raise ValueError(f'IMMICH_{kind}_ROOT has less than 2 GiB free; review capacity')
        print(f'Immich {kind.lower()} mount verified; {free // 1024**3} GiB free (library capacity still needs review).')


def prepare(c, root, *, allow_short=False):
    check(c, root, static=True)
    password(root, allow_short=allow_short)
    storage(c)
    for key in ('IMMICH_LIBRARY_ROOT', 'IMMICH_DATABASE_ROOT'):
        # No recursive ownership change; image entrypoints manage their own state.
        Path(settings(c)[key]).mkdir(parents=True, exist_ok=True, mode=0o700)
    print('Immich storage prepared; existing content and ownership preserved.')


def up(c, root, *, allow_short=False):
    check(c, root, allow_short=allow_short)
    # An existing project may already own 2283. Compose detects other port conflicts.
    compose(c, root, ['up', '-d', '--wait', '--wait-timeout', '180'], timeout=300, allow_short=allow_short)
    print('Immich started privately; complete owner setup and backup/restore acceptance before HTTPS activation.')


def status(c, root):
    rows = compose(c, root, ['ps', '--all', '--format', 'json'], static=True, capture=True)
    rows = rows.strip()
    containers = json.loads(rows) if rows.startswith('[') else [json.loads(line) for line in rows.splitlines()]
    good = ({row.get('Service') for row in containers} == {'immich-server', 'redis', 'database'}
            and all(row.get('State') == 'running' and row.get('Health') == 'healthy' for row in containers))
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open('http://127.0.0.1:2283/api/server/ping', timeout=10) as response:
            good = good and json.load(response).get('res') == 'pong'
    except (OSError, ValueError):
        good = False
    print('Immich: ' + ('containers healthy and local API reachable.' if good else 'not ready; inspect local service logs.'))
    return 0 if good else 1
