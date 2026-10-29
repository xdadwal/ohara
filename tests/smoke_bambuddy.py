#!/usr/bin/env python3
"""Disposable official Bambuddy check; never connects a printer or starts a print."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts/lib'))
import bambuddy
import config
import media
import runtime


def main():
    docker = runtime.docker_prefix()
    project = 'ohara-bambuddy-smoke-'+uuid.uuid4().hex[:10]
    (ROOT/'local').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='bambuddy-smoke-', dir=ROOT/'local') as d:
        root = Path(d).resolve()
        for name in ('compose.bambuddy.yaml', 'versions.bambuddy.env'):
            shutil.copy(ROOT/name, root/name)
        c = config.load(ROOT/'.env.example')
        c.update(DATA_ROOT=str(root/'state'), RUN_UID=str(os.getuid() or 1000), RUN_GID=str(os.getgid() or 1000))
        base, _ = bambuddy.settings(c)
        for p in (base/'data', base/'logs'):
            p.mkdir(parents=True, mode=0o700)
            if os.geteuid() == 0:
                os.chown(p, int(c['RUN_UID']), int(c['RUN_GID']))
        model = json.loads(bambuddy.compose(c, root, ['config', '--format', 'json'], capture=True))
        model['name'] = project
        model['services']['bambuddy']['ports'] = [{'target': 8000, 'published': '0', 'host_ip': '127.0.0.1'}]
        fixture = root/'fixture.json'
        fixture.write_text(json.dumps(model))
        command = docker+['compose', '--project-name', project, '--file', str(fixture)]
        def call(*args, **kw):
            return runtime.run(command+list(args), **kw)
        try:
            call('up', '-d', '--wait', '--wait-timeout', '180', timeout=240)
            endpoint = call('port', 'bambuddy', '8000', capture=True).strip()
            api = media.Client('http://'+endpoint)
            assert api.call('/health')['status'] == 'healthy'
            status = api.call('/api/v1/auth/status')
            assert status['requires_setup'] and not status['auth_enabled']
            identifier = call('ps', '-q', 'bambuddy', capture=True).strip()
            state = json.loads(runtime.run(docker+['inspect', identifier], capture=True))[0]
            assert state['Config']['User'] == c['RUN_UID']+':'+c['RUN_GID']
            assert not state['HostConfig']['Privileged'] and state['HostConfig']['NetworkMode'] != 'host'
            assert api.call('/api/v1/printers/') == []
            db = base/'data/bambuddy.db'
            assert db.exists() and db.stat().st_size > 0
            marker = base/'data/disposable-preservation-marker'
            marker.write_text('keep')
            gateway = bambuddy.proxy_gateway(docker, project=project)
            model['services']['bambuddy']['environment'].update(TRUSTED_PROXY_IPS=gateway, FORWARDED_ALLOW_IPS=gateway)
            fixture.write_text(json.dumps(model))
            call('up', '-d', '--force-recreate', '--wait', '--wait-timeout', '180', timeout=240)
            endpoint = call('port', 'bambuddy', '8000', capture=True).strip()
            api = media.Client('http://'+endpoint)
            assert marker.read_text() == 'keep' and db.exists()
            assert api.call('/api/v1/auth/status')['requires_setup']
            identifier = call('ps', '-q', 'bambuddy', capture=True).strip()
            probe = """from starlette.requests import Request
from backend.app.api.routes.auth import _get_client_ip
import os
trusted=os.environ['TRUSTED_PROXY_IPS']
def check(peer, forwarded):
 r=Request({'type':'http','client':(peer,1234),'headers':[(b'x-forwarded-for',forwarded.encode())]})
 return _get_client_ip(r)
assert check(trusted,'198.51.100.7')=='198.51.100.7'
assert check('203.0.113.8','198.51.100.7')=='203.0.113.8'
"""
            runtime.run(docker+['exec',identifier,'python','-c',probe])
            print('PASS: pinned Bambuddy non-root readiness, state recreation, exact gateway proxy trust/spoof rejection; no printers/accounts/jobs created')
        finally:
            call('down', '--timeout', '30', timeout=90)


if __name__ == '__main__':
    main()
