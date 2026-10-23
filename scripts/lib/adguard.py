"""Private initial configuration and isolated Compose operations for AdGuard."""
import base64
import ipaddress
import json
import os
from pathlib import Path
import urllib.error
import urllib.request

import config
import credentials
import host
import runtime


def settings(c):
    try:
        address = ipaddress.IPv4Address(c['ADGUARD_BIND_IP'])
        network = ipaddress.IPv4Network(c['ADGUARD_NETWORK'])
    except (KeyError, ValueError):
        raise ValueError('Set ADGUARD_BIND_IP and ADGUARD_NETWORK to the reserved LAN IPv4 address and subnet') from None
    private = any(network.subnet_of(ipaddress.IPv4Network(n)) for n in
                  ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16'))
    if not private or address not in network or address in (network.network_address, network.broadcast_address):
        raise ValueError('AdGuard requires a usable address inside an RFC1918 LAN subnet')
    return str(address), str(network)


def initial_config(c, password_hash):
    address, network = settings(c)
    names = sorted({c[k] for k in ('DOMAIN', 'HOMEPAGE_HOST', 'REQUESTS_HOST',
                                  'SPEED_HOST', 'JELLYFIN_HOST', 'NAVIDROME_HOST')} |
                   {service+'.'+c['DOMAIN'] for service in
                    ('adguard', 'radarr', 'sonarr', 'prowlarr', 'qbittorrent', 'lidarr', 'bazarr', 'immich', 'maintainerr')})
    return {
        'schema_version': 34,  # Pinned AdGuard v0.107.79 schema.
        'http': {'address': '0.0.0.0:3000'},
        'users': [{'name': 'admin', 'password': password_hash}],
        'dns': {
            'bind_hosts': ['0.0.0.0'], 'port': 1053,
            'allowed_clients': [network],
            'upstream_dns': ['https://dns.cloudflare.com/dns-query'],
            'bootstrap_dns': ['1.1.1.1', '1.0.0.1'],
            'fallback_dns': [], 'use_private_ptr_resolvers': False,
            'hostsfile_enabled': False,
        },
        'filtering': {
            'protection_enabled': True, 'filtering_enabled': True,
            'rewrites': [{'domain': name, 'answer': address, 'enabled': True} for name in names],
        },
        'filters': [{'enabled': True, 'url': 'https://adguardteam.github.io/AdGuardSDNSFilter/Filters/filter.txt',
                     'name': 'AdGuard DNS filter', 'id': 1}],
        'dhcp': {'enabled': False},
        'querylog': {'enabled': True, 'file_enabled': True, 'interval': '24h'},
        'statistics': {'enabled': True, 'interval': '24h'},
    }


def password(root):
    return credentials.read(root/'.env', credentials.DNS_KEYS,
                            ignored=config.KEYS | (credentials.ALL_KEYS - credentials.DNS_KEYS))['ADGUARD_PASSWORD']


def compose(c, root, args, *, capture=False, timeout=60):
    # DNS never needs or receives media/Homepage credentials, even in its environment.
    env = {k:v for k,v in os.environ.items() if not k.startswith('COMPOSE_') and
           k not in config.KEYS | config.IMAGES | credentials.ALL_KEYS | credentials.DERIVED_WIDGET_KEYS}
    values = {k:c[k] for k in ('DATA_ROOT', 'RUN_UID', 'RUN_GID', 'ADGUARD_BIND_IP')}
    values['ADGUARD_IMAGE'] = config.images(root/'versions.env')['ADGUARD_IMAGE']
    values['COMPOSE_DISABLE_ENV_FILE'] = '1'
    env.update(values)
    prefix = runtime.docker_prefix()
    if prefix[:2] == ['sudo', '-n']:
        prefix = prefix[:2]+['--preserve-env='+','.join(sorted(values))]+prefix[2:]
    return runtime.run(prefix+['compose', '--project-directory', str(root), '--env-file', '/dev/null',
                              '-f', str(root/'compose.adguard.yaml')]+args,
                       capture=capture, timeout=timeout, env=env)


def check(c, root):
    settings(c)
    model = json.loads(compose(c, root, ['config', '--format', 'json'], capture=True))
    if set(model['services']) != {'adguard'}:
        raise ValueError('Unexpected service in optional DNS project')
    service = model['services']['adguard']
    ports = {(p['host_ip'], int(p['published']), int(p['target']), p.get('protocol', 'tcp')) for p in service['ports']}
    if ports != {(c['ADGUARD_BIND_IP'], 53, 1053, 'tcp'), (c['ADGUARD_BIND_IP'], 53, 1053, 'udp'),
                 ('127.0.0.1', 3003, 3000, 'tcp')}:
        raise ValueError('Unexpected AdGuard port exposure')
    if service.get('privileged') or service.get('network_mode') == 'host':
        raise ValueError('Privileged/host networking is prohibited')
    if (service.get('user') != c['RUN_UID']+':'+c['RUN_GID'] or
            set(service.get('cap_add', [])) != {'NET_BIND_SERVICE', 'NET_RAW'} or
            set(service.get('cap_drop', [])) != {'ALL'} or
            service.get('environment')):
        raise ValueError('AdGuard must use the configured non-root user, bounded capabilities and no credential environment')
    expected_mounts = {(str(Path(c['DATA_ROOT'])/'adguard'/name), '/opt/adguardhome/'+name)
                       for name in ('conf', 'work')}
    if {(v['source'], v['target']) for v in service.get('volumes', [])} != expected_mounts:
        raise ValueError('Unexpected AdGuard storage mounts')
    print('AdGuard Compose and LAN address configuration valid; router/client DNS unchanged.')


def prepare(c, root):
    check(c, root)
    secret = password(root)  # Validate before creating anything; never rotate an existing account.
    uid, gid = int(c['RUN_UID']), int(c['RUN_GID'])
    base = Path(c['DATA_ROOT'])/'adguard'
    for directory in (base, base/'conf', base/'work'):
        host.ensure_directory(directory, uid, gid)
        if not config.directory_writable(directory, uid, gid):
            raise ValueError('AdGuard storage is not writable by RUN_UID/RUN_GID; review ownership manually')
    target = base/'conf/AdGuardHome.yaml'
    if target.is_symlink():
        raise ValueError('Symlink AdGuard configuration is unsupported')
    if target.exists():
        state = target.stat()
        if not target.is_file() or state.st_mode & 0o077 or state.st_uid != uid:
            raise ValueError('Existing AdGuard config must be a private regular file owned by RUN_UID; review it manually')
        print('Preserving existing AdGuard configuration, accounts, rewrites and filters.')
        return
    try:
        import bcrypt
    except ImportError:
        raise RuntimeError('Initial setup needs distribution package python3-bcrypt') from None
    if len(secret.encode()) > 72:
        raise ValueError('ADGUARD_PASSWORD must be at most 72 UTF-8 bytes for bcrypt')
    if os.geteuid() not in (0, uid):
        raise ValueError('Initial AdGuard setup must run as RUN_UID or root to preserve private configuration ownership')
    hashed = bcrypt.hashpw(secret.encode(), bcrypt.gensalt(rounds=10)).decode()
    created = config.create_file(target, json.dumps(initial_config(c, hashed), indent=2)+'\n')
    if created and os.geteuid() == 0:
        os.chown(target, uid, gid)


def status(c, root):
    secret = password(root)
    token = base64.b64encode(('admin:'+secret).encode()).decode()
    request = urllib.request.Request('http://127.0.0.1:3003/control/status',
                                     headers={'Authorization': 'Basic '+token})
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=10) as response:
            data = json.load(response)
    except (OSError, urllib.error.URLError):
        print('AdGuard authenticated API unavailable; inspect the service locally.')
        return 1
    good = data.get('running') is True and data.get('dns_port') == 1053
    print('AdGuard: authenticated API reachable; DNS '+('running' if good else 'not ready'))
    print('Verify UDP/TCP queries from a LAN device before changing router DHCP DNS.')
    return 0 if good else 1
