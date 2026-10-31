"""Standalone host alert worker: read-only host/API observations, no recovery actions."""
import base64
import concurrent.futures
import datetime
import json
import os
from pathlib import Path
import re
import socket
import ssl
import subprocess
import stat
import time
import urllib.error
import urllib.parse
import urllib.request

CONFIG=Path('/etc/ohara/alerts.json')
STATE=Path('/var/lib/ohara-alerts/state.json')
MARKER='# Managed by Ohara ntfy alerts\n'


def save(path, data):
    if path.is_symlink() or any(p.is_symlink() for p in path.parents):
        raise ValueError('Symlink alert state/config refused')
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    temp=path.with_suffix('.tmp')
    fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w') as f:
        json.dump(data,f);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(temp,path)


def observe(state, key, good, label, threshold=2, now=None):
    """Alert once on confirmed failure; once on recovery. Initial health is quiet."""
    now=time.time() if now is None else now
    row=state.setdefault('checks',{}).setdefault(key,{'healthy':True,'failures':0})
    row['failures']=0 if good else row['failures']+1
    new=good if good or row['failures']>=threshold else row['healthy']
    if new==row['healthy']:return
    row['healthy']=new
    queue=state.setdefault('outbox',[])
    queue.append({'title':'Ohara: '+('recovered' if good else 'attention needed'),
                  'message':label+(' is available again.' if good else ' is unavailable; inspect the server.'),
                  'priority':'3' if good else '4','tags':'white_check_mark' if good else 'warning',
                  'time':now})
    if len(queue)>100:
        del queue[:-100]
        print('Alert outbox reached 100 messages; oldest entries discarded',flush=True)


def http_good(url):
    try:
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        request=urllib.request.Request(url,headers={'Host':'localhost:3000'} if urllib.parse.urlsplit(url).port==3002 else {})
        with opener.open(request,timeout=4) as r:
            return 200<=r.status<400
    except urllib.error.HTTPError as e:
        # Native login required is expected, not a service outage.
        return e.code in (401,403)
    except OSError:
        return False


def send(c, message):
    token=base64.b64encode((c['username']+':'+c['password']).encode()).decode()
    h={'Authorization':'Basic '+token,'Title':message['title'],'Priority':message['priority'],
       'Tags':message['tags'],'Content-Type':'text/plain; charset=utf-8'}
    req=urllib.request.Request(c['url']+'/'+c['topic'],data=message['message'].encode(),headers=h)
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req,timeout=5) as r:
        if r.status!=200:raise ValueError('Publish failed')
        r.read(8192)


def load(path):
    s=path.stat()
    if path.is_symlink() or not stat.S_ISREG(s.st_mode) or s.st_mode&0o077 or s.st_uid!=0:
        raise ValueError('Alert configuration must be root-owned mode 0600')
    c=json.loads(path.read_text())
    if (set(c)-{'allow_short_password','integrations'})!={'url','username','password','topic','checks','drives','pool'} or c['url']!='http://127.0.0.1:2586':
        raise ValueError('Unexpected alert configuration or publication endpoint')
    if type(c.get('allow_short_password', False)) is not bool:
        raise ValueError('Invalid short-password exception')
    minimum = 1 if c.get('allow_short_password', False) else 16
    if c['username'] not in {'admin','ohara'} or c['topic']!='ohara-alerts' or not isinstance(c['password'],str) or not minimum<=len(c['password']) or len(c['password'].encode())>72:
        raise ValueError('Invalid alert credentials/topic')
    for row in c['checks']:
        if set(row)!={'label','url','media'} or not re.fullmatch(r'[A-Za-z0-9 .-]{1,60}',row['label']) or type(row['media']) is not bool:
            raise ValueError('Invalid service alert definition')
        u=urllib.parse.urlsplit(row['url'])
        if u.scheme!='http' or u.hostname!='127.0.0.1' or u.username or u.password or u.query or u.fragment:
            raise ValueError('Service checks must use fixed local HTTP endpoints')
    for d in c['drives']:
        if set(d)!={'uuid','label'} or not re.fullmatch(r'[a-f0-9-]{36}',d['uuid']) or not re.fullmatch(r'[A-Za-z0-9 .-]{1,60}',d['label']):
            raise ValueError('Invalid disk alert definition')
    if c['pool'] not in (None,'/ohara/mnt'):
        raise ValueError('Unsupported media pool')
    validate_integrations(c.get('integrations', {}))
    return c


