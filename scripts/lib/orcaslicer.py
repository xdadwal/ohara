"""Private optional OrcaSlicer backend; never dispatches printer commands."""
import json
import os
import platform
import re
import bambuddy
import config
import host
import runtime


def images(root):
    values = config.parse(root/'versions/orcaslicer.env', {'ORCASLICER_IMAGE'})
    if not re.fullmatch(r'ghcr.io/maziggy/orca-slicer-api:bambuddy-[0-9.]+@sha256:[a-f0-9]{64}', values['ORCASLICER_IMAGE']):
        raise ValueError('OrcaSlicer requires a reviewed release-matched immutable image')
    return values


def storage(c):
    base, _ = bambuddy.settings(c)
    path = base/'orcaslicer'
    if path.is_symlink():
        raise ValueError('OrcaSlicer storage must not be a symlink')
    return path


def compose(c, root, args, *, capture=False):
    values = images(root) | {k:c[k] for k in ('RUN_UID', 'RUN_GID')}
    values.update(ORCASLICER_ROOT=str(storage(c)), COMPOSE_DISABLE_ENV_FILE='1')
    env = {k:v for k,v in os.environ.items() if k in
           {'PATH','HOME','USER','XDG_RUNTIME_DIR','DOCKER_CONFIG','DOCKER_HOST','DOCKER_CONTEXT','SSH_AUTH_SOCK'}}
    env.update(values)
    prefix = ['docker'] if args[0] == 'config' else runtime.docker_prefix()
    if prefix[:2] == ['sudo','-n']:
        prefix = prefix[:2]+['--preserve-env='+','.join(sorted(values))]+prefix[2:]
    return runtime.run(prefix+['compose','--project-directory',str(root),'--env-file','/dev/null',
        '-f',str(root/'compose/orcaslicer.yaml'),*args],env=env,capture=capture,timeout=600)


def check(c, root, *, static=False):
    if platform.machine() not in {'x86_64','AMD64'}:
        raise ValueError('This reviewed sidecar requires native x86-64; emulation is not configured')
    model = json.loads(compose(c,root,['config','--format','json'],capture=True))
    s = model['services']['orcaslicer']
    if (set(model['services']) != {'orcaslicer'} or model['name'] != 'ohara-orcaslicer'
            or s.get('ports') or s.get('privileged') or s.get('network_mode')
            or s['image'] != images(root)['ORCASLICER_IMAGE']
            or set(s.get('networks',{})) != {'bambuddy'}
            or model.get('networks',{}).get('bambuddy',{}).get('name') != 'ohara-bambuddy_default'
            or not model['networks']['bambuddy'].get('external')
            or s['user'] != c['RUN_UID']+':'+c['RUN_GID']
            or s.get('cap_drop') != ['ALL'] or s.get('cap_add')
            or 'no-new-privileges:true' not in s.get('security_opt', [])
            or len(s.get('volumes',[])) != 1
            or s['volumes'][0]['source'] != str(storage(c))
            or s['volumes'][0]['target'] != '/app/data'
            or s['volumes'][0].get('bind',{}).get('create_host_path',False)):
        raise ValueError('OrcaSlicer must retain private networking, dedicated storage and non-root isolation')
    if not static:
        bambuddy.require_storage(c)
        path = storage(c)
        if not path.is_dir() or not config.directory_writable(path,int(c['RUN_UID']),int(c['RUN_GID'])):
            raise ValueError('Run sudo scripts/orcaslicer prepare first')
        # Inspect ownership/gateway; do not create an unrelated network.
        prefix = runtime.docker_prefix()
        runtime.run(prefix+['network','inspect','ohara-bambuddy_default'],capture=True)
        bambuddy.proxy_gateway(prefix)
    print('OrcaSlicer configuration valid'+(' (static only)' if static else ''))


def prepare(c,root):
    check(c,root,static=True)
    bambuddy.require_storage(c)
    host.ensure_directory(storage(c),int(c['RUN_UID']),int(c['RUN_GID']),0o700)
    check(c,root)
