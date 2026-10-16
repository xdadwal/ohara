"""Strict, non-executable configuration shared by Ohara's commands."""
import os
from pathlib import Path
import re

KEYS = {'DOMAIN', 'LAN_IP', 'TZ', 'DATA_ROOT', 'FILES_ROOT', 'RUN_UID',
        'RUN_GID', 'ACME_EMAIL', 'REQUESTS_HOST', 'FILES_HOST', 'SPEED_HOST', 'MEDIA_ROOT', 'JELLYFIN_HOST'}
HOST = re.compile(r'(?=.{1,253}\Z)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}\Z')
PATH = re.compile(r'/[a-zA-Z0-9_./-]+\Z')
IMAGES = {'SEERR_IMAGE', 'SPEED_IMAGE', 'HOMEPAGE_IMAGE', 'JELLYFIN_IMAGE', 'RADARR_IMAGE', 'SONARR_IMAGE', 'PROWLARR_IMAGE', 'QBITTORRENT_IMAGE'}


def parse(path, keys, optional=frozenset()):
    values = {}
    for number, raw in enumerate(Path(path).read_text().splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith('#'):
            continue
        key, sep, value = raw.partition('=')
        if not sep or key not in keys or key in values:
            raise ValueError(f'{Path(path).name}:{number}: unknown, duplicate, or malformed key')
        if not value or any(c.isspace() or ord(c) < 32 for c in value):
            raise ValueError(f'{key}: use a nonempty literal value without whitespace')
        values[key] = value
    if keys - set(values) - optional:
        raise ValueError('Missing keys: ' + ', '.join(sorted(keys - set(values) - optional)))
    return values


def load(path):
    values = parse(path, KEYS, {'MEDIA_ROOT', 'JELLYFIN_HOST', 'LAN_IP', 'FILES_ROOT', 'FILES_HOST'})
    values.pop('FILES_ROOT', None)
    values.pop('FILES_HOST', None)
    values.pop('LAN_IP', None)  # Retired DNS-only input; never used.
    values.setdefault('MEDIA_ROOT', values['DATA_ROOT'] + '/media')
    values.setdefault('JELLYFIN_HOST', 'jellyfin.' + values['DOMAIN'])
    for key in ['DOMAIN', 'REQUESTS_HOST', 'SPEED_HOST', 'JELLYFIN_HOST']:
        if not HOST.fullmatch(values[key]):
            raise ValueError(f'{key}: invalid DNS hostname')
    names = [values[k] for k in ['DOMAIN', 'REQUESTS_HOST', 'SPEED_HOST', 'JELLYFIN_HOST']]
    if len(set(names)) != 4 or any(not n.endswith('.' + values['DOMAIN']) for n in names[1:]):
        raise ValueError('Service hostnames must be distinct subdomains of DOMAIN')
    for key in ['DATA_ROOT', 'MEDIA_ROOT']:
        value = values[key]
        if not PATH.fullmatch(value) or value == '/' or '..' in value.split('/') or '//' in value:
            raise ValueError(f'{key}: require a safe absolute path without spaces or traversal')
        if Path(value).is_symlink():
            raise ValueError(f'{key}: symlink roots are not supported')
    for key in ['RUN_UID', 'RUN_GID']:
        if not values[key].isdigit() or not 1 <= int(values[key]) <= 2147483647:
            raise ValueError(f'{key}: require a non-root numeric ID')
    if not re.fullmatch(r'[a-zA-Z0-9_+-]+(?:/[a-zA-Z0-9_+-]+)*', values['TZ']):
        raise ValueError('TZ: invalid timezone')
    if not (Path('/usr/share/zoneinfo') / values['TZ']).is_file():
        raise ValueError('TZ: timezone is unavailable on this host')
    if not re.fullmatch(r'[a-zA-Z0-9._+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,63}', values['ACME_EMAIL']):
        raise ValueError('ACME_EMAIL: invalid email address')
    return values


def images(path):
    values = parse(path, IMAGES)
    for key, value in values.items():
        if not re.fullmatch(r'[a-z0-9./:_-]+@sha256:[a-f0-9]{64}', value):
            raise ValueError(f'{key}: require an immutable image digest')
    return values


def create_file(path, content, mode=0o600):
    """Never overwrite operator edits or follow an existing symlink."""
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    except FileExistsError:
        return False
    with os.fdopen(descriptor, 'w') as stream:
        stream.write(content)
    return True


def directory_writable(path, uid, gid):
    """Check mode permissions for the container's single UID/GID, not host root."""
    state = Path(path).stat()
    shift = 6 if state.st_uid == uid else 3 if state.st_gid == gid else 0
    return ((state.st_mode >> shift) & 7) == 7
