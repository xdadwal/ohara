"""Read user-managed literal credential files. Never create or rotate secrets."""
import os
from pathlib import Path
import re
import stat

HOMEPAGE_KEYS = {'HOMEPAGE_AUTH_ENABLED', 'HOMEPAGE_AUTH_SECRET', 'HOMEPAGE_AUTH_PASSWORD'}
WIDGET_KEYS = {'HOMEPAGE_VAR_JELLYFIN_API_KEY', 'HOMEPAGE_VAR_SEERR_API_KEY'}
MEDIA_KEYS = {'JELLYFIN_PASSWORD', 'QBITTORRENT_PASSWORD', 'NAVIDROME_PASSWORD'} | {
    name + suffix for name in ('RADARR', 'SONARR', 'PROWLARR', 'LIDARR', 'BAZARR') for suffix in ('_API_KEY', '_PASSWORD')}
ALL_KEYS = HOMEPAGE_KEYS | MEDIA_KEYS | WIDGET_KEYS
DERIVED_WIDGET_KEYS = {'HOMEPAGE_VAR_NAVIDROME_TOKEN'}


def navidrome_widget_environment(media):
    """Subsonic token auth; derive locally, never forward the account password."""
    import hashlib
    # Must match the non-secret salt in configs/homepage/services.yaml.
    token = hashlib.md5((media['NAVIDROME_PASSWORD']+'ohara-homepage').encode()).hexdigest()
    return {'HOMEPAGE_VAR_NAVIDROME_TOKEN': token}


def read(path, keys, optional=frozenset(), ignored=frozenset()):
    path = Path(path)
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
        raise ValueError(f'{path.name}: Symlink private configuration is unsupported')
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        raise ValueError(f'Missing/unreadable user-created private config: {path.name}; follow docs/credentials.md') from None
    with os.fdopen(descriptor) as stream:
        state = os.fstat(stream.fileno())
        if not stat.S_ISREG(state.st_mode) or state.st_mode & 0o077:
            raise ValueError(f'{path.name}: require a regular private file (chmod 0600)')
        values = {}
        seen = set()
        for number, line in enumerate(stream.read().splitlines(), 1):
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            key, separator, value = line.partition('=')
            if not separator or key not in keys | optional | ignored or key in seen:
                raise ValueError(f'{path.name}:{number}: unknown, duplicate or malformed key')
            seen.add(key)
            if key in ignored:
                continue
            if any(ord(character) < 32 or ord(character) == 127 for character in value):
                raise ValueError(f'{key}: control characters are unsupported')
            if key in WIDGET_KEYS:
                if not re.fullmatch(r'[!-~]{20,512}', value):
                    raise ValueError(f'{key}: copy the actual application API key into the private file')
            elif key == 'HOMEPAGE_AUTH_ENABLED':
                if value != 'true':
                    raise ValueError('HOMEPAGE_AUTH_ENABLED must be true')
            elif key.endswith('_API_KEY'):
                if not re.fullmatch(r'[a-fA-F0-9]{32}', value):
                    raise ValueError(f'{key}: supply a 32-character hexadecimal API key')
            else:
                minimum = (32 if key.endswith('_SECRET') else
                           8 if key == 'HOMEPAGE_AUTH_PASSWORD' else 16)
                if len(value) < minimum:
                    raise ValueError(f'{key}: supply at least {minimum} characters')
            values[key] = value
        if not keys <= set(values):
            raise ValueError(f'{path.name}: missing required keys: '+', '.join(sorted(keys-set(values))))
    return values


def load(root):
    """Validate all input before provisioning/storage changes; leave sources untouched."""
    import config
    values = read(root/'.env', HOMEPAGE_KEYS | MEDIA_KEYS, WIDGET_KEYS, config.KEYS)
    return ({k:v for k,v in values.items() if k in HOMEPAGE_KEYS | WIDGET_KEYS},
            {k:v for k,v in values.items() if k in MEDIA_KEYS})
