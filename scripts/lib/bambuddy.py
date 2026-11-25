"""Optional Bambuddy lifecycle. Printer access and owner setup stay in its UI."""

import datetime
import ipaddress
import json
from pathlib import Path

import adguard
import config
import homepage_services
import host
import media
import runtime


def settings(c):
    base = Path(c.get('BAMBUDDY_ROOT', str(Path(c['DATA_ROOT']) / 'bambuddy')))
    expected = Path(c.get('BAMBUDDY_MOUNT', '/'))
    for path in (base, expected):
        if (str(path) != '/' and not config.PATH.fullmatch(str(path))) or '..' in path.parts:
            raise ValueError('Bambuddy requires safe absolute storage paths')
        if any(p.is_symlink() for p in (path, *path.parents)):
            raise ValueError('Bambuddy storage must not use symlinks')
    if base == Path('/') or expected not in base.parents:
        raise ValueError('BAMBUDDY_ROOT must be below BAMBUDDY_MOUNT')
    protected = [Path(c['MEDIA_ROOT']), Path(c['DATA_ROOT']) / 'media'] + [
        Path(c['DATA_ROOT']) / n
        for n in (
            'jellyfin',
            'jellyfin-cache',
            'homepage',
            'seerr',
            'immich',
            'radarr',
            'sonarr',
            'lidarr',
            'bazarr',
            'prowlarr',
            'navidrome',
            'qbittorrent',
            'adguard',
            'maintainerr',
        )
    ]
    if any(base == p or base in p.parents or p in base.parents for p in protected):
        raise ValueError('Bambuddy storage must be separate from other applications and media')
    return base, expected


def images(root):
    return config.pinned_images(
        root / 'versions/bambuddy.env',
        {'BAMBUDDY_IMAGE'},
        r'ghcr.io/maziggy/bambuddy:[0-9.]+',
        'Bambuddy requires an official immutable release image',
    )


def require_storage(c, *, directories=True):
    base, expected = settings(c)
    result = runtime.filesystems_holding(base)[0]
    if result['target'] != str(expected) or result['fstype'] not in runtime.LOCAL_FILESYSTEMS:
        raise ValueError('Bambuddy storage is not on the expected local Linux filesystem')
    if directories:
        for p in (base / 'data', base / 'logs'):
            if (
                p.is_symlink()
                or not p.is_dir()
                or not config.directory_writable(p, int(c['RUN_UID']), int(c['RUN_GID']))
            ):
                raise ValueError(
                    'Run scripts/bambuddy prepare; review existing storage ownership manually'
                )


def proxy_gateway(docker, *, project='ohara-bambuddy'):
    """Trust only the host gateway of this app's own Compose bridge."""
    name = project + '_default'
    try:
        rows = json.loads(runtime.run(docker + ['network', 'inspect', name], capture=True))
    except RuntimeError:
        runtime.run(
            docker
            + [
                'network',
                'create',
                '--label',
                'com.docker.compose.project=' + project,
                '--label',
                'com.docker.compose.network=default',
                name,
            ]
        )
        rows = json.loads(runtime.run(docker + ['network', 'inspect', name], capture=True))
    if (
        len(rows) != 1
        or rows[0].get('Driver') != 'bridge'
        or rows[0].get('Labels', {}).get('com.docker.compose.project') != project
        or rows[0].get('Labels', {}).get('com.docker.compose.network') != 'default'
    ):
        raise ValueError('Bambuddy network is not its owned Compose bridge')
    addresses = []
    for subnet in rows[0].get('IPAM', {}).get('Config', []):
        try:
            address = ipaddress.ip_address(subnet.get('Gateway', ''))
        except ValueError:
            continue
        if address.version == 4:
            if not any(
                address in ipaddress.ip_network(n)
                for n in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16')
            ):
                raise ValueError('Bambuddy requires a private IPv4 Docker gateway')
            addresses.append(str(address))
    if len(addresses) != 1:
        raise ValueError('Bambuddy requires one verified IPv4 proxy gateway')
    return addresses[0]


