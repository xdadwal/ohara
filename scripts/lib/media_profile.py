"""Apply explicitly selected non-secret settings to an existing media stack."""
import json

import credentials
from media import Client


def apply(root, *, urls=None):
    _, values = credentials.load(root)
    profile = json.loads((root / 'configs/media/ohara.json').read_text())
    if (set(profile) != {'indexers', 'rename'} or profile['rename'] is not True
            or not isinstance(profile['indexers'], list)
            or not all(isinstance(x, str) for x in profile['indexers'])):
        raise ValueError('Invalid Ohara media profile')
    urls = urls or {'radarr': 'http://127.0.0.1:7878',
                    'sonarr': 'http://127.0.0.1:8989', 'prowlarr': 'http://127.0.0.1:9696'}
    prowlarr = Client(urls['prowlarr'], values['PROWLARR_API_KEY'])
    existing = prowlarr.call('/api/v1/indexer')
    schemas = prowlarr.call('/api/v1/indexer/schema')
    app_profiles = prowlarr.call('/api/v1/appprofile')
    if not app_profiles:
        raise ValueError('Prowlarr requires an application profile before adding indexers')
    # Fail before changes if the installed definitions do not support this profile.
    available = {row.get('definitionName'): row for row in schemas}
    missing = set(profile['indexers']) - set(available)
    if missing:
        raise ValueError('Unavailable Prowlarr definitions: ' + ', '.join(sorted(missing)))
    for name in profile['indexers']:
        if any(row.get('definitionName') == name or any(
                f.get('name') == 'definitionFile' and f.get('value') == name
                for f in row.get('fields', [])) for row in existing):
            print('Existing indexer preserved: ' + name)
            continue
        row = available[name]
        if not row.get('indexerUrls'):
            raise ValueError('Indexer has no supported endpoint: ' + name)
        row.update(enable=True, appProfileId=app_profiles[0]['id'], priority=25, tags=[])
        for field in row['fields']:
            if field['name'] == 'baseUrl':
                field['value'] = row['indexerUrls'][0]
        prowlarr.call('/api/v1/indexer/test', row)
        prowlarr.call('/api/v1/indexer', row)
        print('Added and tested indexer: ' + name)
    for name in ('radarr', 'sonarr'):
        client = Client(urls[name], values[name.upper() + '_API_KEY'])
        naming = client.call('/api/v3/config/naming')
        key = 'renameMovies' if name == 'radarr' else 'renameEpisodes'
        if not naming.get(key):
            naming[key] = True
            client.call('/api/v3/config/naming', naming, 'PUT')
        print(name + ': renaming enabled; existing formats preserved')
    prowlarr.call('/api/v1/command', {'name': 'ApplicationIndexerSync'})
    print('Indexer synchronization queued. Check each application for category/search failures; '
          'full download/import/playback verification is still required.')
