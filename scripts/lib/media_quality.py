"""Explicit, bounded 1080p acquisition policy; never searches or changes files."""
import credentials
from media import Client

ALLOWED = {'HDTV-1080p', 'WEBDL-1080p', 'WEBRip-1080p', 'Bluray-1080p'}


def configure(profile):
    """Preserve profile ordering/custom formats, recursively restrict qualities."""
    found = set()
    def restrict(items):
        for item in items:
            if item.get('items'):
                restrict(item['items'])
                item['allowed'] = any(child['allowed'] for child in item['items'])
            else:
                name = item.get('quality', {}).get('name')
                item['allowed'] = name in ALLOWED
                if item['allowed']:
                    found.add(name)
    restrict(profile['items'])
    if found != ALLOWED:
        raise ValueError('HD-1080p profile lacks expected qualities; review manually')
    profile['upgradeAllowed'] = False
    return profile


def apply(root, urls=None):
    _, values = credentials.load(root)
    urls = urls or {'radarr':'http://127.0.0.1:7878', 'sonarr':'http://127.0.0.1:8989'}
    # Arr uses MiB/min: approximately 10 decimal GB/120 min and 2.5 GB/45 min.
    plans = []
    for name, minimum, preferred, maximum in [('radarr', 8, 30, 79.47), ('sonarr', 5, 20, 52.98)]:
        client = Client(urls[name], values[name.upper()+'_API_KEY'])
        profiles = client.call('/api/v3/qualityprofile')
        profile = next((x for x in profiles if x['name'] == 'HD-1080p'), None)
        if profile is None:
            raise ValueError(name+': HD-1080p profile missing; review manually')
        configure(profile)
        definitions = [x for x in client.call('/api/v3/qualitydefinition') if x['quality']['name'] in ALLOWED]
        if {x['quality']['name'] for x in definitions} != ALLOWED:
            raise ValueError(name+': expected quality definitions missing; review manually')
        for row in definitions:
            row.update(minSize=minimum, preferredSize=preferred, maxSize=maximum)
        plans.append((name, client, profile, definitions))
    # Validate both services before applying any writes. API failures can still
    # leave earlier steps applied; reruns converge without initiating downloads.
    for name, client, profile, definitions in plans:
        for row in definitions:
            client.call('/api/v3/qualitydefinition/'+str(row['id']), row, 'PUT')
        client.call('/api/v3/qualityprofile/'+str(profile['id']), profile, 'PUT')
        print(name+': HD-1080p restricted to encoded 1080p; size limits applied; upgrades disabled')