def command(args, include_stderr=False):
    """Fixed argv, bounded output; never request container configuration/env."""
    result=subprocess.run(args, check=True, capture_output=True, text=True, timeout=6)
    return result.stdout+(result.stderr if include_stderr else '')


def json_api(port, path, key):
    req=urllib.request.Request(f'http://127.0.0.1:{port}'+path, headers={'X-Api-Key':key})
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=4) as response:
        return json.loads(response.read(1024*1024))


def validate_integrations(c):
    if not isinstance(c,dict):raise ValueError('Invalid integrations')
    if set(c)-{'containers','tailscale','watchdog','tls','dns','bambuddy'}:
        raise ValueError('Unknown alert integration')
    for flag in ('tailscale','watchdog'):
        if flag in c and type(c[flag]) is not bool:raise ValueError('Invalid integration flag')
    if not isinstance(c.get('containers',[]),list) or len(c.get('containers',[]))>40:raise ValueError('Invalid container inventory')
    if not isinstance(c.get('tls',[]),list) or len(c.get('tls',[]))>10:raise ValueError('Invalid TLS inventory')
    for row in c.get('containers',[]):
        if set(row)!={'project','service','media'} or type(row['media']) is not bool or any(not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,79}',row[k]) for k in ('project','service')):
            raise ValueError('Invalid container selection')
    for host in c.get('tls',[]):
        if not re.fullmatch(r'[a-z0-9][a-z0-9.-]{0,250}',host):raise ValueError('Invalid TLS hostname')
    if c.get('dns'):
        import ipaddress
        if not ipaddress.ip_address(c['dns']).is_private:raise ValueError('DNS probe must be private')
    if 'bambuddy' in c and (not isinstance(c['bambuddy'],str) or not c['bambuddy'] or len(c['bambuddy'])>512):
        raise ValueError('Invalid Bambuddy read-only key')


def event(state, title, message, priority='3'):
    state.setdefault('outbox',[]).append({'title':'Ohara: '+title,'message':message,
        'priority':priority,'tags':'warning' if priority=='4' else 'information_source','time':time.time()})
    del state['outbox'][:-100]


def printer_events(state, row):
    key='printer:'+str(row['id'])
    observe(state,key+':connection',row['connected'],'Bambuddy printer connection')
    if not row['connected']:return
    current=row['state']
    previous=state.setdefault('printers',{}).get(key)
    if previous is not None and previous!=current:
        if current in ('FINISH','FAILED','PAUSE'):
            event(state,'printer '+current.lower(),'Bambuddy printer state changed to '+current+'.',
                  '3' if current=='FINISH' else '4')
    state['printers'][key]=current
    observe(state,key+':errors',not bool(row.get('hms_errors')),'Bambuddy printer hardware errors')


def container_events(state, row, info):
    key='container:'+row['project']+'/'+row['service']
    status=info['State']
    observe(state,key,status['Running'] and status.get('Health',{}).get('Status')!='unhealthy',key)
    old=state.setdefault('containers',{}).get(key)
    current={'id':info['Id'],'restarts':info['RestartCount'],'oom':status.get('OOMKilled',False)}
    samples=[]
    if old and old['id']==current['id']:
        samples=[r for r in old.get('restart_events',[]) if time.time()-r[0]<300]
        delta=max(0,current['restarts']-old['restarts'])
        if delta:samples.append([time.time(),delta])
        if current['oom'] and not old['oom']:
            event(state,'container out of memory',key+' was killed by the kernel OOM handler.','4')
    observe(state,key+':restarts',sum(r[1] for r in samples)<3,key+' restart loop (3 restarts in 5 minutes)',threshold=1)
    current['restart_events']=samples
    state['containers'][key]=current


