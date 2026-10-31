"""Optional private ntfy server and explicit host integrations; no secret generation."""
import base64
import datetime
import json
import os
from pathlib import Path
import re
import socket
import urllib.error
import urllib.parse
import urllib.request

import config
import credentials
import host
import runtime

TOPIC = 'ohara-alerts'
USER = 'admin'
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
    options = config.parse(root/'.env', {'NTFY_ALLOW_SHORT_PASSWORD'}, {'NTFY_ALLOW_SHORT_PASSWORD'},
                           (config.KEYS-{'NTFY_ALLOW_SHORT_PASSWORD'}) | credentials.ALL_KEYS)
    flag = options.get('NTFY_ALLOW_SHORT_PASSWORD', 'false')
    if flag not in {'true', 'false'}:
        raise ValueError('NTFY_ALLOW_SHORT_PASSWORD must be true or false')
    value = credentials.read(root/'.env', credentials.NTFY_KEYS,
                             ignored=config.KEYS | (credentials.ALL_KEYS-credentials.NTFY_KEYS),
                             minimum_lengths={'NTFY_PASSWORD':1} if flag == 'true' else None)['NTFY_PASSWORD']
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


def rename_database(db, old='ohara', new='admin'):
    """Offline v2.35 account rename only; preserve ID and all related records."""
    columns={r[1] for r in db.execute('PRAGMA table_info(user)')}
    if not {'id','user','pass','role','provisioned'} <= columns:
        raise ValueError('Unknown ntfy auth schema; inspect without changing it')
    source=db.execute('SELECT id,role FROM user WHERE user=?',(old,)).fetchall()
    target=db.execute('SELECT id,role FROM user WHERE user=?',(new,)).fetchall()
    if len(source)==1 and not target:
        db.execute('UPDATE user SET user=? WHERE id=? AND user=?',(new,source[0][0],old))
        return source[0]
    if not source and len(target)==1:
        return target[0]
    raise ValueError('Ambiguous ntfy account state; preserve both accounts and inspect')


