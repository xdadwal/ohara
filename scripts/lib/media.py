"""Initial media storage using user-supplied credentials; existing state is never replaced."""
import base64
import hashlib
from pathlib import Path
import secrets
import credentials as credential_files

PORTS = {'radarr': 7878, 'sonarr': 8989, 'prowlarr': 9696, 'lidarr': 8686}
SECRET_KEYS = credential_files.MEDIA_KEYS


def prepare(c, root, create, directory, owner, group):
    _, values = credential_files.load(root)
    uid, gid = int(c['RUN_UID']), int(c['RUN_GID'])
    data = Path(c['DATA_ROOT'])
    media = Path(c.get('MEDIA_ROOT', str(data / 'media')))
    for name in ['jellyfin', 'jellyfin-cache', 'radarr', 'sonarr', 'prowlarr', 'qbittorrent', 'lidarr', 'bazarr', 'navidrome']:
        directory(data / name, uid, gid)
    directory(media, uid, gid)
    for name in ['downloads', 'library', 'recycle-bin', 'downloads/incomplete', 'downloads/complete',
                 'downloads/complete/movies', 'downloads/complete/tv', 'downloads/complete/music',
                 'library/movies', 'library/tv', 'library/music', 'recycle-bin/movies', 'recycle-bin/tv']:
        directory(media / name, uid, gid)
    for name, port in PORTS.items():
        # API keys permit the connector to set forms authentication through the API.
        # Do not expose these loopback-only services through Nginx.
        create(data / name / 'config.xml', '<Config>\n'
               f'  <Port>{port}</Port><BindAddress>*</BindAddress>\n'
               f'  <ApiKey>{values[name.upper()+"_API_KEY"]}</ApiKey>\n'
               '  <AuthenticationMethod>Forms</AuthenticationMethod>\n'
               '  <AuthenticationRequired>Enabled</AuthenticationRequired>\n'
               '  <LaunchBrowser>False</LaunchBrowser><UpdateMechanism>Docker</UpdateMechanism>\n'
               '</Config>\n', uid, gid)
    directory(data / 'bazarr/config', uid, gid)
    import bazarr
    bazarr.prepare(data, values, create, uid, gid)
    directory(data / 'qbittorrent/qBittorrent', uid, gid)
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha512', values['QBITTORRENT_PASSWORD'].encode(), salt, 100000, 64)
    password = base64.b64encode(salt).decode() + ':' + base64.b64encode(digest).decode()
    create(data/'qbittorrent/qBittorrent/qBittorrent.conf',
           '[Preferences]\nWebUI\\Username=admin\nWebUI\\Password_PBKDF2="@ByteArray(' + password + ')"\n'
           'WebUI\\LocalHostAuth=true\nWebUI\\AuthSubnetWhitelistEnabled=false\n'
           '[BitTorrent]\nSession\\DefaultSavePath=/data/downloads/complete\n'
           'Session\\TempPath=/data/downloads/incomplete\nSession\\TempPathEnabled=true\n', uid, gid)


class Client:
    """Bounded local JSON/form requests; never include responses/secrets in errors."""
    def __init__(self, base, key=None):
        import http.cookiejar
        import urllib.request
        self.base = base
        self.headers = {'X-Api-Key': key} if key else {}
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                         urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def call(self, path, body=None, method=None, form=False):
        import json
        import urllib.parse
        import urllib.request
        import urllib.error
        headers = {'Referer':self.base+'/', **self.headers}
        data = None
        if body is not None:
            data = (urllib.parse.urlencode(body) if form else json.dumps(body)).encode()
            headers['Content-Type'] = 'application/x-www-form-urlencoded' if form else 'application/json'
        req = urllib.request.Request(self.base + path, data=data, headers=headers,
                                     method=method or ('POST' if data is not None else 'GET'))
        try:
            with self.opener.open(req, timeout=30) as response:
                raw = response.read()
        except (OSError, urllib.error.URLError) as error:
            code = getattr(error, 'code', 'unreachable')
            raise RuntimeError(f'Media API operation failed ({code}): {self.base}{path.split("?")[0]}; inspect service locally') from None
        try:
            return json.loads(raw) if raw else None
        except (ValueError, UnicodeDecodeError):
            return raw.decode()


def fields(resource, values):
    for field in resource['fields']:
        if field['name'] in values:
            field['value'] = values[field['name']]
    return resource


