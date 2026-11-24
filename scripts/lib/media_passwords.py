"""Verify and rotate existing media login passwords through supported local APIs.

The owner chooses new values and writes them to private .env; nothing here
generates, prints or persists a password. Rotation needs a private copy of the
previous .env only for qBittorrent and Navidrome, whose APIs require the current
password. Radarr/Sonarr/Prowlarr/Lidarr and Bazarr change through their API keys.
"""
from pathlib import Path
import credentials as credential_files

ARR = {'radarr': ('/api/v3', 7878), 'sonarr': ('/api/v3', 8989),
       'prowlarr': ('/api/v1', 9696), 'lidarr': ('/api/v1', 8686)}
ROTATABLE = ('radarr', 'sonarr', 'prowlarr', 'lidarr', 'bazarr', 'qbittorrent', 'navidrome')


def default_urls():
    urls = {name: f'http://127.0.0.1:{port}' for name, (_, port) in ARR.items()}
    urls.update(bazarr='http://127.0.0.1:6767', qbittorrent='http://127.0.0.1:8081',
                navidrome='http://127.0.0.1:4533')
    return urls


def _form_post(url, body, headers=None):
    """POST a form without following redirects; return (status, Location)."""
    import urllib.error
    import urllib.parse
    import urllib.request

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect)
    request = urllib.request.Request(url, urllib.parse.urlencode(body).encode(),
                                     {'Content-Type': 'application/x-www-form-urlencoded', **(headers or {})})
    try:
        with opener.open(request, timeout=30) as response:
            return response.status, response.headers.get('Location', ''), response.read(200).decode(errors='replace')
    except urllib.error.HTTPError as error:
        return error.code, error.headers.get('Location', ''), ''
    except OSError:
        raise RuntimeError(f'Media login check could not reach {url.split("?")[0]}') from None


def login_ok(name, url, password, username='admin'):
    """True when the service accepts this login. Never logs the password."""
    if name in ARR:
        status, location, _ = _form_post(url+'/login', {'username': username, 'password': password, 'rememberMe': 'false'})
        return status in (302, 303) and 'loginFailed' not in location
    if name == 'bazarr':
        status, _, _ = _form_post(url+'/api/system/account', {'action': 'login', 'username': username, 'password': password})
        return status == 204
    if name == 'qbittorrent':
        status, _, text = _form_post(url+'/api/v2/auth/login', {'username': username, 'password': password},
                                     {'Referer': url+'/', 'Host': url.split('//', 1)[1]})
        # qBittorrent 5.x answers 204; earlier releases answer 200 "Ok.".
        return status == 204 or (status == 200 and text.strip() == 'Ok.')
    if name == 'navidrome':
        return _navidrome_session(url, password, username) is not None
    raise ValueError(f'Unsupported service {name}')


def _navidrome_session(url, password, username='admin'):
    """Return the login response for a valid Navidrome login, else None."""
    import json
    import urllib.error
    import urllib.request
    request = urllib.request.Request(url+'/auth/login', json.dumps({'username': username, 'password': password}).encode(),
                                     {'Content-Type': 'application/json'})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=30) as response:
            account = json.loads(response.read())
    except urllib.error.HTTPError:
        return None
    except (OSError, ValueError):
        raise RuntimeError('Media login check could not reach '+url+'/auth/login') from None
    if isinstance(account, dict) and isinstance(account.get('token'), str) and account['token'] and account.get('id'):
        return account
    return None


def verify(root, urls=None, out=print):
    """Report whether each service accepts its .env login; return the failures."""
    _, values = credential_files.load(root)
    urls = urls or default_urls()
    failed = []
    for name in ROTATABLE:
        if name.upper()+'_PASSWORD' not in values:
            out(f'{name}: not in .env (setup-only); skipped')
            continue
        ok = login_ok(name, urls[name], values[name.upper()+'_PASSWORD'])
        out(f'{name}: {"login ok" if ok else "LOGIN REJECTED"}')
        if not ok:
            failed.append(name)
    return failed


