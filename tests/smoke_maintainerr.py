"""Disposable official Maintainerr startup/restart with no real media connections."""
import json
import os
from pathlib import Path
import sys
import tempfile
import uuid
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts/lib'))
import config
import maintainerr
import media
import runtime


def main():
    docker=runtime.docker_prefix()
    project='ohara-maintainerr-smoke-'+uuid.uuid4().hex[:10]
    with tempfile.TemporaryDirectory(prefix=project) as d:
        root=Path(d)
        c=config.load(ROOT/'.env.example')
        c.update(DATA_ROOT=d,RUN_UID=str(os.getuid()),RUN_GID=str(os.getgid()))
        maintainerr.prepare(c,ROOT)
        model=json.loads(maintainerr.compose(c,ROOT,['config','--format','json'],capture=True))
        model['name']=project
        model['networks']={'default':{}}
        model['services']['maintainerr']['ports'][0]['published']='0'
        file=root/'compose.json';file.write_text(json.dumps(model))
        env={k:v for k,v in os.environ.items() if k in {'PATH','HOME','DOCKER_HOST','DOCKER_CONTEXT','DOCKER_CONFIG','XDG_RUNTIME_DIR'}}
        env['COMPOSE_DISABLE_ENV_FILE']='1'
        def compose(args):return runtime.run(docker+['compose','--env-file','/dev/null','-p',project,'-f',str(file)]+args,env=env,capture=True,timeout=240)
        try:
            compose(['up','-d','--wait','--wait-timeout','180'])
            port=compose(['port','maintainerr','6246']).strip().rsplit(':',1)[1]
            api=media.Client('http://127.0.0.1:'+port)
            api.call('/api/health/ready')
            assert api.call('/api/rules')==[] and api.call('/api/collections')==[]
            api.call('/api/settings',{'applicationTitle':'Disposable restart verification'},method='PATCH')
            compose(['up','-d','--force-recreate','--wait','--wait-timeout','180'])
            port=compose(['port','maintainerr','6246']).strip().rsplit(':',1)[1]
            api=media.Client('http://127.0.0.1:'+port)
            assert api.call('/api/settings')['applicationTitle']=='Disposable restart verification'
            assert api.call('/api/rules')==[] and api.call('/api/collections')==[]
            print('PASS: official Maintainerr non-root startup, readiness, state after recreation, no rules/collections or media mounts.')
        finally:
            compose(['down','--remove-orphans'])

if __name__=='__main__':main()