def compose(c, root, args, *, capture=False, timeout=60):
    starting = runtime.starts_containers(args)
    if starting:
        require_storage(c)
    base, _ = settings(c)
    values = {k: c[k] for k in ('RUN_UID', 'RUN_GID', 'TZ')}
    values['BAMBUDDY_ROOT'] = str(base)
    values.update(images(root))
    prefix = runtime.project_prefix(args)
    values['BAMBUDDY_PROXY_IP'] = proxy_gateway(prefix) if starting else '127.0.0.1'
    return runtime.project_compose(
        root, 'compose/bambuddy.yaml', values, args, prefix=prefix, capture=capture, timeout=timeout
    )


def check(c, root, *, static=False):
    base, _ = settings(c)
    model = json.loads(compose(c, root, ['config', '--format', 'json'], capture=True))
    if model.get('name') != 'ohara-bambuddy' or set(model['services']) != {'bambuddy'}:
        raise ValueError('Unexpected Bambuddy project inventory')
    s = model['services']['bambuddy']
    mounts = {
        (v.get('source'), v['target'], v.get('read_only', False)) for v in s.get('volumes', [])
    }
    ports = {(p.get('host_ip'), int(p['published']), int(p['target'])) for p in s.get('ports', [])}
    if (
        s['image'] != images(root)['BAMBUDDY_IMAGE']
        or s.get('user') != c['RUN_UID'] + ':' + c['RUN_GID']
        or s.get('privileged')
        or s.get('network_mode') == 'host'
        or ports != {('127.0.0.1', 8008, 8000)}
        or mounts
        != {(str(base / 'data'), '/app/data', False), (str(base / 'logs'), '/app/logs', False)}
        or set(s.get('environment', {}))
        != {
            'TZ',
            'HOST',
            'PORT',
            'DATA_DIR',
            'LOG_DIR',
            'DEBUG',
            'LOG_LEVEL',
            'TRUSTED_PROXY_IPS',
            'FORWARDED_ALLOW_IPS',
        }
        or s.get('environment', {}).get('TRUSTED_PROXY_IPS') != '127.0.0.1'
        or s.get('environment', {}).get('FORWARDED_ALLOW_IPS') != '127.0.0.1'
        or s.get('cap_drop') != ['ALL']
        or s.get('cap_add') != ['NET_BIND_SERVICE']
        or 'no-new-privileges:true' not in s.get('security_opt', [])
    ):
        raise ValueError(
            'Bambuddy must keep dedicated state, non-root execution and only its loopback web port'
        )
    if any(v.get('bind', {}).get('create_host_path', False) for v in s['volumes']):
        raise ValueError('Bambuddy must not auto-create storage')
    if not static:
        require_storage(c)
    print('Bambuddy configuration valid' + (' (static only)' if static else ''))


def prepare(c, root):
    check(c, root, static=True)
    require_storage(c, directories=False)
    base, _ = settings(c)
    for p in (base, base / 'data', base / 'logs'):
        host.ensure_directory(p, int(c['RUN_UID']), int(c['RUN_GID']), 0o700)
    check(c, root)


def client():
    return media.Client('http://127.0.0.1:8008')


def status():
    api = client()
    if api.call('/health').get('status') != 'healthy':
        raise ValueError('Bambuddy health check failed')
    state = api.call('/api/v1/auth/status')
    print(
        'Bambuddy healthy; owner setup '
        + ('pending' if state['requires_setup'] else 'completed')
        + '; authentication '
        + ('enabled' if state['auth_enabled'] else 'disabled')
    )
    print('Printer connection, camera and real printing require owner UI verification.')