def extra_checks(c,state,pool_good):
    integrations=c.get('integrations',{})
    def check(key, label, action):
        try:action();observe(state,'monitor:'+key,True,label+' monitoring')
        except Exception:
            observe(state,'monitor:'+key,False,label+' monitoring')
    if integrations.get('watchdog'):
        def watchdog():
            w=json.loads(Path('/run/ohara-storage-watchdog/state.json').read_text())
            action=w.get('last_action')
            observe(state,'watchdog:safety',action not in ('unsafe','unsafe-stop'),'Storage watchdog unsafe mount',threshold=1)
            exhausted=action=='cooldown' and len([t for t in w.get('attempts',[]) if time.monotonic()-t<3600])>=3
            observe(state,'watchdog:backoff',not exhausted,'Storage watchdog recovery attempts exhausted',threshold=1)
            if action in ('missing','stop','unsafe','unsafe-stop','recover','settling','cooldown'):state['storage_recovery_pending']=True
            if action=='healthy' and state.pop('storage_recovery_pending',False):
                event(state,'storage recovered','Storage watchdog restored healthy media storage.')
            state['watchdog_action']=action
            active=command(['systemctl','is-active','ohara-storage-watchdog.timer']).strip()=='active'
            observe(state,'watchdog:timer',active,'Storage watchdog timer')
        check('watchdog','Storage watchdog',watchdog)
    if integrations.get('tls'):
        def certbot():
            failed=command(['systemctl','show','certbot.service','--property=Result','--value']).strip()
            observe(state,'certbot',failed=='success','Certbot certificate renewal')
        check('certbot','Certbot',certbot)
    if integrations.get('tailscale'):
        def tailscale():
            r=json.loads(command(['tailscale','status','--json']))
            observe(state,'tailscale',r.get('BackendState')=='Running' and r.get('Self',{}).get('Online',False),'Tailscale private access')
        check('tailscale','Tailscale',tailscale)
    if integrations.get('dns'):
        def dns():
            r=command(['dig','@'+integrations['dns'],'example.org','A','+time=2','+tries=1'])
            observe(state,'adguard:dns','status: NOERROR' in r and bool(re.search(r'ANSWER: [1-9]',r)),'AdGuard DNS resolution')
        check('dns','AdGuard DNS',dns)
    for host in integrations.get('tls',[]):
        def tls(host=host):
            with socket.create_connection(('127.0.0.1',443),timeout=4) as raw:
                with ssl.create_default_context().wrap_socket(raw,server_hostname=host) as sock:
                    days=(ssl.cert_time_to_seconds(sock.getpeercert()['notAfter'])-time.time())/86400
                    observe(state,'cert:'+host,days>=14,'TLS certificate for '+host+' (under 14 days remaining)')
                    observe(state,'cert-critical:'+host,days>=3,'TLS certificate for '+host+' (under 3 days remaining)',threshold=1)
                    sock.sendall(('GET / HTTP/1.1\r\nHost: '+host+'\r\nConnection: close\r\n\r\n').encode())
                    status=int(sock.recv(1024).split(b' ')[1])
                    observe(state,'https:'+host,status<500,'Nginx HTTPS route '+host)
        check('tls:'+host,'Nginx TLS '+host,tls)
    if integrations.get('bambuddy'):
        def printers():
            key=integrations['bambuddy']
            for row in json_api(8008,'/api/v1/printers/',key):
                printer_events(state,json_api(8008,'/api/v1/printers/'+str(row['id'])+'/status',key))
        check('bambuddy','Bambuddy printer',printers)
    def inspect_container(row):
        if row['media'] and not pool_good:return
        name=row['project']+'/'+row['service']
        def container():
            ids=command(['docker','ps','-aq','--filter','label=com.docker.compose.project='+row['project'],
                         '--filter','label=com.docker.compose.service='+row['service']]).split()
            if len(ids)!=1:
                observe(state,'container:'+name,False,'Container '+name);return
            # Explicit projection excludes Config.Env, mounts, labels and credentials.
            info=json.loads(command(['docker','inspect','--format',
                '{"Id":{{json .Id}},"State":{"Running":{{json .State.Running}},"OOMKilled":{{json .State.OOMKilled}},"Health":{"Status":{{with index .State "Health"}}{{json .Status}}{{else}}"none"{{end}}}},"RestartCount":{{json .RestartCount}}}',ids[0]]))
            container_events(state,row,info)
            if row['service']=='maintainerr':
                since=state.setdefault('log_since',{}).get(name)
                now=datetime.datetime.now(datetime.timezone.utc).isoformat()
                if since:
                    logs=command(['docker','logs','--since',since,'--tail','200',ids[0]],include_stderr=True)
                    # Never forward log bodies, which can contain account data.
                    observe(state,'maintainerr:logs',not bool(re.search(r'(?i)(\berror\b|\bfatal\b)',logs)),
                            'Maintainerr error logs',threshold=1)
                state['log_since'][name]=now
        check('container:'+name,'Container '+name,container)
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        list(executor.map(inspect_container,integrations.get('containers',[])))


