"""Bounded subprocess and local stack operations. Never log expanded secrets."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import urllib.error
import urllib.request

import config
import credentials as credential_files


def run(args, *, capture=False, timeout=60, env=None, input=None):
    result = subprocess.run(args, input=input, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=timeout, env=env)
    if result.returncode:
        # Child stderr can contain credentials/resolved configuration. Do not echo it.
        raise RuntimeError(f'{Path(args[0]).name}: command failed (exit {result.returncode}); inspect local service logs')
    if capture:
        return result.stdout
    return None


def docker_prefix():
    if not shutil.which('docker'):
        raise RuntimeError('Docker is missing; run scripts/setup on a supported Linux host')
    try:
        run(['docker', 'info', '--format', '{{.ServerVersion}}'], timeout=15)
        return ['docker']
    except RuntimeError:
        if os.geteuid() != 0 and shutil.which('sudo'):
            run(['sudo', '-n', 'docker', 'info', '--format', '{{.ServerVersion}}'], timeout=15)
            return ['sudo', '-n', 'docker']
        raise


def compose(c, root, args, *, capture=False, timeout=60, docker=None):
    # Do not let ambient COMPOSE_* variables or shell interpolation override config.
    env = {k: v for k, v in os.environ.items()
           if not k.startswith('COMPOSE_') and k not in config.KEYS | config.IMAGES}
    env.update(c)
    env.update(config.images(root / 'versions.env'))
    env['COMPOSE_DISABLE_ENV_FILE'] = '1'
    command = (docker if docker is not None else docker_prefix()) + [
        'compose', '--project-directory', str(root), '--env-file', '/dev/null',
        '-f', str(root / 'compose.yaml')] + args
    return run(command, capture=capture, timeout=timeout, env=env)


def validate_model(model, c):
    expected = {
        'jellyfin': {('127.0.0.1', 8096, 8096, 'tcp')},
        'radarr': {('127.0.0.1', 7878, 7878, 'tcp')},
        'sonarr': {('127.0.0.1', 8989, 8989, 'tcp')},
        'prowlarr': {('127.0.0.1', 9696, 9696, 'tcp')},
        'qbittorrent': {('127.0.0.1', 8081, 8081, 'tcp')},
        'homepage': {('127.0.0.1', 3002, 3000, 'tcp')},
        'seerr': {('127.0.0.1', 5055, 5055, 'tcp')},
        'speedtest': {('127.0.0.1', 3000, 3000, 'tcp')},
    }
    services = model['services']
    if set(services) != set(expected):
        raise ValueError('Unexpected application inventory in compose.yaml')
    hp = services['homepage'].get('environment', {})
    if (hp.get('HOMEPAGE_AUTH_ENABLED') != 'true' or hp.get('HOMEPAGE_ALLOWED_HOSTS') != c['DOMAIN']
            or hp.get('HOMEPAGE_EXTERNAL_URL') != 'https://' + c['DOMAIN']):
        raise ValueError('Homepage must require login, allow only DOMAIN, and use its HTTPS URL')
    for name, service in services.items():
        ports = {(p.get('host_ip'), int(p['published']), int(p['target']), p.get('protocol', 'tcp'))
                 for p in service.get('ports', [])}
        if ports != expected[name]:
            raise ValueError(f'{name}: unexpected port exposure')
        if service.get('privileged') or service.get('network_mode') == 'host':
            raise ValueError(f'{name}: privileged/host networking is prohibited')
        for volume in service.get('volumes', []):
            if 'docker.sock' in volume.get('source', ''):
                raise ValueError(f'{name}: Docker socket exposure is prohibited')


def check(c, root, *, static=False):
    # config rendering needs the CLI, not a running daemon.
    model = json.loads(compose(c, root, ['config', '--no-env-resolution', '--format', 'json'],
                               capture=True, docker=['docker']))
    validate_model(model, c)
    if not static:
        credential_files.load(root)
        for path in [root / 'local/homepage.env', root / 'local/media-credentials'] + [
                Path(c['DATA_ROOT'])/name/'config.xml' for name in ('radarr','sonarr','prowlarr')
                ] + [Path(c['DATA_ROOT'])/'qbittorrent/qBittorrent/qBittorrent.conf']:
            if path.is_symlink() or not path.is_file() or not os.access(path, os.R_OK):
                raise ValueError(f'Missing/unreadable private config: {path.name}; run scripts/setup')
        for path in [Path(c['DATA_ROOT']) / n for n in ['seerr', 'homepage', 'jellyfin', 'jellyfin-cache', 'radarr', 'sonarr', 'prowlarr', 'qbittorrent']] + [Path(c['MEDIA_ROOT'])]:
            if path.is_symlink() or not path.is_dir():
                raise ValueError(f'Missing storage directory: {path}; run scripts/setup')
        for path, uid, gid in [
            (Path(c['DATA_ROOT']) / 'seerr', 1000, 1000),
            (Path(c['DATA_ROOT']) / 'homepage', int(c['RUN_UID']), int(c['RUN_GID'])),
        ]:
            if not config.directory_writable(path, uid, gid):
                raise ValueError(f'Storage is not writable by container UID/GID {uid}:{gid}: {path}; review ownership manually')
        for name in ['jellyfin', 'jellyfin-cache', 'radarr', 'sonarr', 'prowlarr', 'qbittorrent']:
            if not config.directory_writable(Path(c['DATA_ROOT'])/name, int(c['RUN_UID']), int(c['RUN_GID'])):
                raise ValueError(f'{name}: storage is not writable by RUN_UID/RUN_GID; review ownership manually')
        for name in ['', 'downloads', 'downloads/incomplete', 'downloads/complete', 'downloads/complete/movies', 'downloads/complete/tv', 'library', 'library/movies', 'library/tv']:
            path = Path(c['MEDIA_ROOT'])/name
            if path.is_symlink() or not path.is_dir() or not config.directory_writable(path, int(c['RUN_UID']), int(c['RUN_GID'])):
                raise ValueError('Media storage missing or not writable by RUN_UID/RUN_GID; review mount and ownership manually')
    print('Configuration valid' + (' (static only; local storage/secrets not checked)' if static else ''))


def status(c, root):
    data = compose(c, root, ['ps', '--all', '--format', 'json'], capture=True, timeout=30)
    try:
        rows = json.loads(data)
        if isinstance(rows, dict):
            rows = [rows]
    except json.JSONDecodeError:
        rows = [json.loads(line) for line in data.splitlines() if line.strip()]
    by_name = {r['Service']: r for r in rows}
    good = True
    for name, port, path in [('homepage', 3002, '/api/healthcheck'), ('seerr', 5055, '/api/v1/settings/public'),
                              ('speedtest', 3000, '/'),
                              ('jellyfin', 8096, '/health'), ('radarr', 7878, '/'),
                              ('sonarr', 8989, '/'), ('prowlarr', 9696, '/'), ('qbittorrent', 8081, '/')]:
        running = by_name.get(name, {}).get('State') == 'running'
        health = by_name.get(name, {}).get('Health', '')
        http = False
        if running:
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{port}{path}', timeout=5) as response:
                    http = response.status < 400
            except urllib.error.HTTPError as error:
                http = error.code in (401, 403)  # protected page is reachable
            except (OSError, urllib.error.URLError):
                pass
        good = good and running and http and health not in ('unhealthy', 'starting')
        print(f'{name}: container={"running" if running else "stopped/missing"}, '
              f'HTTP={"reachable" if http else "unreachable"}, health={health or "not configured"}')
    print('Seerr owner/media-server configuration and request fulfillment require application verification.')
    print('Public DNS and HTTPS are not established by this check.')
    return 0 if good else 1
