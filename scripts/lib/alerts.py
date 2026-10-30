"""Standalone host alert worker. No Docker socket, media reads or watchdog changes."""
import base64
import concurrent.futures
import datetime
import json
import os
from pathlib import Path
import re
import socket
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
        with opener.open(url,timeout=4) as r:
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
    if set(c)!={'url','username','password','topic','checks','drives','pool'} or c['url']!='http://127.0.0.1:2586':
        raise ValueError('Unexpected alert configuration or publication endpoint')
    if c['username']!='ohara' or c['topic']!='ohara-alerts' or not isinstance(c['password'],str) or not 16<=len(c['password']) or len(c['password'].encode())>72:
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
    return c


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
       'drives':[],'pool':None}
    if c.get('MEDIA_POOL_MOUNT'):
        import storage_watchdog
        cfg=storage_watchdog.load_config(storage_watchdog.CONFIG)
        d['pool']=cfg['pool']
        d['drives']=[{'uuid':b['uuid'],'label':Path(b['mount']).name+' drive'} for b in cfg['branches']]
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