def rotate_account(c,root):
    """Explicit owner-authorized offline rename/password update, with rollback."""
    import bcrypt
    from contextlib import closing
    import sqlite3
    import tempfile
    if os.geteuid()!=0:
        raise ValueError('Use sudo scripts/ntfy rotate-account after pausing alert timer/worker')
    for unit in ['ohara-alerts.timer','ohara-alerts.service']:
        if runtime.run(['systemctl','show',unit,'-p','ActiveState','--value'],capture=True).strip() == 'active':
            raise ValueError('Pause ohara-alerts.timer and its worker before account rotation')
    secret=password(root)
    storage(c)
    if not images(root)['NTFY_IMAGE'].startswith('binwiederhier/ntfy:v2.35.0@'):
        raise ValueError('Offline rename requires review against this ntfy version')
    _,base,_,_=settings(c)
    server=base/'config/server.yml';database=base/'data/auth.db'
    if database.is_symlink() or not database.is_file():raise ValueError('Expected private ntfy auth database')
    before=server.read_bytes();owner=server.stat()
    d=read_server(server)
    entries=[x for x in d.get('auth-users',[]) if x.split(':',1)[0] in {'ohara',USER}]
    if len(entries)!=1:raise ValueError('Expected one configured old/new ntfy account; preserve and inspect')
    backup=Path('/var/backups/ohara')/('ntfy-account-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    backup.mkdir(parents=True,mode=0o700)
    config.create_file(backup/'server.yml',before.decode(),0o600)
    compose(c,root,['stop'])
    # A clean server stop avoids concurrent writers and closes SQLite WAL handles.
    with closing(sqlite3.connect(database)) as db,closing(sqlite3.connect(backup/'auth.db')) as saved:
        db.backup(saved)
    (backup/'auth.db').chmod(0o600)
    try:
        with closing(sqlite3.connect(database)) as db:
            account_id,role=rename_database(db)
            if role not in {'user','admin'}:raise ValueError('Unexpected account role')
            db.commit()
            db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        rewritten=[]
        for entry in d['auth-users']:
            if entry.split(':',1)[0] in {'ohara',USER}:
                entry=USER+':'+bcrypt.hashpw(secret.encode(),bcrypt.gensalt()).decode()+':'+role
            rewritten.append(entry)
        d['auth-users']=rewritten
        for key in ['auth-access','auth-tokens']:
            if key in d:
                d[key]=[USER+entry[len('ohara'):] if entry.startswith('ohara:') else entry for entry in d[key]]
        fd,name=tempfile.mkstemp(prefix='.ntfy-account-',dir=server.parent)
        try:
            with os.fdopen(fd,'w') as f:
                json.dump(d,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
            os.chmod(name,owner.st_mode&0o777);os.chown(name,owner.st_uid,owner.st_gid)
            os.replace(name,server)
        finally:
            if os.path.exists(name):os.unlink(name)
        compose(c,root,['up','-d','--wait','--wait-timeout','90'],timeout=180)
        status(c,root)
        with closing(sqlite3.connect('file:'+str(database)+'?mode=ro',uri=True)) as db:
            row=db.execute('SELECT id,role FROM user WHERE user=?',(USER,)).fetchone()
            if row!=(account_id,role):raise ValueError('Account identity/role changed unexpectedly')
        if request('/'+TOPIC+'/json?poll=1',data=None,headers={'Authorization':'Basic '+base64.b64encode(('ohara:'+secret).encode()).decode()})[0] not in (401,403):
            raise ValueError('Old username unexpectedly accepted')
    except Exception:
        compose(c,root,['stop'])
        with closing(sqlite3.connect(backup/'auth.db')) as saved,closing(sqlite3.connect(database)) as db:saved.backup(db)
        server.write_bytes(before);os.chown(server,owner.st_uid,owner.st_gid);server.chmod(owner.st_mode&0o777)
        compose(c,root,['up','-d','--wait','--wait-timeout','90'],timeout=180)
        raise RuntimeError('ntfy account rotation failed; original auth state restored; inspect privately') from None
    print('ntfy username/password updated; account ID/role, permissions and cached messages preserved')
    print('Private rollback backup: '+str(backup))


READER='homepage-reader'


def reader_password(root):
    value=credentials.read(root/'.env',credentials.NTFY_WIDGET_KEYS,
        ignored=config.KEYS | (credentials.ALL_KEYS-credentials.NTFY_WIDGET_KEYS))['NTFY_HOMEPAGE_PASSWORD']
    if len(value.encode())>72:raise ValueError('NTFY_HOMEPAGE_PASSWORD must be at most 72 UTF-8 bytes')
    if value==password(root):raise ValueError('Homepage reader must have an independent password')
    return value


def reader_config(server, secret):
    """Add one bounded reader; preserve all publisher accounts/preferences."""
    import copy
    import bcrypt
    d=copy.deepcopy(server)
    if d.get('auth-default-access')!='deny-all' or d.get('enable-signup') is not False:
        raise ValueError('Private ntfy defaults required before widget setup')
    entries=[x for x in d.get('auth-users',[]) if x.split(':',1)[0]==READER]
    acls=[x for x in d.get('auth-access',[]) if x.split(':',1)[0]==READER]
    if entries:
        if len(entries)!=1 or entries[0].rsplit(':',1)[-1]!='user' or acls!=[READER+':'+TOPIC+':ro']:
            raise ValueError('Existing reader role/ACL differs; preserve and review')
        if not bcrypt.checkpw(secret.encode(),entries[0].split(':')[1].encode()):
            raise ValueError('Existing reader password differs; do not rotate implicitly')
    else:
        if acls:raise ValueError('Unowned reader ACL requires review')
        d.setdefault('auth-users',[]).append(READER+':'+bcrypt.hashpw(secret.encode(),bcrypt.gensalt()).decode()+':user')
        d.setdefault('auth-access',[]).append(READER+':'+TOPIC+':ro')
    return d


def verify_reader(secret):
    h={'Authorization':'Basic '+base64.b64encode((READER+':'+secret).encode()).decode()}
    if request('/'+TOPIC+'/json?poll=1',headers=h)[0]!=200:
        raise ValueError('Reader cannot read its allowed topic')
    if request('/'+TOPIC,data=b'Read-only permission verification',headers=h)[0]!=403:
        raise ValueError('Reader publication must be forbidden')
    if request('/ohara-widget-denied-probe/json?poll=1',headers=h)[0]!=403:
        raise ValueError('Reader must not read unrelated topics')


def widget_profile(c):
    return {'type':'ntfy','url':'https://'+settings(c)[0],'topic':TOPIC,
            'username':READER,'password':'{{HOMEPAGE_VAR_NTFY_PASSWORD}}',
            'fields':['title','message','priority','lastReceived']}


def widget(c,root):
    """Provision the supplied private reader and selectively merge its widget."""
    import sqlite3
    from contextlib import closing
    import tempfile
    import yaml
    import jellyfin_theme
    if os.geteuid()!=0:raise ValueError('Use sudo scripts/ntfy widget')
    secret=reader_password(root)
    status(c,root);storage(c)
    _,base,_,_=settings(c)
    server=base/'config/server.yml';database=base/'data/auth.db'
    if database.is_symlink() or not database.is_file():raise ValueError('Existing ntfy auth database required')
    before=server.read_bytes();owner=server.stat()
    existing=read_server(server)
    if not any(x.split(':',1)[0]==READER for x in existing.get('auth-users',[])):
        with closing(sqlite3.connect('file:'+str(database)+'?mode=ro',uri=True)) as db:
            if db.execute('SELECT id FROM user WHERE user=?',(READER,)).fetchone():
                raise ValueError('Unmanaged existing reader account; preserve and review')
    desired=reader_config(existing,secret)
    path=jellyfin_theme.safe(Path(c['DATA_ROOT'])/'homepage/services.yaml')
    original=path.read_text();data=yaml.safe_load(original)
    cards=[entry['ntfy'] for group in data for rows in group.values() for entry in rows if 'ntfy' in entry]
    if len(cards)!=1:raise ValueError('Run scripts/ntfy homepage first; exactly one ntfy card is required')
    if cards[0].get('widgets') or (cards[0].get('widget') and cards[0]['widget']!=widget_profile(c)):
        raise ValueError('Existing ntfy widget differs; preserve and review')
    cards[0]['widget']=widget_profile(c)
    backup=Path('/var/backups/ohara')/('ntfy-widget-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    backup.mkdir(parents=True,mode=0o700)
    config.create_file(backup/'server.yml',before.decode(),0o600)
    config.create_file(backup/'services.yaml',original,0o600)
    changed=desired!=read_server(server)
    if changed:
        compose(c,root,['stop'])
        with closing(sqlite3.connect(database)) as db,closing(sqlite3.connect(backup/'auth.db')) as saved:db.backup(saved)
        (backup/'auth.db').chmod(0o600)
    try:
        if changed:
            fd,name=tempfile.mkstemp(prefix='.ntfy-reader-',dir=server.parent)
            try:
                with os.fdopen(fd,'w') as f:
                    json.dump(desired,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
                os.chmod(name,owner.st_mode&0o777);os.chown(name,owner.st_uid,owner.st_gid);os.replace(name,server)
            finally:
                if os.path.exists(name):os.unlink(name)
            compose(c,root,['up','-d','--wait','--wait-timeout','90'],timeout=180)
        verify_reader(secret);status(c,root)
        path.write_text(yaml.safe_dump(data,sort_keys=False,allow_unicode=True))
        runtime.compose(c,root,['up','-d','--no-deps','--wait','--wait-timeout','90','homepage'],timeout=180)
        verify_homepage_widget(c,root,secret)
    except Exception:
        if changed:
            compose(c,root,['stop'])
            with closing(sqlite3.connect(backup/'auth.db')) as saved,closing(sqlite3.connect(database)) as db:saved.backup(db)
            server.write_bytes(before);os.chown(server,owner.st_uid,owner.st_gid);server.chmod(owner.st_mode&0o777)
            compose(c,root,['up','-d','--wait','--wait-timeout','90'],timeout=180)
        path.write_text(original)
        raise RuntimeError('ntfy widget setup failed; previous account/config/card restored; inspect privately') from None
    print('ntfy read-only widget configured; Homepage recreated; authenticated widget response and credential exclusion verified')
    print('Private rollback backup: '+str(backup))


def verify_homepage_widget(c,root,secret):
    import media
    api=media.Client('https://'+c['HOMEPAGE_HOST'])
    values,_=credentials.load(root)
    csrf=api.call('/api/auth/csrf')['csrfToken']
    login=api.call('/api/auth/callback/credentials',{'csrfToken':csrf,
        'password':values['HOMEPAGE_AUTH_PASSWORD'],'callbackUrl':'https://'+c['HOMEPAGE_HOST'],'json':'true'},form=True)
    if 'error' in login.get('url',''):raise ValueError('Homepage login failed')
    groups=api.call('/api/services')
    if secret in json.dumps(groups):raise ValueError('Reader credential leaked through browser service configuration')
    cards=[(g['name'],svc) for g in groups for svc in g['services'] if svc['name']=='ntfy']
    if len(cards)!=1:raise ValueError('Expected one authenticated ntfy card')
    query=urllib.parse.urlencode({'group':cards[0][0],'service':'ntfy','index':0,'endpoint':'messages'})
    result=api.call('/api/services/proxy?'+query)
    if not isinstance(result,dict) or result.get('error') or not any(k in result for k in ('time','message','title')):
        raise ValueError('Native ntfy widget response invalid; inspect privately')
    if secret in json.dumps(result):raise ValueError('Reader credential leaked through widget response')
