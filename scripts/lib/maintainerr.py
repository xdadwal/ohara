"""Optional LAN-only Maintainerr lifecycle; never creates or executes cleanup rules."""
import base64
import datetime
import json
import os
from pathlib import Path
import re

import adguard
import config
import credentials
import host
import jellyfin_theme
import media
import runtime

IMAGE_KEYS = {'MAINTAINERR_IMAGE'}
SERVICE_KEYS = {'HOMEPAGE_VAR_JELLYFIN_API_KEY','HOMEPAGE_VAR_SEERR_API_KEY','RADARR_API_KEY','SONARR_API_KEY'}


def storage(c):
    path = Path(c['DATA_ROOT'])/'maintainerr'
    if any(p.is_symlink() for p in (path,*path.parents)):
        raise ValueError('Maintainerr storage must not use symlinks')
    return path


def images(root):
    values = config.parse(root/'versions.maintainerr.env',IMAGE_KEYS)
    if not re.fullmatch(r'ghcr.io/maintainerr/maintainerr:[0-9.]+@sha256:[a-f0-9]{64}',values['MAINTAINERR_IMAGE']):
        raise ValueError('Maintainerr requires an official immutable release image')
    return values


def compose(c,root,args,*,capture=False,timeout=60):
    values = {k:c[k] for k in ('DATA_ROOT','RUN_UID','RUN_GID','TZ')}
    values.update(images(root));values['COMPOSE_DISABLE_ENV_FILE']='1'
    env = {k:v for k,v in os.environ.items() if k in {'PATH','HOME','USER','XDG_RUNTIME_DIR','DOCKER_CONFIG','DOCKER_HOST','DOCKER_CONTEXT','SSH_AUTH_SOCK'}}
    env.update(values)
    prefix = ['docker'] if args[0]=='config' else runtime.docker_prefix()
    if prefix[:2]==['sudo','-n']:
        prefix=prefix[:2]+['--preserve-env='+','.join(sorted(values))]+prefix[2:]
    return runtime.run(prefix+['compose','--project-directory',str(root),'--env-file','/dev/null','-f',str(root/'compose.maintainerr.yaml')]+args,env=env,capture=capture,timeout=timeout)


def check(c,root,*,static=False):
    path=storage(c)
    model=json.loads(compose(c,root,['config','--format','json'],capture=True))
    if model.get('name')!='ohara-maintainerr' or set(model['services'])!={'maintainerr'}:
        raise ValueError('Unexpected Maintainerr project inventory')
    s=model['services']['maintainerr']
    ports={(p.get('host_ip'),int(p['published']),int(p['target'])) for p in s.get('ports',[])}
    mounts={(v.get('source'),v.get('target'),v.get('read_only',False)) for v in s.get('volumes',[])}
    if (ports!={('127.0.0.1',6246,6246)} or mounts!={(str(path),'/opt/data',False)}
        or s['image']!=images(root)['MAINTAINERR_IMAGE'] or s.get('user')!=c['RUN_UID']+':'+c['RUN_GID']
        or s.get('privileged') or s.get('network_mode')=='host'
        or s.get('environment')!={'TZ':c['TZ'],'TELEMETRY':'off'}
        or model['networks']['default'].get('name')!='ohara_default'
        or model['networks']['default'].get('external') is not True):
        raise ValueError('Maintainerr must keep its private port, dedicated data and no media mounts')
    if not static and (not path.is_dir() or not config.directory_writable(path,int(c['RUN_UID']),int(c['RUN_GID']))):
        raise ValueError('Run scripts/maintainerr prepare; review existing storage ownership manually')
    print('Maintainerr configuration valid'+(' (static only)' if static else ''))


def prepare(c,root):
    check(c,root,static=True)
    path=storage(c)
    host.ensure_directory(path,int(c['RUN_UID']),int(c['RUN_GID']),0o700)
    check(c,root)


def client():
    return media.Client('http://127.0.0.1:6246')


def ok(result,label):
    if not isinstance(result,dict) or result.get('code')!=1:
        raise ValueError('Maintainerr '+label+' failed; inspect its local UI')


