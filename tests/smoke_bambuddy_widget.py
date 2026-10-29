#!/usr/bin/env python3
"""Disposable pinned Homepage Custom API check; no production printer or keys."""
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
import urllib.parse
import uuid
import yaml
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts/lib'))
import bambuddy
import config
import media
import runtime


def main():
    docker = runtime.docker_prefix()
    image = config.images(ROOT/'versions.env')['HOMEPAGE_IMAGE']
    identifier = 'ohara-widget-'+uuid.uuid4().hex[:10]
    key = 'disposable-bambuddy-widget-status-key'
    status = {'connected': True, 'state': 'RUNNING', 'progress': 42,
              'temperatures': {'nozzle': 210, 'bed': 60}, 'remaining_time': 17}
    server = """const http=require('http');http.createServer((q,s)=>{
      if(q.method!=='GET'||q.url!=='/api/v1/printers/7/status'||
         q.headers['x-api-key']!==process.env.TEST_KEY){s.writeHead(403);s.end('{}');return;}
      s.setHeader('Content-Type','application/json');s.end(process.env.TEST_STATUS);
    }).listen(8000,'0.0.0.0');"""
    (ROOT/'local').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='widget-smoke-',dir=ROOT/'local') as d:
        directory=Path(d).resolve()
        shutil.copytree(ROOT/'configs/homepage',directory/'config')
        profile=bambuddy.widget_config('example.com',7)
        profile['url']='http://fixture:8000/api/v1/printers/7/status'
        (directory/'config/services.yaml').write_text(yaml.safe_dump([
            {'3D Print':[{'Bambuddy':{'widget':profile}}]}]))
        try:
            runtime.run(docker+['network','create',identifier])
            runtime.run(docker+['run','-d','--name',identifier+'-api','--network',identifier,
                '--network-alias','fixture','-e','TEST_KEY='+key,'-e','TEST_STATUS='+json.dumps(status),
                '--entrypoint','node',image,'-e',server])
            runtime.run(docker+['run','-d','--name',identifier+'-homepage','--network',identifier,'--user',f'{os.getuid()}:{os.getgid()}',
                '-p','127.0.0.1::3000','-v',str(directory/'config')+':/app/config',
                '-e','HOMEPAGE_ALLOWED_HOSTS=widget.test',
                '-e','HOMEPAGE_AUTH_ENABLED=false',
                '-e','HOMEPAGE_VAR_BAMBUDDY_API_KEY='+key,image])
            port=runtime.run(docker+['port',identifier+'-homepage','3000/tcp'],capture=True).strip().rsplit(':',1)[1]
            api=media.Client('http://127.0.0.1:'+port)
            api.headers['Host']='widget.test'
            deadline=time.monotonic()+90
            while True:
                try:
                    groups=api.call('/api/services')
                    break
                except RuntimeError:
                    if time.monotonic()>deadline:
                        raise
                    time.sleep(2)
            assert key not in json.dumps(groups), 'Widget header leaked to browser configuration'
            result=api.call('/api/services/proxy?'+urllib.parse.urlencode({
                'group':'3D Print','service':'Bambuddy','index':0}))
            assert result==status, 'Custom API did not send the configured status header'
            assert key not in json.dumps(result), 'Key leaked through status response'
            print('Disposable pinned Homepage: custom header, status fields and browser credential exclusion passed')
        finally:
            runtime.run(docker+['rm','-f',identifier+'-homepage',identifier+'-api'])
            runtime.run(docker+['network','rm',identifier])


if __name__=='__main__':
    main()
