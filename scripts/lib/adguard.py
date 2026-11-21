"""Private initial configuration and isolated Compose operations for AdGuard."""
import base64
import ipaddress
import json
import os
import re
from pathlib import Path
import urllib.error
import urllib.request

import config
import credentials
import host
import runtime


# Encrypted upstreams from two independent providers, so one provider's outage
# does not stop LAN DNS. Plain addresses only resolve those resolver hostnames.
UPSTREAMS = ('https://dns.cloudflare.com/dns-query', 'https://dns.quad9.net/dns-query')
BOOTSTRAP = ('1.1.1.1', '1.0.0.1', '9.9.9.9', '149.112.112.112')


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
                    ('adguard', 'radarr', 'sonarr', 'prowlarr', 'qbittorrent', 'lidarr', 'bazarr', 'immich', 'maintainerr', 'bambuddy', 'ntfy')} | {c.get('KUTT_HOST','kutt.'+c['DOMAIN'])})
    return {
        'schema_version': 34,  # Unchanged in pinned AdGuard v0.107.80.
        'http': {'address': '0.0.0.0:3000'},
        'users': [{'name': 'admin', 'password': password_hash}],
        'dns': {
            'bind_hosts': ['0.0.0.0'], 'port': 1053,
            'allowed_clients': [network],
            'upstream_dns': list(UPSTREAMS),
            'bootstrap_dns': list(BOOTSTRAP),
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


def images(root):
    values=config.parse(root/'versions/adguard.env',{'ADGUARD_IMAGE'})
    if not re.fullmatch(r'adguard/adguardhome:v[0-9.]+@sha256:[a-f0-9]{64}',values['ADGUARD_IMAGE']):
        raise ValueError('AdGuard requires an official immutable release image')
    return values


def compose(c, root, args, *, capture=False, timeout=60):
    # DNS never needs or receives media/Homepage credentials, even in its environment.
    env = {k:v for k,v in os.environ.items() if not k.startswith('COMPOSE_') and
           k not in config.KEYS | config.IMAGES | credentials.ALL_KEYS | credentials.DERIVED_WIDGET_KEYS}
    values = {k:c[k] for k in ('DATA_ROOT', 'RUN_UID', 'RUN_GID', 'ADGUARD_BIND_IP')}
    values['ADGUARD_IMAGE'] = images(root)['ADGUARD_IMAGE']
    values['COMPOSE_DISABLE_ENV_FILE'] = '1'
    env.update(values)
    prefix = runtime.docker_prefix()
    if prefix[:2] == ['sudo', '-n']:
        prefix = prefix[:2]+['--preserve-env='+','.join(sorted(values))]+prefix[2:]
    return runtime.run(prefix+['compose', '--project-directory', str(root), '--env-file', '/dev/null',
                              '-f', str(root/'compose/adguard.yaml')]+args,
                       capture=capture, timeout=timeout, env=env)


def stop(c, root, *, allow_dns_outage=False):
    if not allow_dns_outage:
        raise ValueError(
            'Refusing to stop active LAN DNS; deploy/verify a fallback resolver '
            'and rerun scripts/adguard stop --allow-dns-outage for an approved window')
    compose(c, root, ['stop'])
    print('DNS stopped for the explicitly approved outage window; restore with scripts/adguard up and verify from a LAN client.')


def check(c, root):
    settings(c)
    model = json.loads(compose(c, root, ['config', '--format', 'json'], capture=True))
    if set(model['services']) != {'adguard'}:
        raise ValueError('Unexpected service in optional DNS project')
    service = model['services']['adguard']
    if set(service.get('networks',{})) != {'default','media'} or model['networks']['media'].get('name') != 'ohara_default' or model['networks']['media'].get('external') is not True:
        raise ValueError('AdGuard widget requires only its private network and the existing media network')
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


def api(root, path, body=None):
    token = base64.b64encode(('admin:'+password(root)).encode()).decode()
    headers = {'Authorization': 'Basic '+token}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers['Content-Type'] = 'application/json'
    request = urllib.request.Request('http://127.0.0.1:3003/control/'+path, data=data, headers=headers)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=30) as response:
        raw = response.read()
    return json.loads(raw) if raw.strip() else {}


def merged(existing, reviewed):
    """Existing entries in their order, then any reviewed entry still missing."""
    existing = list(existing or [])
    return existing+[item for item in reviewed if item not in existing]


def upstreams(c, root):
    """Add the reviewed upstream/bootstrap entries to a running resolver.

    Uses the live API, so DNS is not restarted. Owner-added entries, fallback
    settings, accounts, rewrites and filters are left as they are.
    """
    try:
        info = api(root, 'dns_info')
        wanted = {'upstream_dns': merged(info.get('upstream_dns'), UPSTREAMS),
                  'bootstrap_dns': merged(info.get('bootstrap_dns'), BOOTSTRAP)}
        if all(info.get(key) == value for key, value in wanted.items()):
            print('AdGuard upstreams already include the reviewed providers; nothing changed.')
            return 0
        if not all(u.startswith(('https://', 'tls://', 'quic://', 'h3://', 'sdns://', '[/', '#'))
                   for u in wanted['upstream_dns']):
            raise ValueError('Existing AdGuard upstreams include a plaintext resolver; review them in the dashboard')
        tested = api(root, 'test_upstream_dns', dict(wanted, fallback_dns=info.get('fallback_dns') or [],
                                                     private_upstream=info.get('local_ptr_upstreams') or []))
        failed = sorted(name for name, result in tested.items() if result != 'OK')
        if failed:
            raise ValueError('AdGuard upstream test failed for '+', '.join(failed)+'; nothing changed')
        api(root, 'dns_config', wanted)
        applied = api(root, 'dns_info')
    except (OSError, urllib.error.URLError):
        print('AdGuard authenticated API unavailable; inspect the service locally.')
        return 1
    if any(applied.get(key) != value for key, value in wanted.items()):
        raise ValueError('AdGuard did not report the requested upstreams; review the dashboard')
    print('AdGuard upstreams: '+', '.join(applied['upstream_dns']))
    print('Verify UDP/TCP queries from a LAN device.')
    return 0


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
