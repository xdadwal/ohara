"""Optional Kutt + independent Postgres; no automatic owner or secret creation."""
import base64
import datetime
import ipaddress
import json
import os
from pathlib import Path
import re
import socket

import config
import credentials
import host
import jellyfin_theme
import media
import runtime

PORT=3010


def settings(c):
    if int(c['RUN_UID'])==0 or int(c['RUN_GID'])==0:raise ValueError('Kutt app requires a non-root UID/GID')
    name=c.get('KUTT_HOST','go.'+c['DOMAIN'])
    others={c[k] for k in ('DOMAIN','HOMEPAGE_HOST','REQUESTS_HOST','JELLYFIN_HOST','SPEED_HOST','NAVIDROME_HOST')}
    others.update(prefix+'.'+c['DOMAIN'] for prefix in ('ntfy','immich','bambuddy','maintainerr','adguard','radarr','sonarr','prowlarr','qbittorrent','lidarr','bazarr'))
    if not config.HOST.fullmatch(name) or name in others:raise ValueError('KUTT_HOST must be a distinct valid hostname')
    base=Path(c.get('KUTT_ROOT',str(Path(c['DATA_ROOT'])/'kutt')))
    mount=Path(c.get('KUTT_MOUNT','/'))
    for p in (base,mount):
        if (str(p)!='/' and not config.PATH.fullmatch(str(p))) or '..' in p.parts or '//' in str(p):
            raise ValueError('Kutt storage requires safe absolute paths')
        if any(x.is_symlink() for x in (p,*p.parents)):raise ValueError('Kutt storage symlinks refused')
    if base==Path('/') or mount not in base.parents:raise ValueError('KUTT_ROOT must be below KUTT_MOUNT')
    protected=[Path(c['MEDIA_ROOT']),Path(c['DATA_ROOT'])/'media']
    protected += [Path(c['DATA_ROOT'])/s for s in ('immich','ntfy','homepage','bambuddy','maintainerr','jellyfin','jellyfin-cache','navidrome','radarr','sonarr','lidarr','bazarr','prowlarr','qbittorrent','adguard')]
    for key in ('MEDIA_POOL_MOUNT','IMMICH_LIBRARY_ROOT','IMMICH_DATABASE_ROOT','NTFY_ROOT','BAMBUDDY_ROOT'):
        if c.get(key):protected.append(Path(c[key]))
    if any(base==p or base in p.parents or p in base.parents for p in protected):
        raise ValueError('Kutt database/secrets must be independent of media and other application storage')
    return name,base,mount


def secrets(root,*,owner=False):
    required={'KUTT_DB_PASSWORD','KUTT_JWT_SECRET'} | ({'KUTT_PASSWORD'} if owner else set())
    values=credentials.read(root/'.env',required,ignored=config.KEYS | (credentials.ALL_KEYS-required))
    if any(v!=v.strip() for v in values.values()):raise ValueError('Kutt file inputs must not have leading/trailing whitespace')
    if len(set(values.values()))!=len(values):raise ValueError('Kutt inputs must be independent values')
    if owner and len(values['KUTT_PASSWORD'])>64:raise ValueError('KUTT_PASSWORD exceeds native 64-character limit')
    return values


def images(root):
    values=config.parse(root/'versions.kutt.env',{'KUTT_IMAGE','KUTT_POSTGRES_IMAGE'})
    for key,pattern in [('KUTT_IMAGE',r'kutt/kutt:v[0-9.]+@sha256:[a-f0-9]{64}'),
                        ('KUTT_POSTGRES_IMAGE',r'postgres:17\.[0-9]+-alpine[0-9.]+@sha256:[a-f0-9]{64}')]:
        if not re.fullmatch(pattern,values[key]):raise ValueError('Kutt requires reviewed official release/digest pins')
    return values


