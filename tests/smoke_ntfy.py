#!/usr/bin/env python3
"""Disposable ntfy auth/cache/publish/subscribe checks; never production credentials."""
import json
import base64
import http.client
import os
from pathlib import Path
import shutil
import sys
import ssl
import tempfile
import time
import uuid
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts/lib'))
import config
import ntfy
import alerts
import ntfy_proxy
import runtime
import media
import yaml

NGINX='nginx@sha256:ed84151ed2d47ef93c0939eb9b9754c6990db6092cd2081e11988a47a83d47ea'


def proxy_check(c,root,project):
    certs=root/'certs';certs.mkdir()
    runtime.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1',
                 '-subj','/CN=ntfy.xdadwal.in','-keyout',str(certs/'key.pem'),'-out',str(certs/'cert.pem')])
    text=ntfy_proxy.render(c,ROOT).replace('127.0.0.1:2586','ntfy:8080').replace(
        '/etc/letsencrypt/live/ohara-wildcard/fullchain.pem','/certs/cert.pem').replace(
        '/etc/letsencrypt/live/ohara-wildcard/privkey.pem','/certs/key.pem')
    p=root/'nginx.conf'
    p.write_text('events {}\nhttp {\nmap $http_upgrade $ohara_connection_upgrade { default upgrade; "" close; }\n'+text+'\n}\n')
    name=project+'-proxy';docker=runtime.docker_prefix()
    try:
        runtime.run(docker+['run','-d','--name',name,'--network',project+'_default',
                           '-p','127.0.0.1::443','-v',str(p)+':/etc/nginx/nginx.conf:ro',
                           '-v',str(certs)+':/certs:ro',NGINX],timeout=120)
        port=int(runtime.run(docker+['port',name,'443'],capture=True).strip().rsplit(':',1)[1])
        token=base64.b64encode(('admin:'+ntfy.password(root)).encode()).decode()
        def request(path,body=None,authenticated=False):
            h={'Host':'ntfy.xdadwal.in'}
            if authenticated:h['Authorization']='Basic '+token
            connection=http.client.HTTPSConnection('127.0.0.1',port,context=ssl._create_unverified_context(),timeout=5)
            try:
                connection.request('POST' if body else 'GET',path,body=body,headers=h)
                response=connection.getresponse();return response.status,response.read()
            finally:connection.close()
        for attempt in range(20):
            try:
                if request('/v1/health')[0]==200:break
            except OSError:pass
            time.sleep(1)
        else:raise AssertionError('Disposable Nginx did not become ready')
        assert request('/ohara-alerts/json?poll=1')[0] in (401,403)
        assert request('/ohara-alerts',b'Blocked anonymous publish')[0] in (401,403)
        assert request('/ohara-alerts',b'Authenticated HTTPS proxy fixture',True)[0]==200
        code,raw=request('/ohara-alerts/json?poll=1&since=all',authenticated=True)
        assert code==200 and b'Authenticated HTTPS proxy fixture' in raw
        print('Disposable ntfy Nginx: TLS route, authenticated publish/read and anonymous denials passed.')
    finally:
        runtime.run(docker+['rm','-f',name])


def homepage_check(c,root,project,reader):
    """Exercise the pinned real Homepage proxy; credentials never reach its browser API."""
    directory=root/'homepage';shutil.copytree(ROOT/'configs/homepage',directory)
    profile=ntfy.widget_profile(c);profile['url']='http://ntfy:8080'
    (directory/'services.yaml').write_text(yaml.safe_dump([{'Utility':[{'ntfy':{'widget':profile}}]}]))
    image=config.images(ROOT/'versions.env')['HOMEPAGE_IMAGE']
    name=project+'-homepage';docker=runtime.docker_prefix()
    try:
        runtime.run(docker+['run','-d','--name',name,'--network',project+'_default',
            '--user',f'{os.getuid()}:{os.getgid()}','-p','127.0.0.1::3000',
            '-v',str(directory)+':/app/config','-e','HOMEPAGE_ALLOWED_HOSTS=widget.test',
            '-e','HOMEPAGE_AUTH_ENABLED=false','-e','HOMEPAGE_VAR_NTFY_PASSWORD='+reader,image])
        port=runtime.run(docker+['port',name,'3000/tcp'],capture=True).strip().rsplit(':',1)[1]
        api=media.Client('http://127.0.0.1:'+port);api.headers['Host']='widget.test'
        deadline=time.monotonic()+90
        while True:
            try:groups=api.call('/api/services');break
            except RuntimeError:
                if time.monotonic()>deadline:raise
                time.sleep(2)
        assert reader not in json.dumps(groups),'Reader credential leaked to browser configuration'
        result=api.call('/api/services/proxy?group=Utility&service=ntfy&index=0&endpoint=messages')
        assert isinstance(result,dict) and result.get('time'),'Native ntfy widget did not retrieve a notification'
        assert reader not in json.dumps(result),'Reader credential leaked through proxy response'
        print('Disposable pinned Homepage: native ntfy message retrieval and browser credential exclusion passed.')
    finally:runtime.run(docker+['rm','-f',name])