def connect(c,root):
    """Test all connections before saving; preserve existing instances/rules."""
    api=client()
    values=credentials.read(root/'.env',SERVICE_KEYS,ignored=config.KEYS | (credentials.ALL_KEYS-SERVICE_KEYS))
    jf=jellyfin_theme.client(root)
    admins=[u for u in jf.call('/Users') if u.get('Policy',{}).get('IsAdministrator') and not u.get('Policy',{}).get('IsDisabled')]
    if len(admins)!=1:
        raise ValueError('Choose a Jellyfin administrator in Maintainerr UI; exactly one active admin could not be inferred')
    previous=api.call('/api/settings')
    if previous.get('media_server_type') not in (None,'','jellyfin'):
        raise ValueError('Existing Maintainerr media server differs; preserve and review in UI')
    payloads={
        'jellyfin':{'jellyfin_url':'http://jellyfin:8096','jellyfin_api_key':values['HOMEPAGE_VAR_JELLYFIN_API_KEY'],'jellyfin_user_id':admins[0]['Id']},
        'seerr':{'url':'http://seerr:5055','api_key':values['HOMEPAGE_VAR_SEERR_API_KEY']},
        'radarr':{'serverName':'Ohara Radarr','url':'http://radarr:7878','apiKey':values['RADARR_API_KEY']},
        'sonarr':{'serverName':'Ohara Sonarr','url':'http://sonarr:8989','apiKey':values['SONARR_API_KEY']},
    }
    existing={name:api.call('/api/settings/'+name) for name in payloads}
    if any(not isinstance(existing[name],list) for name in ('radarr','sonarr')):
        raise ValueError('Unexpected Maintainerr instance list')
    for name,payload in payloads.items():
        if name in ('jellyfin','seerr'):
            key='jellyfin_url' if name=='jellyfin' else 'url'
            if existing[name].get(key) and existing[name][key].rstrip('/')!=payload[key]:
                raise ValueError('Different existing '+name+' connection; preserve and review in UI')
        test='/api/settings/jellyfin/test' if name=='jellyfin' else '/api/settings/test/'+name
        ok(api.call(test,payload),name+' connection test')
    backup=root/'local/maintainerr-backups'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    for p in (root/'local',backup.parent,backup):
        host.ensure_directory(p,os.getuid(),os.getgid(),0o700)
    config.create_file(backup/'connections.json',json.dumps(existing,indent=2)+'\n')
    for name,payload in payloads.items():
        if name in ('radarr','sonarr'):
            if not isinstance(existing[name],list):raise ValueError('Unexpected Maintainerr instance list')
            matches=[r for r in existing[name] if r['url'].rstrip('/')==payload['url']]
            if matches:
                continue  # Preserve existing credentials, names and tag preferences.
        elif all(existing[name].get(k)==v for k,v in payload.items()):
            continue
        ok(api.call('/api/settings/'+name,payload),name+' save')
    print('Jellyfin, Seerr, Radarr and Sonarr tested/connected; existing rules and instances preserved.')
    print('Private connection snapshot: '+str(backup))


def homepage(c,root):
    import yaml
    path=Path(c['DATA_ROOT'])/'homepage/services.yaml'
    jellyfin_theme.safe(path)
    before=path.read_text();data=yaml.safe_load(before)
    if any('Maintainerr' in entry for group in data for entries in group.values() for entry in entries):
        print('Existing Maintainerr Homepage card preserved.');return
    target=next((g['Administration'] for g in data if 'Administration' in g),None)
    if target is None:target=[];data.append({'Administration':target})
    target.append({'Maintainerr':{'icon':'maintainerr.png','href':'https://maintainerr.'+c['DOMAIN'],'description':'Media maintenance (local network)'}})
    backup=root/'local/maintainerr-backups'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S-homepage')
    backup.mkdir(mode=0o700,parents=True)
    config.create_file(backup/'services.yaml',before)
    # Replace file contents without changing existing ownership/mode.
    path.write_text(yaml.safe_dump(data,sort_keys=False,allow_unicode=True))
    print('Homepage Maintainerr card merged; existing cards/widgets preserved.')


def dns(c,root):
    name='maintainerr.'+c['DOMAIN'];address,_=adguard.settings(c)
    api=media.Client('http://127.0.0.1:3003')
    api.headers['Authorization']='Basic '+base64.b64encode(('admin:'+adguard.password(root)).encode()).decode()
    rows=api.call('/control/rewrite/list')
    matching=[r for r in rows if r['domain']==name]
    if matching:
        if not all(r['answer']==address and r.get('enabled',True) for r in matching):raise ValueError('Conflicting or disabled Maintainerr DNS rewrite; preserve and review')
    else:api.call('/control/rewrite/add',{'domain':name,'answer':address})
    print('Exact Maintainerr LAN DNS rewrite present; other records preserved.')