def tick(c,state):
    missing=False
    for d in c['drives']:
        try:present=stat.S_ISBLK((Path('/dev/disk/by-uuid')/d['uuid']).stat().st_mode)
        except OSError:present=False
        missing |= not present
        observe(state,'disk:'+d['uuid'],present,d['label'],threshold=1)
    pool_good=True
    if c['pool']:
        # Kernel metadata only, so monitoring does not wake the HDD.
        rows=Path('/proc/self/mountinfo').read_text().splitlines()
        pool_good=not missing and any(line.split()[4]==c['pool'] and ' - fuse.mergerfs ' in line for line in rows)
        observe(state,'media-pool',pool_good,'Media storage pool',threshold=1)
    checks=[row for row in c['checks'] if not row['media'] or pool_good]
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        good=list(executor.map(lambda row:http_good(row['url']),checks))
    for row,result in zip(checks,good):
        observe(state,'service:'+row['label'],result,row['label'])
    usage=os.statvfs('/')
    free=usage.f_bavail/max(1,usage.f_blocks)
    observe(state,'root-space',free>=0.10,'System disk free space (below 10 percent)',threshold=2)
    extra_checks(c,state,pool_good)
    for _ in range(min(10,len(state.get('outbox',[])))):
        message=state['outbox'][0]
        try:send(c,message)
        except Exception:
            print('ntfy publish unavailable; pending alerts retained for retry',flush=True)
            break
        state['outbox'].pop(0)
        print('Published alert transition',flush=True)


def run():
    if os.geteuid()!=0:raise ValueError('Alert worker requires root')
    c=load(CONFIG)
    if STATE.is_symlink():raise ValueError('Symlink alert state refused')
    try:state=json.loads(STATE.read_text())
    except FileNotFoundError:state={}
    try:tick(c,state)
    finally:save(STATE,state)