def rotate(root, previous, urls=None, out=print):
    """Apply .env passwords to services that do not accept them yet.

    `previous` is a private copy of .env from before the edit; only its
    QBITTORRENT_PASSWORD is used. Services already accepting the new value are
    skipped, so an interrupted run can be repeated.
    """
    import json
    from media import Client
    _, values = credential_files.load(root)
    urls = urls or default_urls()
    for name, (version, _) in ARR.items():
        if name.upper()+'_PASSWORD' not in values:
            out(f'{name}: not in .env (setup-only); unchanged')
            continue
        new = values[name.upper()+'_PASSWORD']
        if login_ok(name, urls[name], new):
            out(f'{name}: already uses the .env password')
            continue
        client = Client(urls[name], values[name.upper()+'_API_KEY'])
        resource = client.call(version+'/config/host')
        resource.update(password=new, passwordConfirmation=new)
        client.call(version+'/config/host', resource, 'PUT')
        if not login_ok(name, urls[name], new, resource.get('username') or 'admin'):
            raise RuntimeError(f'{name}: password update was not accepted; check its UI')
        out(f'{name}: password changed and login verified')

    new = values.get('BAZARR_PASSWORD')
    if new is None:
        out('bazarr: not in .env (setup-only); unchanged')
    elif login_ok('bazarr', urls['bazarr'], new):
        out('bazarr: already uses the .env password')
    else:
        bazarr = Client(urls['bazarr'])
        bazarr.headers['X-API-KEY'] = values['BAZARR_API_KEY']
        bazarr.call('/api/system/settings', {'settings-auth-password': new}, form=True)
        if not login_ok('bazarr', urls['bazarr'], new):
            raise RuntimeError('bazarr: password update was not accepted; check its UI')
        out('bazarr: password changed and login verified')

    new = values['QBITTORRENT_PASSWORD']
    qb_url = urls['qbittorrent']
    if login_ok('qbittorrent', qb_url, new):
        out('qbittorrent: already uses the .env password')
    else:
        if previous is None:
            raise ValueError('qBittorrent needs --previous-env: a private copy of .env from before the edit')
        old = _previous(previous, 'QBITTORRENT_PASSWORD')
        if not login_ok('qbittorrent', qb_url, old):
            raise RuntimeError('qbittorrent: the previous password was rejected; nothing changed')
        qb = Client(qb_url)
        qb.headers.update(Host=qb_url.split('//', 1)[1], Referer=qb_url+'/')
        qb.call('/api/v2/auth/login', {'username': 'admin', 'password': old}, form=True)
        qb.call('/api/v2/app/setPreferences', {'json': json.dumps({'web_ui_password': new})}, form=True)
        if not login_ok('qbittorrent', qb_url, new):
            raise RuntimeError('qbittorrent: password update was not accepted; check its Web UI options')
        out('qbittorrent: password changed and login verified')

    # Arr download clients store their own copy of the qBittorrent login.
    for name, (version, _) in ARR.items():
        client = Client(urls[name], values[name.upper()+'_API_KEY'])
        for download in client.call(version+'/downloadclient'):
            if download.get('implementation') != 'QBittorrent':
                continue
            for field in download.get('fields', []):
                if field.get('name') == 'password':
                    field['value'] = new
            client.call(version+'/downloadclient/test', download)
            client.call(version+'/downloadclient/'+str(download['id']), download, 'PUT')
            out(f'{name}: download client "{download.get("name")}" updated and tested')

    new = values['NAVIDROME_PASSWORD']
    nd_url = urls['navidrome']
    if login_ok('navidrome', nd_url, new):
        out('navidrome: already uses the .env password')
    else:
        if previous is None:
            raise ValueError('Navidrome needs --previous-env: a private copy of .env from before the edit')
        old = _previous(previous, 'NAVIDROME_PASSWORD')
        account = _navidrome_session(nd_url, old)
        if account is None:
            raise RuntimeError('navidrome: the previous password was rejected; nothing changed')
        from urllib.parse import quote
        nd = Client(nd_url)
        nd.headers['X-ND-Authorization'] = 'Bearer '+account['token']
        path = '/api/user/'+quote(account['id'], safe='')
        user = nd.call(path)
        if not isinstance(user, dict) or user.get('id') != account['id']:
            raise RuntimeError('navidrome: could not read the admin account; nothing changed')
        # Upstream requires the current password when a user changes their own.
        user.update(password=new, currentPassword=old)
        nd.call(path, user, 'PUT')
        if not login_ok('navidrome', nd_url, new):
            raise RuntimeError('navidrome: password update was not accepted; check its UI')
        out('navidrome: password changed and login verified; update music apps that log in to it')
    out('Run scripts/up so Homepage receives the new qBittorrent password and Navidrome token.')


def _previous(previous, key):
    """Read one old value from the private pre-edit copy of .env."""
    value = credential_files.read(Path(previous), set(), {key},
                                  (credential_files.ALL_KEYS - {key}) | _config_keys(),
                                  minimum_lengths={key: 1}).get(key)
    if not value:
        raise ValueError(f'--previous-env has no {key}')
    return value


def _config_keys():
    import config
    return config.KEYS
