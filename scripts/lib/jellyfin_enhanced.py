"""Selective Enhanced QoL configuration using existing private integration keys."""
import copy
import datetime
import json
import os
from pathlib import Path
import re
import urllib.parse

import config
import credentials
import jellyfin_theme as theme
import media

PREFIX = '/JellyfinEnhanced/'
KEYS = {'HOMEPAGE_VAR_SEERR_API_KEY', 'SONARR_API_KEY', 'RADARR_API_KEY'}


def mapping(existing, jellyfin_url, target):
    lines = [line for line in (existing or '').splitlines() if line.strip()]
    if not any(line.partition('|')[0].rstrip('/').lower() == jellyfin_url.rstrip('/').lower() for line in lines):
        lines.append(jellyfin_url+'|'+target)
    return '\n'.join(lines)


def instance(existing, name, url, key, jellyfin_url, browser_url):
    try:
        entries = json.loads(existing or '[]')
    except ValueError:
        raise ValueError('Existing Enhanced instance list is invalid; preserve and review it') from None
    if not isinstance(entries, list) or any(not isinstance(row, dict) for row in entries):
        raise ValueError('Unexpected Enhanced instance list')
    entries = copy.deepcopy(entries)
    match = next((row for row in entries if row.get('Url', '').rstrip('/') == url), None)
    if match is None:
        match = {'Name':name, 'Url':url, 'Enabled':True}
        entries.append(match)
    if match.get('Enabled') is False:
        raise ValueError('Existing matching Enhanced instance is disabled; review before enabling it')
    match['ApiKey'] = key
    match['UrlMappings'] = mapping(match.get('UrlMappings'), jellyfin_url, browser_url)
    return json.dumps(entries)


def build(previous, profile, c, values):
    missing = set(profile['server'])-set(previous)
    if missing:
        raise ValueError('Installed Enhanced schema lacks profile fields: '+', '.join(sorted(missing)))
    updated = copy.deepcopy(previous)
    for key,value in profile['server'].items():
        if not isinstance(value, bool):
            raise ValueError('Enhanced QoL profile accepts only Boolean server settings')
        if key.endswith('UseNativeTab'):
            prefix = key.removesuffix('UseNativeTab')
            if previous.get(prefix+'UsePluginPages') or previous.get(prefix+'UseCustomTabs'):
                continue  # Keep explicitly chosen companion navigation integrations.
        updated[key] = value
    jf = 'https://'+c['JELLYFIN_HOST']
    seerr = 'http://seerr:5055'
    existing_urls = [line.strip().rstrip('/') for line in (previous.get('JellyseerrUrls') or '').splitlines() if line.strip()]
    if existing_urls and seerr not in existing_urls:
        raise ValueError('Enhanced already has a different Seerr connection; review before changing it')
    updated['JellyseerrUrls'] = previous.get('JellyseerrUrls') or seerr
    updated['JellyseerrApiKey'] = values['HOMEPAGE_VAR_SEERR_API_KEY']
    updated['JellyseerrUrlMappings'] = mapping(previous.get('JellyseerrUrlMappings'), jf, 'https://'+c['REQUESTS_HOST'])
    for service,port in [('Sonarr',8989),('Radarr',7878)]:
        url = f'http://{service.lower()}:{port}'
        if previous.get(service+'Url') and previous[service+'Url'].rstrip('/') != url and not json.loads(previous.get(service+'Instances') or '[]'):
            raise ValueError('Enhanced has a custom legacy '+service+' connection; preserve and review it')
        updated[service+'Instances'] = instance(previous.get(service+'Instances'), 'Ohara '+service,
            url, values[service.upper()+'_API_KEY'], jf, 'https://'+service.lower()+'.'+c['DOMAIN'])
    updated['BazarrUrl'] = previous.get('BazarrUrl') or 'https://bazarr.'+c['DOMAIN']
    return updated


def personal(previous, patch):
    if set(patch)-set(previous):
        raise ValueError('Installed Enhanced personal-settings schema differs from the profile')
    updated = {**previous, **patch}
    updated.pop('IsAdmin', None)  # Derived caller information is never a saved preference.
    return updated


def identify(api, profile):
    plugin = next((p for p in api.call('/Plugins') if p.get('Name') == 'Jellyfin Enhanced'), None)
    if not plugin or plugin.get('Status') != 'Active':
        raise ValueError('Install/activate Jellyfin Enhanced before configuration')
    if plugin.get('Version') != profile['tested_plugin_version']:
        raise ValueError('Enhanced version differs from the reviewed profile; review its schema first')
    compat = api.call(PREFIX+'host-compat')
    if compat.get('mismatch') or compat.get('stale'):
        raise ValueError('Enhanced reports an incompatible or stale installation')
    return plugin


def validate_services(api, values):
    for service,port,key in [('jellyseerr',5055,'HOMEPAGE_VAR_SEERR_API_KEY'),
                             ('sonarr',8989,'SONARR_API_KEY'),('radarr',7878,'RADARR_API_KEY')]:
        check = media.Client(api.base)
        check.headers = {**api.headers, 'X-Arr-ApiKey':values[key]}
        name = 'seerr' if service == 'jellyseerr' else service
        path = PREFIX+('jellyseerr/validate' if service=='jellyseerr' else 'arr/validate/'+service)
        data = check.call(path+'?'+urllib.parse.urlencode({'url':f'http://{name}:{port}'}))
        if data.get('ok') is not True:
            raise ValueError('Enhanced connection test failed: '+service)


