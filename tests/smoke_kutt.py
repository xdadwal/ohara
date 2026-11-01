#!/usr/bin/env python3
"""Disposable real Kutt/Postgres and TLS tests. Never uses production credentials/state."""
import base64
import http.client
import json
import os
from pathlib import Path
import shutil
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts/lib'))
import config
import kutt
import kutt_proxy
import runtime
from smoke import NGINX


def main():
    docker=runtime.docker_prefix();project='ohara-kutt-smoke-'+uuid.uuid4().hex[:10]
    (ROOT/'local').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='kutt-smoke-',dir=ROOT/'local') as directory:
        root=Path(directory).resolve();base=root/'storage';(base/'secrets').mkdir(parents=True)
        # Known disposable fixtures, including an apostrophe to exercise SQL quoting.
        (base/'secrets/db-password').write_text("Fixture database ' $ # = password")
        (base/'secrets/jwt-secret').write_text('Fixture signing secret only 0123456789abcdef')
        for p in (base/'secrets').iterdir():p.chmod(0o444)
        c=config.load(ROOT/'.env.example') | {'KUTT_ROOT':str(base),'RUN_UID':str(os.getuid()),'RUN_GID':str(os.getgid()),'KUTT_LAN_NETWORK':'10.123.0.0/24'}
        model=json.loads(kutt.compose(c,ROOT,['config','--format','json'],capture=True));kutt.validate_model(model,c,ROOT)
        model['name']=project;model['networks']['default']['name']=project+'_default'
        model['services']['kutt']['ports']=[{'target':3000,'published':'0','host_ip':'127.0.0.1','protocol':'tcp'}]
        volume=project+'-postgres'
        model['volumes']={'postgres':{'name':volume,'external':True}}
        for row in model['services']['postgres']['volumes']:
            if row['target']=='/var/lib/postgresql/data':
                row.clear();row.update(type='volume',source='postgres',target='/var/lib/postgresql/data')
        candidate=root/'compose.json';candidate.write_text(json.dumps(model))
        def compose(args,capture=False):
            return runtime.run(docker+['compose','--project-directory',str(root),'--env-file','/dev/null','-f',str(candidate),*args],capture=capture,timeout=240)
        def request(path,data=None,token=None,html=False,redirect=False):
            class NoRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self,*args):return None
            headers={'Host':kutt.settings(c)[0],'Accept':'text/html' if html else 'application/json'}
            if token:headers['Cookie']='token='+token
            if data is not None:headers['Content-Type']='application/json'
            req=urllib.request.Request(base_url+path,data=json.dumps(data).encode() if data is not None else None,headers=headers)
            opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
            try:
                with opener.open(req,timeout=10) as response:return response.status,response.read(),response.headers
            except urllib.error.HTTPError as error:return error.code,error.read(),error.headers
        try:
            runtime.run(docker+['volume','create',volume])
            runtime.run(docker+['run','--rm','--network','none','--user','0:0','-v',volume+':/data','--entrypoint','sh',kutt.images(ROOT)['KUTT_POSTGRES_IMAGE'],'-c','chown 70:70 /data && chmod 0700 /data'])
            compose(['up','-d','--wait','--wait-timeout','180'])
            port=compose(['port','kutt','3000'],capture=True).strip().rsplit(':',1)[1]
            base_url='http://127.0.0.1:'+port
            assert request('/api/health')[0]==200
            assert request('/api/links',{'target':'https://example.org/anonymous'})[0] in (401,403)
            assert request('/api/auth/signup',{'email':'unwanted@example.test','password':'Fixture unwanted password'})[0] in (400,401,403)
            code,raw,_=request('/api/auth/create-admin',{'email':'owner@example.test','password':'Fixture owner password only'})
            assert code==201,'Disposable owner creation failed'
            code,raw,_=request('/api/auth/login',{'email':'owner@example.test','password':'Fixture owner password only'})
            assert code==200,'Explicit owner login failed';token=json.loads(raw)['token']
            assert request('/api/auth/create-admin',{'email':'another@example.test','password':'Fixture another password'})[0]==400
            code,raw,_=request('/api/links',{'target':'https://example.org/first','customurl':'stable-qr'},token)
            assert code in (200,201),'Disposable link creation failed: '+str(code)+' '+raw.decode()[:600];link=json.loads(raw);address=link['address'];identifier=link['id']
            assert request('/'+address)[2]['Location']=='https://example.org/first'
            # PATCH with urllib request override; same link address and QR payload stay stable.
            api=__import__('media').Client(base_url);api.headers.update({'Cookie':'token='+token,'Host':kutt.settings(c)[0]})
            api.call('/api/links/'+identifier,{'target':'https://example.org/second'},method='PATCH')
            assert request('/'+address)[2]['Location']=='https://example.org/second'
            code,html,_=request('/api/links',token=token,html=True)
            assert code==200 and b'handleQRCode' in html and address.encode() in html,'QR button/short URL not rendered'
            assert b'new QRCode' in request('/scripts/main.js')[1],'Local QR generation asset missing'
            attrs=compose(['exec','-T','postgres','psql','-U','postgres','-d','kutt','-Atc',"SELECT rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication FROM pg_roles WHERE rolname='kutt'"],capture=True).strip()
            assert attrs=='f','App database role must not be privileged'
            assert compose(['exec','-T','postgres','psql','-U','postgres','-d','postgres','-Atc',"SELECT rolpassword IS NULL FROM pg_authid WHERE rolname='postgres'"],capture=True).strip()=='t'
            compose(['up','-d','--force-recreate','--wait','--wait-timeout','180','kutt'])
            port=compose(['port','kutt','3000'],capture=True).strip().rsplit(':',1)[1];base_url='http://127.0.0.1:'+port
            assert request('/'+address)[2]['Location']=='https://example.org/second','Link not persistent after recreation'
            # Restore a consistent dump into another fresh disposable database.
            dump=compose(['exec','-T','postgres','pg_dump','-U','postgres','-d','kutt','--clean','--if-exists'],capture=True)
            compose(['exec','-T','postgres','psql','-U','postgres','-d','postgres','-c','CREATE DATABASE kutt_restore_probe OWNER kutt'])
            runtime.run(docker+['exec','-i',project+'-postgres-1','psql','-U','postgres','-d','kutt_restore_probe','--set','ON_ERROR_STOP=1'],input=dump,timeout=120)
            restored=compose(['exec','-T','postgres','psql','-U','postgres','-d','kutt_restore_probe','-Atc',"SELECT target FROM links WHERE address='stable-qr'"],capture=True).strip()
            assert restored=='https://example.org/second','Database backup/restore lost the stable short link'
            # Banning blocks the target without deleting the link.
            assert request('/api/links/admin/ban/'+identifier,{},token)[0]==200
            assert request('/'+address)[2]['Location']=='/banned'
            code,raw,_=request('/api/links',token=token)
            assert code==200 and address.encode() in raw,'Banning removed the persistent link'
            proxy_check(c,root,project,compose,docker)
            print('PASS: Kutt/Postgres non-root/read-only startup, restricted DB role, anonymous/signup denial, owner login boundary, create/edit/persistent redirects, SQL backup/restore, native QR UI/assets and ban without deletion.')
        finally:
            compose(['down','--volumes'])
            runtime.run(docker+['volume','rm',volume])


