"""Verify and rotate existing media login passwords through supported local APIs.

The owner chooses new values and writes them to private .env; nothing here
generates, prints or persists a password. Rotation needs a private copy of the
previous .env only for qBittorrent, whose API requires the current password.
Radarr/Sonarr/Prowlarr/Lidarr and Bazarr change through their API keys.
"""
from pathlib import Path
import credentials as credential_files

ARR = {'radarr': ('/api/v3', 7878), 'sonarr': ('/api/v3', 8989),
       'prowlarr': ('/api/v1', 9696), 'lidarr': ('/api/v1', 8686)}
ROTATABLE = ('radarr', 'sonarr', 'prowlarr', 'lidarr', 'bazarr', 'qbittorrent')


def default_urls():
    urls = {name: f'http://127.0.0.1:{port}' for name, (_, port) in ARR.items()}
    urls.update(bazarr='http://127.0.0.1:6767', qbittorrent='http://127.0.0.1:8081')
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
    raise ValueError(f'Unsupported service {name}')


def verify(root, urls=None, out=print):
    """Report whether each service accepts its .env login; return the failures."""
    _, values = credential_files.load(root)
    urls = urls or default_urls()
    failed = []
    for name in ROTATABLE:
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

    new = values['BAZARR_PASSWORD']
    if login_ok('bazarr', urls['bazarr'], new):
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
        old = credential_files.read(Path(previous), set(), {'QBITTORRENT_PASSWORD'},
                                    credential_files.ALL_KEYS - {'QBITTORRENT_PASSWORD'} | _config_keys(),
                                    minimum_lengths={'QBITTORRENT_PASSWORD': 1}).get('QBITTORRENT_PASSWORD')
        if not old:
            raise ValueError('--previous-env has no QBITTORRENT_PASSWORD')
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
    out('Run scripts/up so Homepage receives the new qBittorrent password.')


def _config_keys():
    import config
    return config.KEYS