def homepage(c, root):
    path, before, data = homepage_services.read(c)
    if homepage_services.cards(data, 'Bambuddy'):
        print('Existing Bambuddy Homepage card preserved')
        return
    homepage_services.group(data, '3D Print').append(
        {
            'Bambuddy': {
                'icon': 'mdi-printer-3d',
                'href': 'https://bambuddy.' + c['DOMAIN'],
                'description': 'Bambu Lab A1 mini',
            }
        }
    )
    homepage_services.backup(
        root
        / 'local/bambuddy-backups'
        / datetime.datetime.now().strftime('%Y%m%d-%H%M%S-homepage'),
        before,
    )
    path.write_text(homepage_services.dump(data))
    print('Bambuddy Homepage card merged; existing cards and widgets preserved')


def dns(c, root):
    adguard.ensure_rewrite(
        c,
        root,
        'bambuddy.' + c['DOMAIN'],
        'Conflicting Bambuddy DNS rewrite; preserve and review',
    )
    print('Exact Bambuddy LAN DNS rewrite present; other records preserved')


def widget_config(domain, printer_id):
    """Only a placeholder is persisted; credentials stay in Homepage's environment."""
    if type(printer_id) is not int or printer_id < 1:
        raise ValueError('Invalid Bambuddy printer ID')
    profile = {
        'type': 'customapi',
        'url': f'https://bambuddy.{domain}/api/v1/printers/{printer_id}/status',
        'headers': {'X-API-Key': '{{HOMEPAGE_VAR_BAMBUDDY_API_KEY}}'},
        'refreshInterval': 15000,
        'display': 'list',
        'mappings': [
            {
                'field': 'connected',
                'label': 'Connection',
                'remap': [{'value': True, 'to': 'Online'}, {'value': False, 'to': 'Offline'}],
            },
            {'field': 'state', 'label': 'State', 'remap': [{'value': None, 'to': 'Unknown'}]},
            {'field': 'progress', 'label': 'Progress', 'suffix': '%'},
            {'field': 'temperatures.nozzle', 'label': 'Nozzle', 'suffix': '°C'},
            {'field': 'temperatures.bed', 'label': 'Bed', 'suffix': '°C'},
            {'field': 'remaining_time', 'label': 'Remaining', 'suffix': 'min'},
        ],
    }
    for mapping in profile['mappings'][2:]:
        mapping['remap'] = [{'value': None, 'to': '—'}]
    return profile


def widget(c, root):
    """Install a status-only widget after an owner supplies an application key."""
    import credentials

    homepage_credentials, _ = credentials.load(root)
    key = homepage_credentials.get('HOMEPAGE_VAR_BAMBUDDY_API_KEY')
    if not key:
        raise ValueError(
            'Save a Bambuddy Read Status-only key as HOMEPAGE_VAR_BAMBUDDY_API_KEY in private .env first'
        )
    api = media.Client('http://127.0.0.1:8008', key)
    printers = api.call('/api/v1/printers/')
    if not isinstance(printers, list) or len(printers) != 1:
        raise ValueError('Restrict the Homepage API key to exactly one printer in Bambuddy')
    printer_id = printers[0].get('id')
    profile = widget_config(c['DOMAIN'], printer_id)
    status = api.call(f'/api/v1/printers/{printer_id}/status')
    if not isinstance(status, dict) or not isinstance(status.get('connected'), bool):
        raise ValueError('Bambuddy returned an unsupported printer status')
    path, before, data = homepage_services.read(c)
    cards = homepage_services.cards(data, 'Bambuddy')
    if len(cards) != 1:
        raise ValueError('Expected exactly one existing Bambuddy Homepage card; run homepage first')
    if cards[0].get('widgets'):
        raise ValueError('Existing multiple Bambuddy widgets require manual review')
    cards[0]['widget'] = profile
    after = homepage_services.dump(data)
    if after != before:
        homepage_services.backup(
            root
            / 'local/bambuddy-backups'
            / datetime.datetime.now().strftime('%Y%m%d-%H%M%S-widget'),
            before,
        )
        path.write_text(after)
    print('Bambuddy status widget configured; recreate Homepage to load its allowlisted key')