def proxy_check(c,root,project,compose,docker):
    certs=root/'certs';certs.mkdir()
    runtime.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1','-subj','/CN='+kutt.settings(c)[0],'-keyout',str(certs/'key.pem'),'-out',str(certs/'cert.pem')])
    network=json.loads(runtime.run(docker+['network','inspect',project+'_default'],capture=True))[0]
    gateway=network['IPAM']['Config'][0]['Gateway'];app=project+'-kutt-1'
    # Only the host gateway is allowed in this disposable proxy; app peer is denied.
    pc=c | {'KUTT_LAN_NETWORK':gateway+'/32','KUTT_TLS_CERT':'/certs/cert.pem','KUTT_TLS_KEY':'/certs/key.pem'}
    name=project+'-proxy';path=root/'nginx.conf'
    def render(public):
        return 'events {}\nhttp {\n'+kutt_proxy.render(pc,ROOT,public=public).replace('127.0.0.1:3010','kutt:3000')+'\n}\n'
    try:
        path.write_text(render(False))
        runtime.run(docker+['run','-d','--name',name,'--network',project+'_default','-p','127.0.0.1::443','-p','127.0.0.1::80','-v',str(path)+':/etc/nginx/nginx.conf:ro','-v',str(certs)+':/certs:ro',NGINX])
        port=int(runtime.run(docker+['port',name,'443'],capture=True).strip().rsplit(':',1)[1])
        def https():
            conn=http.client.HTTPSConnection('127.0.0.1',port,context=ssl._create_unverified_context(),timeout=5)
            try:
                conn.request('GET','/api/health',headers={'Host':kutt.settings(c)[0]})
                response=conn.getresponse();return response.status,response.read(),response.headers
            finally:conn.close()
        for attempt in range(30):
            try:
                if https()[0]==200:break
            except OSError:pass
            time.sleep(1)
        else:raise AssertionError('Disposable Kutt TLS route not ready')
        def peer(path,scheme='https'):
            code="fetch('"+scheme+"://"+name+path+"',{headers:{Host:'"+kutt.settings(c)[0]+"','X-Forwarded-For':'127.0.0.1'},redirect:'manual'}).then(r=>console.log(r.status))"
            return runtime.run(docker+['exec','-e','NODE_TLS_REJECT_UNAUTHORIZED=0',app,'node','-e',code],capture=True).strip()
        assert peer('/api/health')=='403','Onboarding accepted forged LAN headers'
        assert peer('/api/health','http')=='403','HTTP onboarding redirected a non-LAN client'
        path.write_text(render(True));runtime.run(docker+['exec',name,'nginx','-t']);runtime.run(docker+['exec',name,'nginx','-s','reload']);time.sleep(1)
        assert peer('/api/health')=='200','Public route remained restricted'
        assert peer('/api/auth/create-admin')=='403','Public first-owner endpoint exposed'
        assert peer('/api/v2/auth/create-admin')=='403','Public v2 first-owner alias exposed'
        assert https()[2].get('Cache-Control')=='no-store','Dynamic redirects must not be proxy/browser cached'
        print('PASS: Kutt TLS route, LAN-only onboarding, forged forwarding-header denial, public transition, private owner-creation route and no-store policy.')
    finally:runtime.run(docker+['rm','-f',name])


if __name__=='__main__':main()