def configure_storage(root, urls=None):
    """Apply storage policy without owner initialization or relocating torrents."""
    import json
    _, values = credential_files.load(root)
    urls = urls or {**{name: f'http://127.0.0.1:{port}' for name, port in PORTS.items()},
                    'qbittorrent': 'http://127.0.0.1:8081'}
    qb = Client(urls['qbittorrent'])
    qb.headers.update(Host='127.0.0.1:8081', Referer='http://127.0.0.1:8081/')
    qb.call('/api/v2/auth/login', {'username':'admin', 'password':values['QBITTORRENT_PASSWORD']}, form=True)
    preferences = qb.call('/api/v2/app/preferences')
    if not isinstance(preferences, dict) or 'auto_tmm_enabled' not in preferences:
        raise ValueError('qBittorrent did not return authenticated storage preferences')
    categories = qb.call('/api/v2/torrents/categories')
    for category in ('movies', 'tv'):
        path = '/data/downloads/complete/'+category
        if category in categories and categories[category].get('savePath') != path:
            # Editing a category can relocate existing automatically managed torrents.
            raise ValueError(f'qBittorrent {category} category has a custom path; review relocation before changing it')
    # Reaching a seeding limit can immediately trigger Arr's removal of both the
    # torrent and source. Disable cleanup in both services BEFORE changing limits.
    for name in ('radarr', 'sonarr'):
        client = Client(urls[name], values[name.upper()+'_API_KEY'])
        for download in client.call('/api/v3/downloadclient'):
            if download.get('name') == 'Ohara qBittorrent' and download.get('removeCompletedDownloads'):
                download['removeCompletedDownloads'] = False
                client.call('/api/v3/downloadclient/'+str(download['id']), download, 'PUT')
    policy = {'auto_tmm_enabled':True, 'max_ratio_enabled':False,
              'max_ratio_act':3, 'max_seeding_time_enabled':True, 'max_seeding_time':4320,
              'max_inactive_seeding_time_enabled':False}
    if any(preferences.get(key) != value for key, value in policy.items()):
        qb.call('/api/v2/app/setPreferences', {'json':json.dumps(policy)}, form=True)
    for category in ('movies', 'tv'):
        path = '/data/downloads/complete/'+category
        if category not in categories:
            qb.call('/api/v2/torrents/createCategory', {'category':category, 'savePath':path}, form=True)
    for name, category in [('radarr', 'movies'), ('sonarr', 'tv')]:
        client = Client(urls[name], values[name.upper()+'_API_KEY'])
        settings = client.call('/api/v3/config/mediamanagement')
        before = dict(settings)
        settings['copyUsingHardlinks'] = True
        if not settings.get('recycleBin'):
            settings.update(recycleBin='/data/recycle-bin/'+category, recycleBinCleanupDays=7)
        if settings != before:
            client.call('/api/v3/config/mediamanagement', settings, 'PUT')
    print('Storage policy applied: automatic category paths for new torrents, hardlinks, '
          'recycle bins, and removal of torrents/download files after 72 hours of seeding. '
          'Existing torrent states/overrides and custom recycle settings preserved.')


