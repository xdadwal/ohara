"""Seed Bazarr 1.6.2 on first run, preserving existing YAML/legacy INI.

Languages, language profiles, provider selection and provider credentials remain
pending manual configuration in Bazarr. Shared /data/library paths require no
Sonarr/Radarr path mappings. Schema and MD5 password encoding follow upstream:
https://github.com/morpheus65535/bazarr/blob/v1.6.2/bazarr/app/config.py
https://github.com/morpheus65535/bazarr/blob/v1.6.2/bazarr/utilities/helper.py
"""
import hashlib
import json


def prepare(data, values, create_owned, uid, gid):
    """Seed data/bazarr/config/config.yaml; caller prepares owned directories."""
    directory = data / 'bazarr' / 'config'
    destination = directory / 'config.yaml'
    legacy = directory / 'config.ini'
    for path in (directory.parent, directory, destination, legacy):
        if path.is_symlink():
            raise ValueError('Symlink Bazarr configuration is unsupported')
    if destination.exists() or legacy.exists():
        return
    settings = {
        'auth': {
            'apikey': values['BAZARR_API_KEY'],
            'type': 'form',
            'username': 'admin',
            # This is Bazarr's supported storage format, including in 1.6.2.
            'password': hashlib.md5(values['BAZARR_PASSWORD'].encode('utf-8')).hexdigest(),
        },
        'general': {
            'use_sonarr': True,
            'use_radarr': True,
            'path_mappings': [],
            'path_mappings_movie': [],
            'enabled_providers': [],
        },
    }
    for service, port in (('sonarr', 8989), ('radarr', 7878)):
        settings[service] = {
            'ip': service, 'port': port, 'ssl': False, 'base_url': '/',
            'apikey': values[service.upper() + '_API_KEY'],
        }
    # JSON is valid YAML, preserving strings such as "true", quotes and newlines
    # without introducing a runtime YAML dependency or YAML interpolation.
    create_owned(destination, json.dumps(settings, indent=2) + '\n', uid, gid, 0o600)
