"""Reviewed LetterboxdSync installation through Jellyfin's package API."""
import datetime
import hashlib
import io
import json
import os
from pathlib import Path
import urllib.parse
import urllib.request
import zipfile

import config
import host
import jellyfin_theme as theme
import runtime


def profile(root):
    return json.loads((root/'configs/jellyfin/letterboxd-sync.json').read_text())


def verify_release(data,p):
    if hashlib.sha256(data).hexdigest()!=p['zip_sha256']:
        raise ValueError('LetterboxdSync release hash differs from the reviewed artifact')
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        if archive.namelist()!=['LetterboxdSync.dll']:
            raise ValueError('Unexpected LetterboxdSync archive layout')
        if hashlib.sha256(archive.read('LetterboxdSync.dll')).hexdigest()!=p['dll_sha256']:
            raise ValueError('LetterboxdSync assembly differs from the reviewed release')


def installed(api,p):
    return next((v for v in api.call('/Plugins') if v['Id'].replace('-','').lower()==p['id'].replace('-','')),None)


def verify_installed(c,p):
    path=theme.safe(Path(c['DATA_ROOT'])/'jellyfin/plugins'/(p['name']+'_'+p['version'])/'LetterboxdSync.dll')
    if hashlib.sha256(path.read_bytes()).hexdigest()!=p['dll_sha256']:
        raise ValueError('Installed plugin hash differs; do not restart until reviewed')


def install(c,root):
    p=profile(root);api=theme.client(root)
    if api.call('/System/Info/Public')['Version']!=p['tested_jellyfin_version']:
        raise ValueError('Review LetterboxdSync compatibility against this Jellyfin version first')
    existing=installed(api,p)
    if existing:
        if existing['Version']!=p['version'] or existing['Status'] not in ('Active','Restart'):
            raise ValueError('Existing LetterboxdSync version/state differs; preserve and review')
        verify_installed(c,p)
        print('Existing reviewed LetterboxdSync installation preserved.')
        return existing['Status']=='Restart'
    # Fetch the exact public asset before changing repository configuration.
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(p['source_url'],timeout=60) as response:
        data=response.read(10*1024*1024+1)
    verify_release(data,p)
    repos=api.call('/Repositories')
    matching=[r for r in repos if r['Url']==p['manifest_url']]
    if matching and any(not r['Enabled'] for r in matching):
        raise ValueError('Existing LetterboxdSync repository is disabled; preserve and review')
    backup=root/'local/jellyfin-letterboxd-backups'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    for path in (root/'local',backup.parent,backup):host.ensure_directory(path,os.getuid(),os.getgid(),0o700)
    config.create_file(backup/'repositories.json',json.dumps(repos,indent=2)+'\n')
    config.create_file(backup/'plugins.json',json.dumps(api.call('/Plugins'),indent=2)+'\n')
    if not matching:
        if api.call('/Repositories')!=repos:
            raise ValueError('Plugin repositories changed during setup; review before retrying')
        api.call('/Repositories',repos+[{'Name':'Letterboxd Sync','Url':p['manifest_url'],'Enabled':True}])
    query=urllib.parse.urlencode({'assemblyGuid':p['id'],'version':p['version'],'repositoryUrl':p['manifest_url']})
    api.call('/Packages/Installed/'+p['name']+'?'+query,method='POST')
    # Verify the installed binary before allowing a restart to load it.
    verify_installed(c,p)
    print('LetterboxdSync '+p['version']+' installed and verified; Jellyfin restart required.')
    return True


def restart(c,root):
    api=theme.client(root)
    if any(s.get('NowPlayingItem') for s in api.call('/Sessions')):
        raise ValueError('Playback session exists; restart when viewers finish')
    # Preserve the read-only Abyss overlay, image pin and all existing mounts.
    runtime.compose(c,root,['up','-d','--no-deps','--force-recreate','--wait','--wait-timeout','120','jellyfin'],timeout=180)


def check(root):
    api=theme.client(root);p=profile(root);plugin=installed(api,p)
    if not plugin or plugin['Status']!='Active' or plugin['Version']!=p['version']:
        raise ValueError('Reviewed LetterboxdSync is not active; check pending restart/version')
    settings=api.call('/Plugins/'+plugin['Id']+'/Configuration')
    print('LetterboxdSync '+plugin['Version']+' active; configuration API readable; configured accounts: '+str(len(settings.get('Accounts',[]))))
    print('Outgoing sync in this release can resubmit old watches and duplicate diary entries; keep account Enable and real-time sync disabled. See docs/jellyfin-letterboxd.md.')
    print('No sync is triggered by this check.')
