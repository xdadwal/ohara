"""Optional private ntfy server and explicit host integrations; no secret generation."""
import base64
import datetime
import json
import os
from pathlib import Path
import re
import socket
import urllib.error
import urllib.request

import config
import credentials
import host
import runtime

TOPIC = 'ohara-alerts'
USER = 'ohara'
BASE = 'http://127.0.0.1:2586'


def settings(c):
    name = c.get('NTFY_HOST', 'ntfy.'+c['DOMAIN'])
    if not config.HOST.fullmatch(name) or name != 'ntfy.'+c['DOMAIN']:
        raise ValueError('NTFY_HOST must be ntfy.DOMAIN')
    if name in {c[k] for k in ['HOMEPAGE_HOST', 'REQUESTS_HOST', 'SPEED_HOST', 'JELLYFIN_HOST', 'NAVIDROME_HOST']}:
        raise ValueError('ntfy hostname overlaps another service')
    base = Path(c.get('NTFY_ROOT', str(Path(c['DATA_ROOT'])/'ntfy')))
    mount = Path(c.get('NTFY_MOUNT', '/'))
    for p in [base, mount]:
        if (str(p) != '/' and not config.PATH.fullmatch(str(p))) or '..' in p.parts or '//' in str(p):
            raise ValueError('ntfy requires safe absolute storage paths')
        if any(x.is_symlink() for x in [p, *p.parents]):
            raise ValueError('Symlink ntfy storage is unsupported')
    protected = [Path(c['MEDIA_ROOT']), Path(c['DATA_ROOT'])/'media'] + [Path(c['DATA_ROOT'])/n for n in
                 ['homepage','seerr','jellyfin','jellyfin-cache','navidrome','radarr','sonarr','lidarr',
                  'bazarr','prowlarr','qbittorrent','adguard','immich','bambuddy','maintainerr']]
    if base == Path('/') or mount not in base.parents or any(base == p or base in p.parents or p in base.parents for p in protected):
        raise ValueError('ntfy storage must be separate from application/media storage and below its mount')
    relay = c.get('NTFY_IOS_RELAY', 'none')
    if relay not in {'none', 'https://ntfy.sh'}:
        raise ValueError('NTFY_IOS_RELAY must be none or explicitly approved https://ntfy.sh')
    return name, base, mount, relay


def password(root):
    value = credentials.read(root/'.env', credentials.NTFY_KEYS,
                             ignored=config.KEYS | (credentials.ALL_KEYS-credentials.NTFY_KEYS))['NTFY_PASSWORD']
    if len(value.encode()) > 72:
        raise ValueError('NTFY_PASSWORD must be at most 72 UTF-8 bytes for bcrypt')
    return value


def images(root):
    d = config.parse(root/'versions.ntfy.env', {'NTFY_IMAGE'})
    if not re.fullmatch(r'binwiederhier/ntfy:v[0-9.]+@sha256:[a-f0-9]{64}', d['NTFY_IMAGE']):
        raise ValueError('ntfy requires the official immutable release image')
    return d


def storage(c, directories=True):
    _, base, expected, _ = settings(c)
    p = base
    while not p.exists():
        p = p.parent
    rows = json.loads(runtime.run(['findmnt','--json','--target',str(p),'-o','TARGET,FSTYPE'], capture=True))['filesystems']
    if len(rows) != 1 or rows[0]['target'] != str(expected) or rows[0]['fstype'] not in {'ext4','xfs','btrfs','zfs'}:
        raise ValueError('ntfy must use the verified independent local filesystem')
    if directories:
        for p in [base/'config', base/'data']:
            if p.is_symlink() or not p.is_dir() or not config.directory_writable(p, int(c['RUN_UID']), int(c['RUN_GID'])):
                raise ValueError('Run scripts/ntfy prepare and verify existing ownership')


def compose(c, root, args, capture=False, timeout=60):
    if any(a in {'up','start','restart','create','run'} for a in args):
        storage(c)
    _, base, _, _ = settings(c)
    values = {k:c[k] for k in ['TZ','RUN_UID','RUN_GID']}
    values.update(NTFY_ROOT=str(base), COMPOSE_DISABLE_ENV_FILE='1', **images(root))
    env = {k:v for k,v in os.environ.items() if k in
           {'PATH','HOME','USER','XDG_RUNTIME_DIR','DOCKER_CONFIG','DOCKER_HOST','DOCKER_CONTEXT','SSH_AUTH_SOCK'}}
    env.update(values)
    prefix = ['docker'] if args[0] == 'config' else runtime.docker_prefix()
    if prefix[:2] == ['sudo','-n']:
        prefix = prefix[:2]+['--preserve-env='+','.join(sorted(values))]+prefix[2:]
    return runtime.run(prefix+['compose','--project-directory',str(root),'--env-file','/dev/null',
                              '-f',str(root/'compose.ntfy.yaml'),*args], env=env, capture=capture, timeout=timeout)


def check(c, root, static=False):
    settings(c)
    d = json.loads(compose(c, root, ['config','--format','json'], capture=True))
    if d.get('name') != 'ohara-ntfy' or set(d['services']) != {'ntfy'}:
        raise ValueError('Unexpected ntfy project inventory')
    s = d['services']['ntfy']
    if s.get('privileged') or s.get('network_mode') == 'host' or s.get('user') != c['RUN_UID']+':'+c['RUN_GID']:
        raise ValueError('ntfy requires unprivileged bridge networking and configured non-root identity')
    if {(p.get('host_ip'),str(p['published']),p['target'],p.get('protocol','tcp')) for p in s['ports']} != {('127.0.0.1','2586',8080,'tcp')}:
        raise ValueError('ntfy backend must be loopback only')
    _, base, _, _ = settings(c)
    mounts = {(v['source'],v['target'],v.get('read_only',False)) for v in s['volumes']}
    if mounts != {(str(base/'config'),'/etc/ntfy',True),(str(base/'data'),'/var/lib/ntfy',False)}:
        raise ValueError('Unexpected ntfy mounts')
    if set(s.get('environment',{})) != {'TZ'} or set(s.get('cap_drop',[])) != {'ALL'} or s.get('cap_add') or 'no-new-privileges:true' not in s.get('security_opt',[]):
        raise ValueError('ntfy credential/capability isolation changed')
    if not static:
        password(root); storage(c)
        server = read_server(base/'config/server.yml')
        if server.get('auth-default-access') != 'deny-all' or server.get('enable-signup') is not False:
            raise ValueError('Existing ntfy configuration is not private')
    print('ntfy configuration valid'+(' (static)' if static else ''))


