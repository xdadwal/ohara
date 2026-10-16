"""Bootstrap Navidrome privately, then prove the supplied admin credentials.

Native UI contract verified against upstream v0.64.2: server/serve_index.go,
server/auth.go, server/nativeapi/native_api.go and consts/consts.go.
https://github.com/navidrome/navidrome/tree/v0.64.2/server
"""
import json
import re
from urllib.parse import quote

from media import Client


def connect(url, password):
    """Create admin only on first run; never reset or replace an existing user."""
    if not isinstance(password, str) or not password:
        raise ValueError('Supply NAVIDROME_PASSWORD in the private credentials file')
    client = Client(url.rstrip('/'))
    page = client.call('/app/')
    marker = re.search(r'window\.__APP_CONFIG__\s*=\s*', page) if isinstance(page, str) else None
    try:
        config, _ = json.JSONDecoder().raw_decode(page[marker.end():].lstrip()) if marker else (None, None)
        # Go's HTML template emits the config as a JSON-encoded string.
        if isinstance(config, str):
            config = json.loads(config)
    except (ValueError, TypeError):
        config = None
    if not isinstance(config, dict) or type(config.get('firstTime')) is not bool:
        raise RuntimeError('Navidrome bootstrap state unavailable; inspect service locally')
    credentials = {'username': 'admin', 'password': password}
    if config['firstTime']:
        # Upstream independently rejects createAdmin when any user already exists.
        # A race or interrupted request fails closed; rerun to prove the login.
        client.call('/auth/createAdmin', credentials)
    account = client.call('/auth/login', credentials)
    if (not isinstance(account, dict) or account.get('username') != 'admin'
            or account.get('isAdmin') is not True
            or not isinstance(account.get('token'), str) or not account['token']
            or not isinstance(account.get('id'), str) or not account['id']):
        raise RuntimeError('Navidrome admin login was not verified; existing account preserved')
    client.headers['X-ND-Authorization'] = 'Bearer ' + account['token']
    user = client.call('/api/user/' + quote(account['id'], safe=''))
    if (not isinstance(user, dict) or user.get('id') != account['id']
            or user.get('userName') != 'admin' or user.get('isAdmin') is not True):
        raise RuntimeError('Navidrome protected admin access was not verified')