def setup(c, root):
    import host
    api = theme.client(root)
    profile = json.loads((root/'configs/jellyfin/enhanced-qol.json').read_text())
    plugin = identify(api,profile)
    values = credentials.read(root/'.env', KEYS, ignored=config.KEYS | (credentials.ALL_KEYS-KEYS))
    validate_services(api,values)
    path = '/Plugins/'+plugin['Id']+'/Configuration'
    before = api.call(path)
    after = build(before,profile,c,values)
    backup = theme.safe(root/'local/jellyfin-enhanced-backups'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    for directory in (root/'local',backup.parent,backup):
        host.ensure_directory(directory,os.getuid(),os.getgid(),0o700)
    config.create_file(backup/'configuration.json',json.dumps(before,indent=2)+'\n')
    branding = api.call('/Branding/Configuration')
    config.create_file(backup/'branding.json',json.dumps(branding,indent=2)+'\n')
    records = []
    for user in api.call('/Users'):
        user_id = user['Id']
        if not re.fullmatch(r'[a-fA-F0-9-]{32,36}',user_id):
            raise ValueError('Unexpected Jellyfin user ID')
        target = PREFIX+'user-settings/'+user_id+'/settings.json'
        original = api.call(target)
        config.create_file(backup/(user_id+'.json'),json.dumps(original,indent=2)+'\n')
        records.append((target,original,personal(original,profile['personal'])))
    active_theme = bool((theme.state(c) or {}).get('enabled'))
    if active_theme:
        theme.prepare(c,root)
    if api.call(path) != before:
        raise ValueError('Enhanced configuration changed during setup; retry after reviewing it')
    changed = []
    try:
        api.call(path,after)
        for target,original,updated in records:
            changed.append((target,original))
            api.call(target,updated)
        if active_theme:
            api.call('/System/Configuration/Branding',{**branding,'CustomCss':theme.css(branding.get('CustomCss'))})
    except (ValueError,OSError,RuntimeError):
        failures = []
        for target,original in reversed(changed):
            try:api.call(target,original)
            except (ValueError,OSError,RuntimeError):failures.append(target)
        for target,original in [(path,before),('/System/Configuration/Branding',branding)]:
            try:api.call(target,original)
            except (ValueError,OSError,RuntimeError):failures.append(target)
        if failures:
            raise RuntimeError('Enhanced rollback incomplete; inspect private backup '+str(backup)) from None
        raise
    return backup,len(records)


def check(root):
    api = theme.client(root)
    profile = json.loads((root/'configs/jellyfin/enhanced-qol.json').read_text())
    plugin = identify(api,profile)
    values = credentials.read(root/'.env', KEYS, ignored=config.KEYS | (credentials.ALL_KEYS-KEYS))
    validate_services(api,values)
    data = api.call('/Plugins/'+plugin['Id']+'/Configuration')
    public = api.call(PREFIX+'public-config')
    secrets = list(values.values())+[v for k,v in data.items() if isinstance(v,str) and len(v)>=12 and ('apikey' in k.lower() or '_api_key' in k.lower() or 'secret' in k.lower())]
    text = json.dumps(public)
    if any(secret in text for secret in secrets):
        raise ValueError('Enhanced public configuration unexpectedly contains a private key')
    audit = api.call(PREFIX+'jellyseerr/permission-audit')
    print('Enhanced '+plugin['Version']+': Seerr/Sonarr/Radarr connection tests passed; public config excludes private keys.')
    print('Seerr linked accounts:',sum(bool(row.get('linked')) for row in audit),'/',len(audit))
    return audit


def restore(root, location):
    base = root/'local/jellyfin-enhanced-backups'
    path = Path(location)
    path = theme.safe(path if path.is_absolute() else base/path).resolve()
    if path == base.resolve() or base.resolve() not in path.parents:
        raise ValueError('Choose a private Enhanced backup inside local/jellyfin-enhanced-backups')
    api = theme.client(root)
    profile = json.loads((root/'configs/jellyfin/enhanced-qol.json').read_text())
    plugin = identify(api,profile)
    # Read and validate all input before restoring anything.
    original = json.loads(theme.safe(path/'configuration.json').read_text())
    branding = json.loads(theme.safe(path/'branding.json').read_text())
    users = []
    for file in path.glob('*.json'):
        if file.name in ('configuration.json','branding.json'):
            continue
        if not re.fullmatch(r'[a-fA-F0-9-]{32,36}',file.stem):
            raise ValueError('Unexpected file in Enhanced backup')
        users.append((file.stem,json.loads(theme.safe(file).read_text())))
    api.call('/Plugins/'+plugin['Id']+'/Configuration',original)
    for user_id,prefs in users:
        api.call(PREFIX+'user-settings/'+user_id+'/settings.json',prefs)
    api.call('/System/Configuration/Branding',branding)
    print('Enhanced configuration, selected branding snapshot and saved user preferences restored.')