def seerr(c,root):
    """Configure only Seerr's native ntfy provider; preserve all other agents."""
    import credentials
    import media
    import ntfy
    if os.geteuid()!=0:raise ValueError('Use sudo scripts/ntfy seerr')
    ntfy.status(c,root)
    values,_=credentials.load(root)
    key=values.get('HOMEPAGE_VAR_SEERR_API_KEY')
    if not key:raise ValueError('Supply HOMEPAGE_VAR_SEERR_API_KEY privately in .env')
    api=media.Client('http://127.0.0.1:5055',key)
    before=api.call('/api/v1/settings/notifications/ntfy')
    desired={'enabled':True,'embedPoster':False,'types':2|128|4096,
             'options':{'url':'https://'+ntfy.settings(c)[0],'topic':ntfy.TOPIC,
                'tags':'movie_camera','priority':3,'locale':'en',
                'authMethodUsernamePassword':True,'authMethodToken':False,
                'username':ntfy.USER,'password':ntfy.password(root)}}
    if before.get('enabled') and before!=desired:
        # Do not replace an unrelated destination or existing event preferences.
        if before.get('options',{}).get('topic')!=ntfy.TOPIC or before.get('options',{}).get('url')!=desired['options']['url']:
            raise ValueError('Existing Seerr ntfy destination differs; preserve and review')
        desired['types'] |= before.get('types',0)
    backup=Path('/var/backups/ohara')/('ntfy-seerr-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    save(backup/'provider.json',before)
    # Native test publishes a labelled test without creating any media request.
    api.call('/api/v1/settings/notifications/ntfy/test',desired)
    try:
        api.call('/api/v1/settings/notifications/ntfy',desired)
        if api.call('/api/v1/settings/notifications/ntfy')!=desired:
            raise ValueError('Seerr ntfy verification failed')
    except Exception:
        api.call('/api/v1/settings/notifications/ntfy',before)
        raise
    print('Seerr native ntfy configured for pending, automatically approved and automatic new requests; test published')


def install(c,root):
    import config
    import ntfy
    import runtime
    if os.geteuid()!=0:raise ValueError('Use sudo scripts/ntfy install-alerts')
    ntfy.status(c,root)  # Verify real supplied account before installing publisher credentials.
    rows=[('Homepage',3002,'/api/healthcheck',True),('Jellyfin',8096,'/health',True),
          ('Navidrome',4533,'/ping',True),('Seerr',5055,'/api/v1/settings/public',False),
          ('Radarr',7878,'/',True),('Sonarr',8989,'/',True),('Lidarr',8686,'/',True),
          ('Bazarr',6767,'/',True),('Prowlarr',9696,'/',False),('qBittorrent',8081,'/',True),
          ('OpenSpeedTest',3000,'/',False),('ntfy',2586,'/v1/health',False),
          ('Nginx',80,'/',False)]
    # Include optional services only when the real project/service is running.
    running=runtime.run(runtime.docker_prefix()+['ps','--format','{{.Label "com.docker.compose.project"}}/{{.Label "com.docker.compose.service"}}'],capture=True).splitlines()
    for name,port,path,project in [('Immich',2283,'/api/server/ping','ohara-immich/immich-server'),
                                   ('Bambuddy',8008,'/health','ohara-bambuddy/bambuddy'),
                                   ('Maintainerr',6246,'/','ohara-maintainerr/maintainerr'),
                                   ('AdGuard',3003,'/','ohara-dns/adguard')]:
        if project in running:rows.append((name,port,path,False))
    d={'url':ntfy.BASE,'username':ntfy.USER,'password':ntfy.password(root),'topic':ntfy.TOPIC,
       'checks':[{'label':n,'url':f'http://127.0.0.1:{p}'+path,'media':m} for n,p,path,m in rows],
       'drives':[],'pool':None,'allow_short_password':c.get('NTFY_ALLOW_SHORT_PASSWORD','false')=='true'}
    if c.get('MEDIA_POOL_MOUNT'):
        import storage_watchdog
        cfg=storage_watchdog.load_config(storage_watchdog.CONFIG)
        d['pool']=cfg['pool']
        d['drives']=[{'uuid':b['uuid'],'label':Path(b['mount']).name+' drive'} for b in cfg['branches']]
    import credentials
    values,_=credentials.load(root)
    media_names={n.lower() for n,_,_,m in rows if m}
    d['integrations']={
        'containers':[{'project':p,'service':svc,'media':svc in media_names}
                      for p,svc in (r.split('/',1) for r in running) if p in
                      {'ohara','ohara-ntfy','ohara-bambuddy','ohara-maintainerr','ohara-dns','ohara-immich'}],
        'tailscale':Path('/usr/bin/tailscale').exists(),
        'watchdog':bool(d['pool']),
        'tls':[ntfy.settings(c)[0],c['REQUESTS_HOST'],c['JELLYFIN_HOST']],
    }
    if 'ohara-dns/adguard' in running:d['integrations']['dns']=c['ADGUARD_BIND_IP']
    if 'ohara-bambuddy/bambuddy' in running and values.get('HOMEPAGE_VAR_BAMBUDDY_API_KEY'):
        d['integrations']['bambuddy']=values['HOMEPAGE_VAR_BAMBUDDY_API_KEY']
    validate_integrations(d['integrations'])
    if d['integrations'].get('dns'):
        import shutil
        if not shutil.which('dig'):raise ValueError('Install DNS probe prerequisite: sudo apt-get install dnsutils')
    backup=Path('/var/backups/ohara')/('ntfy-alerts-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    worker=Path('/usr/local/lib/ohara/alerts.py')
    target_units={Path('/etc/systemd/system')/('ohara-alerts.'+suffix):root/'configs/systemd'/('ohara-alerts.'+suffix) for suffix in ['service','timer']}
    for p in [CONFIG,worker,*target_units]:
        if p.is_symlink() or any(x.is_symlink() for x in p.parents):raise ValueError('Symlink alert installation target')
        if p in target_units and p.exists() and not p.read_text().startswith(MARKER):raise ValueError('Unmanaged alert unit; preserve and review')
    backup.mkdir(parents=True,mode=0o700)
    for p in [CONFIG,worker,*target_units]:
        if p.exists():config.create_file(backup/p.name,p.read_text(),0o600)
    save(CONFIG,d);os.chown(CONFIG,0,0)
    worker.parent.mkdir(parents=True,exist_ok=True)
    worker.write_text((root/'scripts/lib/alerts.py').read_text());worker.chmod(0o644);os.chown(worker,0,0)
    for dest,source in target_units.items():
        dest.write_text(source.read_text());dest.chmod(0o644);os.chown(dest,0,0)
    runtime.run(['systemd-analyze','verify',*[str(p) for p in target_units]])
    runtime.run(['systemctl','daemon-reload'])
    runtime.run(['systemctl','enable','--now','ohara-alerts.timer'])
    print('Host alert timer enabled; topic '+ntfy.TOPIC+'; publisher credentials are root-only')


if __name__=='__main__':
    try:run()
    except Exception as e:
        print('Ohara alerts: '+type(e).__name__,flush=True)
        raise SystemExit(1)