def storage(c,*,prepared=True):
    _,base,mount=settings(c)
    p=base
    while not p.exists():p=p.parent
    rows=json.loads(runtime.run(['findmnt','--json','--target',str(p),'-o','TARGET,FSTYPE'],capture=True))['filesystems']
    if len(rows)!=1 or rows[0]['target']!=str(mount) or rows[0]['fstype'] not in {'ext4','xfs','btrfs','zfs'}:
        raise ValueError('Kutt requires the verified independent local filesystem')
    if prepared:
        for path,uid,gid in [(base,0,0),(base/'postgres',70,70),(base/'secrets',0,0)]:
            if path.is_symlink() or not path.is_dir():raise ValueError('Run sudo scripts/kutt prepare')
            st=path.stat()
            if (st.st_uid,st.st_gid)!=(uid,gid) or st.st_mode&0o077:
                raise ValueError('Existing Kutt directory ownership/mode requires review; no recursive chown')
        for name,uid,gid,mode in [('db-password',int(c['RUN_UID']),70,0o440),('jwt-secret',int(c['RUN_UID']),int(c['RUN_GID']),0o400)]:
            p=base/'secrets'/name
            if p.is_symlink() or not p.is_file():raise ValueError('Prepared private Kutt input missing')
            st=p.stat()
            if (st.st_uid,st.st_gid,st.st_mode&0o777)!=(uid,gid,mode):raise ValueError('Installed Kutt secret ownership/mode drift; preserve and review')


def compose(c,root,args,*,capture=False,timeout=60,input=None):
    if any(a in {'up','start','restart','create','run'} for a in args):storage(c)
    name,base,_=settings(c)
    values={k:c[k] for k in ('TZ','RUN_UID','RUN_GID')}
    values.update(images(root),KUTT_ROOT=str(base),KUTT_HOST=name,
                  KUTT_INIT_SCRIPT=str(root/'configs/kutt/10-kutt.sh'),COMPOSE_DISABLE_ENV_FILE='1')
    env={k:v for k,v in os.environ.items() if k in {'PATH','HOME','USER','XDG_RUNTIME_DIR','DOCKER_CONFIG','DOCKER_HOST','DOCKER_CONTEXT','SSH_AUTH_SOCK'}}
    env.update(values)
    docker=['docker'] if 'config' in args else runtime.docker_prefix()
    if docker[:2]==['sudo','-n']:docker=docker[:2]+['--preserve-env='+','.join(sorted(values))]+docker[2:]
    return runtime.run(docker+['compose','--project-directory',str(root),'--env-file','/dev/null','-f',str(root/'compose.kutt.yaml'),*args],env=env,capture=capture,timeout=timeout,input=input)


def check(c,root,*,static=False):
    _,base,_=settings(c)
    m=json.loads(compose(c,root,['config','--format','json'],capture=True))
    validate_model(m,c,root)
    if not static:
        values=secrets(root);storage(c)
        # Existing installations never silently rotate DB or signing credentials.
        for key,file in [('KUTT_DB_PASSWORD','db-password'),('KUTT_JWT_SECRET','jwt-secret')]:
            if (base/'secrets'/file).read_text()!=values[key]:raise ValueError('Private input differs from installed Kutt state; explicit rotation required')
    print('Kutt configuration valid'+(' (static)' if static else ''))


