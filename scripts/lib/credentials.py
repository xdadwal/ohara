"""Read user-managed literal credential files. Never create or rotate secrets."""
import os
from pathlib import Path
import re
import stat

BASE_KEYS = {'COPYPARTY_PASSWORD', 'PIHOLE_PASSWORD'}
HOMEPAGE_KEYS = {'HOMEPAGE_AUTH_ENABLED', 'HOMEPAGE_AUTH_SECRET', 'HOMEPAGE_AUTH_PASSWORD'}
MEDIA_KEYS = {'JELLYFIN_PASSWORD', 'QBITTORRENT_PASSWORD'} | {
    name + suffix for name in ('RADARR', 'SONARR', 'PROWLARR') for suffix in ('_API_KEY', '_PASSWORD')}


def read(path, keys):
    path = Path(path)
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
        raise ValueError(f'{path.name}: Symlink private configuration is unsupported')
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        raise ValueError(f'Missing/unreadable private config: user-created local/{path.name}; follow docs/credentials.md') from None
    with os.fdopen(descriptor) as stream:
        state = os.fstat(stream.fileno())
        if not stat.S_ISREG(state.st_mode) or state.st_mode & 0o077:
            raise ValueError(f'local/{path.name}: require a regular private file (chmod 0600)')
        values = {}
        for number, line in enumerate(stream.read().splitlines(), 1):
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            key, separator, value = line.partition('=')
            if not separator or key not in keys or key in values:
                raise ValueError(f'local/{path.name}:{number}: unknown, duplicate or malformed key')
            if any(ord(character) < 32 or ord(character) == 127 for character in value):
                raise ValueError(f'{key}: control characters are unsupported')
            if key == 'HOMEPAGE_AUTH_ENABLED':
                if value != 'true':
                    raise ValueError('HOMEPAGE_AUTH_ENABLED must be true')
            elif key.endswith('_API_KEY'):
                if not re.fullmatch(r'[a-fA-F0-9]{32}', value):
                    raise ValueError(f'{key}: supply a 32-character hexadecimal API key')
            elif len(value) < (32 if key.endswith('_SECRET') else 16):
                raise ValueError(f'{key}: supply at least {32 if key.endswith("_SECRET") else 16} characters')
            values[key] = value
        if set(values) != keys:
            raise ValueError(f'local/{path.name}: missing required keys: '+', '.join(sorted(keys-set(values))))
    return values


def load(root):
    """Validate all input before provisioning/storage changes; leave sources untouched."""
    return (read(root/'local/credentials', BASE_KEYS),
            read(root/'local/homepage.env', HOMEPAGE_KEYS),
            read(root/'local/media-credentials', MEDIA_KEYS))