def main():
    project='ohara-ntfy-smoke-'+uuid.uuid4().hex[:10]
    (ROOT/'local').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='ntfy-smoke-',dir=ROOT/'local') as directory:
        root=Path(directory).resolve()
        for name in ['compose.ntfy.yaml','versions.ntfy.env']:shutil.copy(ROOT/name,root/name)
        p=root/'.env';p.write_text('NTFY_PASSWORD=Disposable ntfy fixture only $ # =\nNTFY_HOMEPAGE_PASSWORD=Disposable reader fixture only\n');p.chmod(0o600)
        c=config.load(ROOT/'.env.example')|{'NTFY_ROOT':str(root/'storage'),'RUN_UID':str(os.getuid()),'RUN_GID':str(os.getgid())}
        ntfy.prepare(c,root)
        reader=ntfy.reader_password(root)
        server=Path(c['NTFY_ROOT'])/'config/server.yml'
        server.write_text(json.dumps(ntfy.reader_config(ntfy.read_server(server),reader)))
        override=root/'override.yaml'
        override.write_text('services:\n  ntfy:\n    ports: !override\n      - "127.0.0.1::8080"\n')
        def compose(args,capture=False):
            return ntfy.compose(c,root,['-p',project,'-f',str(override),*args],capture=capture,timeout=180)
        try:
            compose(['up','-d','--wait','--wait-timeout','90'])
            port=compose(['port','ntfy','8080'],capture=True).strip().rsplit(':',1)[1]
            ntfy.BASE='http://127.0.0.1:'+port
            ntfy.status(c,root)
            assert ntfy.request('/ohara-alerts',data=b'anonymous must fail')[0] in (401,403)
            assert ntfy.request('/other-topic',root,b'outside ACL must fail')[0] in (401,403)
            code,raw=ntfy.request('/ohara-alerts',root,b'Disposable end-to-end notification',{'Title':'Fixture alert'})
            assert code==200
            message=json.loads(raw);identifier=message['id']
            code,raw=ntfy.request('/ohara-alerts/json?poll=1&since=all',root)
            assert code==200 and any(json.loads(line).get('id')==identifier for line in raw.splitlines())
            state={}
            alerts.observe(state,'service:fixture',False,'Fixture service')
            alerts.observe(state,'service:fixture',False,'Fixture service')
            alerts.observe(state,'service:fixture',True,'Fixture service')
            publisher={'url':ntfy.BASE,'topic':'ohara-alerts','username':'admin','password':ntfy.password(root)}
            for event in state['outbox']:alerts.send(publisher,event)
            code,raw=ntfy.request('/ohara-alerts/json?poll=1&since=all',root)
            assert code==200
            titles=[json.loads(line).get('title') for line in raw.splitlines()]
            assert 'Ohara: attention needed' in titles and 'Ohara: recovered' in titles
            compose(['restart','ntfy'])
            port=compose(['port','ntfy','8080'],capture=True).strip().rsplit(':',1)[1]
            ntfy.BASE='http://127.0.0.1:'+port
            for attempt in range(60):
                try:
                    if ntfy.request('/v1/health')[0]==200:break
                except RuntimeError:pass
                time.sleep(1)
            else:raise AssertionError('ntfy did not become ready after restart')
            code,raw=ntfy.request('/ohara-alerts/json?poll=1&since=all',root)
            assert code==200 and any(json.loads(line).get('id')==identifier for line in raw.splitlines())
            print('Disposable ntfy: non-root startup, anonymous read/write denial, scoped topic ACL, authenticated publish/read and persistent cache passed.')
            ntfy.verify_reader(reader)
            homepage_check(c,root,project,reader)
            proxy_check(c,root,project)
        finally:
            compose(['down','--volumes'])


if __name__=='__main__':main()