def validate_model(m,c,root):
    name,base,_=settings(c)
    if m.get('name')!='ohara-kutt' or set(m['services'])!={'kutt','postgres'}:raise ValueError('Unexpected Kutt project inventory')
    for name_,s in m['services'].items():
        if s.get('privileged') or s.get('network_mode') or s.get('cap_add') or s.get('cap_drop')!=['ALL'] or not s.get('read_only') or 'no-new-privileges:true' not in s.get('security_opt',[]):
            raise ValueError('Kutt services require isolated non-root hardened containers')
        if s['image']!=images(root)['KUTT_IMAGE' if name_=='kutt' else 'KUTT_POSTGRES_IMAGE']:
            raise ValueError('Unexpected Kutt image')
        if any(v.get('bind',{}).get('create_host_path',False) or not str(v['source']).startswith(str(base)+'/') and v['source']!=str(root/'configs/kutt/10-kutt.sh') for v in s['volumes']):
            raise ValueError('Unexpected Kutt bind source or implicit creation')
    app=m['services']['kutt'];db=m['services']['postgres'];e=app['environment']
    ports={(p.get('host_ip'),str(p['published']),p['target']) for p in app['ports']}
    if ports!={('127.0.0.1','3010',3000)} or db.get('ports') or app.get('user')!=c['RUN_UID']+':'+c['RUN_GID'] or db.get('user')!='70:70':
        raise ValueError('Kutt must expose only its loopback app port and use reviewed non-root identities')
    for key,value in {'DB_CLIENT':'pg','DB_HOST':'postgres','DB_USER':'kutt','DB_NAME':'kutt','REDIS_ENABLED':'false','MAIL_ENABLED':'false','OIDC_ENABLED':'false','DISALLOW_REGISTRATION':'true','DISALLOW_ANONYMOUS_LINKS':'true','ENABLE_RATE_LIMIT':'true','DEFAULT_DOMAIN':name}.items():
        if str(e.get(key))!=value:raise ValueError('Kutt private deployment policy changed')
    if any(key in e for key in ('DB_PASSWORD','JWT_SECRET','KUTT_PASSWORD')):raise ValueError('Use narrow private file inputs; no plaintext container environment')
    expected_app={(str(base/'secrets/db-password'),'/run/secrets/db_password',True),(str(base/'secrets/jwt-secret'),'/run/secrets/jwt_secret',True)}
    expected_db={(str(base/'postgres'),'/var/lib/postgresql/data',False),(str(base/'secrets/db-password'),'/run/secrets/db_password',True),(str(root/'configs/kutt/10-kutt.sh'),'/docker-entrypoint-initdb.d/10-kutt.sh',True)}
    for s,expected in [(app,expected_app),(db,expected_db)]:
        if {(v['source'],v['target'],v.get('read_only',False)) for v in s['volumes']}!=expected:raise ValueError('Unexpected Kutt mounts')
    if any(n.get('external') or n.get('name')!='ohara-kutt_default' for n in m['networks'].values()):raise ValueError('Kutt must keep its independent bridge')


def prepare(c,root):
    if os.geteuid()!=0:raise ValueError('Use sudo scripts/kutt prepare')
    values=secrets(root);check(c,root,static=True);storage(c,prepared=False)
    # Confirm reviewed image identity on the actual target architecture.
    image=images(root)['KUTT_POSTGRES_IMAGE']
    uid=runtime.run(runtime.docker_prefix()+['run','--rm','--network','none','--entrypoint','id',image,'-u','postgres'],capture=True).strip()
    if uid!='70':raise ValueError('Postgres image UID changed; review storage ownership first')
    _,base,_=settings(c)
    for p,uid,gid in [(base,0,0),(base/'postgres',70,70),(base/'secrets',0,0)]:host.ensure_directory(p,uid,gid,0o700)
    for file,key,uid,gid,mode in [('db-password','KUTT_DB_PASSWORD',int(c['RUN_UID']),70,0o440),('jwt-secret','KUTT_JWT_SECRET',int(c['RUN_UID']),int(c['RUN_GID']),0o400)]:
        p=base/'secrets'/file
        if p.exists() or p.is_symlink():
            if p.is_symlink() or not p.is_file() or p.read_text()!=values[key]:raise ValueError('Preserve existing Kutt secret; explicit rotation required')
        else:
            config.create_file(p,values[key],mode);os.chown(p,uid,gid)
    check(c,root)
    print('Kutt independent storage/private inputs prepared; owner setup remains in its LAN-only UI')


def client():return media.Client('http://127.0.0.1:'+str(PORT))


def sql(c,root,statement):
    return compose(c,root,['exec','-T','postgres','psql','-U','postgres','-d','kutt','-Atc',statement],capture=True).strip()


def status(c,root):
    if client().call('/api/health')!='OK':raise ValueError('Kutt health endpoint failed')
    if sql(c,root,"SELECT rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication FROM pg_roles WHERE rolname='kutt'")!='f':
        raise ValueError('Kutt application database role is not restricted')
    count=sql(c,root,"SELECT count(*) FROM users WHERE role='ADMIN' AND verified=true AND banned=false")
    print('Kutt/Postgres healthy; restricted app role verified; owner setup '+('pending' if count=='0' else 'present (verify login before public activation)'))


