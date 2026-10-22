"""Private Google OAuth configuration; never permits automatic user registration."""
import json
import os
from pathlib import Path
import re
import stat
import tempfile

import config
import credentials


def validate_policy(policy):
    if policy.get('machineLearning', {}).get('enabled') is not False:
        raise ValueError('Immich machine learning must remain disabled')
    oauth = policy.get('oauth', {})
    if oauth.get('autoRegister') is not False or oauth.get('autoLaunch') is not False:
        raise ValueError('Immich OAuth must disable auto registration and automatic redirects')
    password_login = policy.get('passwordLogin', {}).get('enabled')
    if not isinstance(password_login, bool) or (not password_login and not oauth.get('enabled')):
        raise ValueError('Immich requires at least one enabled login method')
    if oauth.get('enabled'):
        if (oauth.get('issuerUrl') != 'https://accounts.google.com' or
                oauth.get('scope') != 'openid email profile' or
                oauth.get('mobileOverrideEnabled') is not True or
                not oauth.get('clientId') or not oauth.get('clientSecret')):
            raise ValueError('Invalid invite-only Google OAuth configuration')


def configuration_path(root, *, static=False):
    private = root / 'local/immich/immich.json'
    if static or not (private.exists() or private.is_symlink()):
        return root / 'configs/immich/immich.json'
    if any(p.is_symlink() for p in (private, *private.parents)):
        raise ValueError('Symlink private Immich configuration is unsupported')
    state = private.stat()
    if not stat.S_ISREG(state.st_mode) or state.st_mode & 0o077:
        raise ValueError('Private Immich configuration must be a regular file with mode 0600')
    validate_policy(json.loads(private.read_text()))
    return private


def render(root, c):
    inputs = credentials.read(root / '.env', credentials.IMMICH_OAUTH_KEYS,
        ignored=config.KEYS | (credentials.ALL_KEYS - credentials.IMMICH_OAUTH_KEYS))
    client_id = inputs['IMMICH_GOOGLE_CLIENT_ID']
    if not re.fullmatch(r'[A-Za-z0-9_-]+\.apps\.googleusercontent\.com', client_id):
        raise ValueError('IMMICH_GOOGLE_CLIENT_ID: supply the actual Google Web application client ID')
    policy = json.loads((root / 'configs/immich/immich.json').read_text())
    validate_policy(policy)
    policy['oauth'] = {
        'enabled': True, 'autoRegister': False, 'autoLaunch': False,
        'buttonText': 'Sign in with Google', 'issuerUrl': 'https://accounts.google.com',
        'clientId': client_id, 'clientSecret': inputs['IMMICH_GOOGLE_CLIENT_SECRET'],
        'scope': 'openid email profile', 'signingAlgorithm': 'RS256',
        'profileSigningAlgorithm': 'none', 'tokenEndpointAuthMethod': 'client_secret_post',
        'mobileOverrideEnabled': True,
        'mobileRedirectUri': 'https://immich.' + c['DOMAIN'] + '/api/oauth/mobile-redirect',
    }
    policy['passwordLogin'] = {'enabled': False}
    validate_policy(policy)
    return json.dumps(policy, indent=2) + '\n'


def prepare(root, c):
    content = render(root, c)  # Validate all inputs before creating/writing any file.
    directory = root / 'local/immich'
    if any(p.is_symlink() for p in (directory, *directory.parents)):
        raise ValueError('Symlink private Immich configuration is unsupported')
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if directory.stat().st_mode & 0o077:
        raise ValueError('Private Immich configuration directory requires mode 0700')
    target = directory / 'immich.json'
    if target.exists() or target.is_symlink():
        configuration_path(root)
        if target.read_text() == content:
            return
        # Keep the prior generated config private for deliberate rollback.
        descriptor, _ = tempfile.mkstemp(prefix='immich-previous-', suffix='.json', dir=directory)
        with os.fdopen(descriptor, 'w') as stream:
            stream.write(target.read_text())
    descriptor, temporary = tempfile.mkstemp(prefix='.immich-', dir=directory)
    try:
        with os.fdopen(descriptor, 'w') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def restore(root, previous):
    """Restore the prior managed file after failed activation; retain failed input privately."""
    target = root / 'local/immich/immich.json'
    if previous is None:
        if target.exists():
            descriptor, failed = tempfile.mkstemp(prefix='immich-failed-', suffix='.json', dir=target.parent)
            os.close(descriptor)
            os.replace(target, failed)
        return
    descriptor, temporary = tempfile.mkstemp(prefix='.immich-restore-', dir=target.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(previous)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