def read_server(path):
    if path.is_symlink():
        raise ValueError('Symlink ntfy server configuration refused')
    import yaml
    return yaml.safe_load(path.read_text())


def prepare(c, root):
    check(c, root, static=True)
    secret = password(root)
    storage(c, directories=False)
    _, base, _, relay = settings(c)
    uid, gid = int(c['RUN_UID']), int(c['RUN_GID'])
    for p in [base, base/'config', base/'data']:
        host.ensure_directory(p,uid,gid,0o700)
        if not config.directory_writable(p,uid,gid):
            raise ValueError('Existing ntfy directory ownership requires review')
    dest = base/'config/server.yml'
    if dest.exists() or dest.is_symlink():
        read_server(dest)
        print('Preserved existing ntfy settings and account state; input changes do not rotate accounts')
        return
    import bcrypt
    name, _, _, _ = settings(c)
    d = {'base-url':'https://'+name, 'listen-http':':8080', 'cache-file':'/var/lib/ntfy/cache.db',
         'cache-duration':'24h','auth-file':'/var/lib/ntfy/auth.db','auth-default-access':'deny-all',
         'auth-users':[USER+':'+bcrypt.hashpw(secret.encode(),bcrypt.gensalt()).decode()+':user'],
         'auth-access':[USER+':'+TOPIC+':rw'], 'enable-login':True, 'enable-signup':False,
         'enable-reservations':False, 'behind-proxy':True, 'log-level':'info'}
    if relay != 'none':
        d['upstream-base-url'] = relay
    config.create_file(dest,json.dumps(d,indent=2)+'\n',0o600)
    if os.geteuid() == 0:
        os.chown(dest,uid,gid)
    print('Private ntfy configuration prepared; only a password hash is stored in its configuration')


def request(path, root=None, data=None, headers=None):
    h = dict(headers or {})
    if root is not None:
        h['Authorization'] = 'Basic '+base64.b64encode((USER+':'+password(root)).encode()).decode()
    req = urllib.request.Request(BASE+path, data=data, headers=h)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req,timeout=5) as r:
            return r.status,r.read(131072)
    except urllib.error.HTTPError as e:
        return e.code,b''
    except OSError:
        raise RuntimeError('ntfy backend unreachable') from None


def status(c, root):
    code, data = request('/v1/health')
    if code != 200 or json.loads(data).get('healthy') is not True:
        raise ValueError('ntfy health failed')
    if request('/'+TOPIC+'/json?poll=1')[0] not in (401,403):
        raise ValueError('Anonymous topic reads are not denied')
    if request('/'+TOPIC,data=b'Anonymous access verification; publication must be denied.')[0] not in (401,403):
        raise ValueError('Anonymous topic writes are not denied')
    if request('/'+TOPIC+'/json?poll=1',root)[0] != 200:
        raise ValueError('Supplied ntfy account cannot read its topic')
    print('ntfy healthy; topic authentication verified; phone delivery needs subscriber verification')


def test(c, root):
    status(c,root)
    code,_ = request('/'+TOPIC,root,b'Ohara test notification: server-side publishing is working.',
                     {'Title':'Ohara notification test','Tags':'white_check_mark'})
    if code != 200:
        raise ValueError('ntfy test publish failed')
    print('Test notification accepted; confirm it arrived on the subscribed phone')


def homepage(c, root):
    import yaml
    import jellyfin_theme
    path = jellyfin_theme.safe(Path(c['DATA_ROOT'])/'homepage/services.yaml')
    before = path.read_text(); d = yaml.safe_load(before)
    if any('ntfy' in row for group in d for rows in group.values() for row in rows):
        print('Existing ntfy Homepage card preserved');return
    group = next((g['Utility'] for g in d if 'Utility' in g),None)
    if group is None:
        group=[];d.append({'Utility':group})
    group.append({'ntfy':{'icon':'ntfy.png','href':'https://'+settings(c)[0], 'description':'Server notifications'}})
    backup = root/'local/ntfy-backups'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    backup.mkdir(parents=True,mode=0o700);config.create_file(backup/'services.yaml',before)
    path.write_text(yaml.safe_dump(d,sort_keys=False,allow_unicode=True))
    print('ntfy Homepage card merged; prior cards/widgets preserved')


def dns(c, root):
    import adguard
    import media
    name = settings(c)[0];address,_ = adguard.settings(c)
    api = media.Client('http://127.0.0.1:3003')
    api.headers['Authorization']='Basic '+base64.b64encode(('admin:'+adguard.password(root)).encode()).decode()
    matches=[r for r in api.call('/control/rewrite/list') if r['domain']==name]
    if matches and not all(r['answer']==address and r.get('enabled',True) for r in matches):
        raise ValueError('Conflicting ntfy DNS rewrite; preserve and inspect')
    if not matches:api.call('/control/rewrite/add',{'domain':name,'answer':address})
    print('Exact ntfy LAN DNS rewrite verified; other records preserved')