def require_accounts(c,root):
    password=secrets(root,owner=True)['KUTT_PASSWORD']
    emails=sql(c,root,"SELECT email FROM users WHERE role='ADMIN' AND verified=true AND banned=false ORDER BY id").splitlines()
    if len(emails)!=1:raise ValueError('Exactly one verified enabled owner is required for initial public activation')
    api=client();reply=api.call('/api/auth/login',{'email':emails[0],'password':password})
    if not isinstance(reply,dict) or not reply.get('token'):raise ValueError('Native Kutt owner login not verified')
    api.headers['Cookie']='token='+reply['token']
    api.call('/api/users/admin')
    return api


def homepage(c,root):
    import yaml
    name,_,_=settings(c);p=jellyfin_theme.safe(Path(c['DATA_ROOT'])/'homepage/services.yaml')
    before=p.read_text();data=yaml.safe_load(before)
    cards=[entry['Kutt'] for g in data for rows in g.values() for entry in rows if 'Kutt' in entry]
    if cards:
        if len(cards)!=1 or cards[0].get('href') not in ('https://'+name,'https://{{HOMEPAGE_VAR_KUTT_HOST}}'):raise ValueError('Existing Kutt card differs; preserve and review')
        print('Existing Kutt Homepage card preserved');return
    group=next((g['Utility'] for g in data if 'Utility' in g),None)
    if group is None:group=[];data.append({'Utility':group})
    group.append({'Kutt':{'icon':'mdi-link-variant','href':'https://'+name,'description':'Short links and QR codes'}})
    backup=root/'local/kutt-backups'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    backup.mkdir(parents=True,mode=0o700);config.create_file(backup/'services.yaml',before,0o600)
    p.write_text(yaml.safe_dump(data,sort_keys=False,allow_unicode=True))
    print('Kutt Homepage link merged; existing widgets preserved; no credentials forwarded')


def dns(c,root):
    import adguard
    name,_,_=settings(c);address,_=adguard.settings(c)
    with socket.socket() as probe:probe.bind((address,0))
    api=media.Client('http://127.0.0.1:3003')
    api.headers['Authorization']='Basic '+base64.b64encode(('admin:'+adguard.password(root)).encode()).decode()
    rows=[r for r in api.call('/control/rewrite/list') if r['domain']==name]
    if rows and not all(r['answer']==address and r.get('enabled',True) for r in rows):raise ValueError('Conflicting Kutt DNS record; preserve and inspect')
    if not rows:api.call('/control/rewrite/add',{'domain':name,'answer':address})
    print('Kutt exact local DNS rewrite configured; router/client DNS unchanged')


def backup(c,root):
    """Private consistent SQL dump and installed secrets, never printed."""
    if os.geteuid()!=0:raise ValueError('Use sudo scripts/kutt backup')
    check(c,root)
    _,base,_=settings(c)
    dest=Path('/var/backups/ohara')/('kutt-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    dest.mkdir(parents=True,mode=0o700)
    dump=compose(c,root,['exec','-T','postgres','pg_dump','-U','postgres','-d','kutt','--clean','--if-exists'],capture=True,timeout=180)
    config.create_file(dest/'database.sql',dump,0o600)
    for filename in ('db-password','jwt-secret'):
        config.create_file(dest/filename,(base/'secrets'/filename).read_text(),0o600)
    config.create_file(dest/'versions.kutt.env',(root/'versions.kutt.env').read_text(),0o600)
    print('Private local Kutt backup: '+str(dest)+'; copy encrypted to an independent destination for host-loss protection')


def restore_sql(c,root,sql_text):
    """Explicit operator-authorized restore only; caller must stop app beforehand."""
    check(c,root)
    if not isinstance(sql_text,str) or not sql_text.strip():raise ValueError('Empty Kutt restore refused')
    compose(c,root,['exec','-T','postgres','psql','-U','postgres','-d','kutt','--set','ON_ERROR_STOP=1'],input=sql_text,timeout=180)