def connect(c, root, email, urls=None):
    """Configure first-run accounts/connections via supported APIs, preserve reruns."""
    import json
    import re
    if not re.fullmatch(r'[A-Za-z0-9._+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}', email):
        raise ValueError('Supply the real Seerr owner email with --owner-email')
    _, values = credential_files.load(root)
    urls = urls or {**{name: f'http://127.0.0.1:{port}' for name, port in PORTS.items()},
                    'qbittorrent': 'http://127.0.0.1:8081', 'jellyfin': 'http://127.0.0.1:8096',
                    'seerr': 'http://127.0.0.1:5055', 'navidrome': 'http://127.0.0.1:4533'}
    statefile = root/'local/media-state.json'
    if statefile.is_symlink():
        raise ValueError('Symlink private configuration is unsupported')
    state = json.loads(statefile.read_text()) if statefile.exists() else {}
    def done(name):
        state[name] = True
        # Private directory; atomic replacement avoids a torn journal on interruption.
        import os
        import tempfile
        descriptor, name_tmp = tempfile.mkstemp(dir=statefile.parent, prefix='.media-state-')
        try:
            with os.fdopen(descriptor, 'w') as stream:
                json.dump(state, stream)
            os.replace(name_tmp, statefile)
        finally:
            if os.path.exists(name_tmp):
                os.unlink(name_tmp)
    arr = {name: Client(urls[name], values[name.upper()+'_API_KEY']) for name in PORTS}
    for name, client in arr.items():
        version = '/api/v1' if name in ('prowlarr', 'lidarr') else '/api/v3'
        if not state.get(name+'-auth'):
            resource = client.call(version+'/config/host')
            resource.update(username='admin', password=values[name.upper()+'_PASSWORD'],
                            passwordConfirmation=values[name.upper()+'_PASSWORD'],
                            authenticationMethod='forms', authenticationRequired='enabled')
            client.call(version+'/config/host', resource, 'PUT')
            done(name+'-auth')
    qb = Client(urls['qbittorrent'])
    qb.headers.update(Host='127.0.0.1:8081', Referer='http://127.0.0.1:8081/')
    qb.call('/api/v2/auth/login', {'username':'admin', 'password':values['QBITTORRENT_PASSWORD']}, form=True)
    categories = qb.call('/api/v2/torrents/categories')
    # Set explicit paths before Arr tests, which can otherwise create categories
    # with qBittorrent's generic default path. Preserve existing category paths.
    for category in ('movies', 'tv', 'music'):
        if category not in categories:
            qb.call('/api/v2/torrents/createCategory', {'category':category,
                    'savePath':'/data/downloads/complete/'+category}, form=True)
    for name, category in [('radarr', 'movies'), ('sonarr', 'tv'), ('lidarr', 'music')]:
        client = arr[name]
        version = '/api/v1' if name == 'lidarr' else '/api/v3'
        path = '/data/library/'+category
        if not any(folder['path'] == path for folder in client.call(version+'/rootfolder')):
            resource = {'path': path}
            if name == 'lidarr':
                profiles = client.call(version+'/qualityprofile')
                metadata = client.call(version+'/metadataprofile')
                if not profiles or not metadata:
                    raise ValueError('Lidarr requires quality and metadata profiles; configure them privately first')
                resource.update(name='Music', defaultQualityProfileId=profiles[0]['id'], defaultMetadataProfileId=metadata[0]['id'],
                                defaultMonitorOption='all', defaultNewItemMonitorOption='all', defaultTags=[])
            client.call(version+'/rootfolder', resource)
        if not any(item['name'] == 'Ohara qBittorrent' for item in client.call(version+'/downloadclient')):
            schema = next(item for item in client.call(version+'/downloadclient/schema') if item['implementation']=='QBittorrent')
            schema.update(name='Ohara qBittorrent', enable=True, priority=1, removeCompletedDownloads=False)
            fields(schema, {'host':'qbittorrent', 'port':8081, 'useSsl':False, 'username':'admin',
                            'password':values['QBITTORRENT_PASSWORD'],
                            'movieCategory':category, 'tvCategory':category, 'musicCategory':category})
            client.call(version+'/downloadclient/test', schema)
            client.call(version+'/downloadclient', schema)
        prowlarr = arr['prowlarr']
        if not any(item['name'] == 'Ohara '+name for item in prowlarr.call('/api/v1/applications')):
            schema = next(item for item in prowlarr.call('/api/v1/applications/schema') if item['implementation']==name.capitalize())
            schema.update(name='Ohara '+name, syncLevel='fullSync')
            fields(schema, {'baseUrl':f'http://{name}:{PORTS[name]}', 'prowlarrUrl':'http://prowlarr:9696',
                            'apiKey':values[name.upper()+'_API_KEY']})
            prowlarr.call('/api/v1/applications/test', schema)
            prowlarr.call('/api/v1/applications', schema)
    # Fresh Arr connection tests reject automatic removal below 14 days. Validate
    # and register clients before applying the owner's shorter retention policy.
    # Existing clients are preserved on reruns; storage-only remains independent.
    configure_storage(root, urls)
    import navidrome
    navidrome.connect(urls['navidrome'], values['NAVIDROME_PASSWORD'])
    jf = Client(urls['jellyfin'])
    jf.headers['Authorization'] = 'MediaBrowser Client="Ohara", Device="Setup", DeviceId="ohara-setup", Version="1"'
    if not jf.call('/System/Info/Public')['StartupWizardCompleted']:
        jf.call('/Startup/Configuration', {'UICulture':'en-US', 'MetadataCountryCode':'US', 'PreferredMetadataLanguage':'en'})
        jf.call('/Startup/User')  # initializes the first user on current Jellyfin
        try:
            jf.call('/Startup/User', {'Name':'admin', 'Password':values['JELLYFIN_PASSWORD']})
        except RuntimeError:
            # A previous run may have set the password before wizard completion.
            # Prove it is ours rather than resetting an existing account.
            jf.call('/Users/AuthenticateByName', {'Username':'admin', 'Pw':values['JELLYFIN_PASSWORD']})
        jf.call('/Startup/RemoteAccess', {'EnableRemoteAccess':True, 'EnableAutomaticPortMapping':False})
        jf.call('/Startup/Complete', {}, 'POST')
    jf.headers['Authorization'] = 'MediaBrowser Client="Ohara", Device="Setup", DeviceId="ohara-setup", Version="1"'
    account = jf.call('/Users/AuthenticateByName', {'Username':'admin', 'Pw':values['JELLYFIN_PASSWORD']})
    jf.headers['Authorization'] += ', Token="'+account['AccessToken']+'"'
    libraries = jf.call('/Library/VirtualFolders')
    import urllib.parse
    for title, category, kind in [('Movies','movies','movies'), ('TV Shows','tv','tvshows')]:
        path = '/media/'+category
        if not any(path in item.get('Locations', []) for item in libraries):
            query = urllib.parse.urlencode({'name':title, 'collectionType':kind, 'refreshLibrary':'true'})
            jf.call('/Library/VirtualFolders?'+query, {'LibraryOptions': {'PathInfos':[{'Path':path}],
                    'EnableRealtimeMonitor':True}}, 'POST')
    # Host Nginx is outside the Docker network. Jellyfin must trust its actual
    # Docker bridge gateway for forwarded client addresses; see the setup guide.
    seerr = Client(urls['seerr'])
    public = seerr.call('/api/v1/settings/public')
    login = {'username':'admin', 'password':values['JELLYFIN_PASSWORD']}
    if public.get('mediaServerType') == 4:
        login.update(hostname='jellyfin', port=8096, useSsl=False, urlBase='', email=email, serverType=2)
    seerr.call('/api/v1/auth/jellyfin', login)
    if not state.get('seerr-jellyfin'):
        seerr.call('/api/v1/settings/main', {'applicationUrl':'https://'+c['REQUESTS_HOST']})
        seerr.call('/api/v1/settings/jellyfin', {'externalHostname':'https://'+c['JELLYFIN_HOST']})
        libraries = seerr.call('/api/v1/settings/jellyfin/library/sync', {})
        for library in libraries:
            if library['name'] in ('Movies', 'TV Shows'):
                seerr.call('/api/v1/settings/jellyfin/library/'+library['id'], {'enabled':True}, 'PUT')
        done('seerr-jellyfin')
    for name, category in [('radarr','movies'), ('sonarr','tv')]:
        existing = seerr.call('/api/v1/settings/'+name)
        if any(item['hostname'] == name for item in existing):
            continue
        if existing:
            raise ValueError(f'Seerr already has a {name} server; review defaults manually, existing settings preserved')
        profiles = arr[name].call('/api/v3/qualityprofile')
        profile = next((item for item in profiles if item['name']=='HD-1080p'), None)
        if profile is None:
            raise ValueError(f'{name}: default HD-1080p profile missing; select a profile manually')
        resource = dict(name='Ohara '+name, hostname=name, port=PORTS[name],
            apiKey=values[name.upper()+'_API_KEY'], useSsl=False, baseUrl='',
            activeProfileId=profile['id'], activeProfileName=profile['name'], activeDirectory='/data/library/'+category,
            tags=[], is4k=False, isDefault=True, syncEnabled=True, preventSearch=False,
            tagRequests=False, overrideRule=[], minimumAvailability='released',
            seriesType='standard', animeSeriesType='standard', enableSeasonFolders=True, monitorNewItems='all')
        seerr.call('/api/v1/settings/'+name+'/test', resource)
        seerr.call('/api/v1/settings/'+name, resource)
    if not public.get('initialized'):
        seerr.call('/api/v1/settings/initialize', {})
    import media_quality
    media_quality.apply(root, urls)
    print('Media accounts and connections configured. Add indexers in Prowlarr and verify a permitted request end to end.')
