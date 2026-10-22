#!/usr/bin/env python3
"""Exercise pinned applications and rendered Nginx using only disposable data."""
import http.client
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import time
import uuid
import urllib.parse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/lib'))
import config
import host
import credential_fixtures
import credentials as credential_files
import media
import proxy
import runtime

NGINX = 'nginx@sha256:ed84151ed2d47ef93c0939eb9b9754c6990db6092cd2081e11988a47a83d47ea'


def request(port, hostname, path='/', method='GET', body=None, headers=None, tls=False):
    if tls:
        connection = http.client.HTTPSConnection('127.0.0.1', port, timeout=20,
                                                 context=ssl._create_unverified_context())
    else:
        connection = http.client.HTTPConnection('127.0.0.1', port, timeout=20)
    try:
        connection.request(method, path, body=body, headers=dict({'Host': hostname}, **(headers or {})))
        response = connection.getresponse()
        return response.status, response.read()
    finally:
        connection.close()


def main():
    docker = runtime.docker_prefix()
    identifier = 'ohara-smoke-' + uuid.uuid4().hex[:10]
    # Keep scratch under checkout for Docker Desktop's file sharing as well as Linux.
    (ROOT / 'local').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='smoke-', dir=ROOT / 'local') as directory:
        root = Path(directory).resolve()
        shutil.copytree(ROOT / 'configs', root / 'configs')
        shutil.copy(ROOT / 'compose.yaml', root / 'compose.yaml')
        shutil.copy(ROOT / 'versions.env', root / 'versions.env')
        c = config.load(ROOT / '.env.example')
        c['HOMEPAGE_HOST'] = 'ohara.' + c['DOMAIN']
        c.update(DATA_ROOT=str(root / 'data'), MEDIA_ROOT=str(root / 'media'),
                 RUN_UID=str(os.getuid() or 1000), RUN_GID=str(os.getgid() or 1000))
        credential_fixtures.write(root)
        host.prepare_storage(c, root)
        # Real container runs as 1000 in both production and disposable Linux CI.
        if os.geteuid() == 0:
            os.chown(root / 'data/seerr', 1000, 1000)
        for path in [root / 'data', root / 'data/seerr', root / 'data/homepage']:
            path.chmod(0o777)  # disposable fixture only, never a production setup behavior
        runtime.check(c, root)
        override = root / 'smoke.yaml'
        override.write_text('services:\n' + '\n'.join(
            f'  {name}:\n    ports: !override\n      - "127.0.0.1::{port}"'
            for name, port in [('homepage',3000),('seerr',5055),('speedtest',3000),('jellyfin',8096),('radarr',7878),('sonarr',8989),('prowlarr',9696),('qbittorrent',8081),('lidarr',8686),('bazarr',6767),('navidrome',4533)]
        ) + '\n')
        def compose(args, capture=False, timeout=120):
            return runtime.compose(c, root, ['-p', identifier, '-f', str(override)] + args,
                                   capture=capture, timeout=timeout, docker=docker)
        def port(service, internal):
            args = ['port', service, str(internal)]
            return int(compose(args, True).strip().rsplit(':', 1)[1])
        nginx_name = identifier + '-proxy'
        try:
            print('Starting isolated application stack...', flush=True)
            try:
                compose(['up', '-d', '--wait', '--wait-timeout', '180'], timeout=900)
            except RuntimeError:
                diagnostic = compose(['logs', '--no-color', '--tail', '25', 'homepage'], capture=True)
                homepage_values, media_values = credential_files.load(root)
                for value in [*homepage_values.values(),
                              *credential_files.navidrome_widget_environment(media_values).values()]:
                    if len(value) > 10:
                        diagnostic = diagnostic.replace(value, '<redacted>')
                print(diagnostic, flush=True)
                raise
            ports = {name: port(name, number) for name, number in [('homepage',3000),('seerr',5055),('speedtest',3000),('jellyfin',8096),('radarr',7878),('sonarr',8989),('prowlarr',9696),('qbittorrent',8081),('lidarr',8686),('bazarr',6767),('navidrome',4533)]}
            for name, value in ports.items():
                deadline = time.monotonic() + 90
                while True:
                    try:
                        code, _ = request(value, 'localhost', '/api/v1/settings/public' if name == 'seerr' else '/api/healthcheck' if name == 'homepage' else '/')
                        if code < 500:
                            break
                    except (OSError, http.client.HTTPException):
                        pass
                    if time.monotonic() > deadline:
                        raise AssertionError(f'{name}: HTTP did not become ready')
                    time.sleep(1)
            print('Connecting media accounts and APIs...', flush=True)
            urls = {name: f'http://127.0.0.1:{value}' for name, value in ports.items()}
            media.connect(c, root, 'smoke@example.com', urls)
            media.connect(c, root, 'smoke@example.com', urls)
            media_secrets = credential_files.load(root)[1]
            qb = media.Client(urls['qbittorrent'])
            qb.headers.update(Host='127.0.0.1:8081', Referer='http://127.0.0.1:8081/')
            qb.call('/api/v2/auth/login', {'username':'admin',
                    'password':media_secrets['QBITTORRENT_PASSWORD']}, form=True)
            preferences = qb.call('/api/v2/app/preferences')
            assert preferences['max_seeding_time_enabled'] and preferences['max_seeding_time'] == 4320
            assert preferences['max_ratio_act'] == 3, 'qBittorrent must delete download files after seeding'
            assert not preferences['max_ratio_enabled'] and not preferences['max_inactive_seeding_time_enabled']
            seerr_api = media.Client(urls['seerr'])
            seerr_api.call('/api/v1/auth/jellyfin', {'username':'admin', 'password':media_secrets['JELLYFIN_PASSWORD']})
            assert seerr_api.call('/api/v1/settings/public')['initialized'], 'Seerr wizard was not completed'
            assert sum(library['enabled'] for library in seerr_api.call('/api/v1/settings/jellyfin/library')) == 2
            # Application-issued tokens in disposable files, never deployment defaults.
            jf = media.Client(urls['jellyfin'])
            jf.headers['Authorization'] = 'MediaBrowser Client="Ohara", Device="Test", DeviceId="widget-smoke", Version="1"'
            account = jf.call('/Users/AuthenticateByName', {'Username':'admin', 'Pw':media_secrets['JELLYFIN_PASSWORD']})
            widget_keys = {
                'HOMEPAGE_VAR_JELLYFIN_API_KEY': account['AccessToken'],
                'HOMEPAGE_VAR_SEERR_API_KEY': seerr_api.call('/api/v1/settings/main')['apiKey'],
            }
            with (root/'.env').open('a') as stream:
                for key, value in widget_keys.items():
                    stream.write(key+'='+value+'\n')
            credential_files.load(root)
            private_widget_values = list(widget_keys.values()) + list(
                credential_files.navidrome_widget_environment(media_secrets).values())
            compose(['up', '-d', '--force-recreate', 'homepage'])
            for name, category in [('radarr','movies'), ('sonarr','tv'), ('lidarr','music')]:
                if name != 'lidarr':
                    settings = seerr_api.call('/api/v1/settings/'+name)
                    assert len(settings) == 1 and settings[0]['isDefault'], 'Seerr duplicate/missing default server'
                    assert settings[0]['activeDirectory'] == '/data/library/'+category
                client = media.Client(urls[name], media_secrets[name.upper()+'_API_KEY'])
                version = '/api/v1' if name == 'lidarr' else '/api/v3'
                clients = client.call(version+'/downloadclient')
                assert len(clients) == 1 and clients[0]['enable'], 'Download client was duplicated or disabled'
                assert request(ports[name], 'localhost', version+'/system/status')[0] in (401,403)
            prowlarr = media.Client(urls['prowlarr'], media_secrets['PROWLARR_API_KEY'])
            assert len(prowlarr.call('/api/v1/applications')) == 3, 'Prowlarr application sync duplicated'
            bazarr_api = media.Client(urls['bazarr'], media_secrets['BAZARR_API_KEY'])
            deadline = time.monotonic() + 120
            while True:
                status = bazarr_api.call('/api/system/status')['data']
                if all(any(ch.isdigit() for ch in str(status.get(name+'_version', '')))
                       for name in ('sonarr', 'radarr')):
                    break
                assert time.monotonic() < deadline, 'Bazarr cannot reach Sonarr/Radarr with supplied keys'
                time.sleep(2)
            assert request(ports['bazarr'], 'localhost', '/api/system/status')[0] in (401,403), 'Bazarr API must require a key'
            # Render real templates; only upstream addresses differ in this container fixture.
            certificates = root / 'certs'
            certificates.mkdir()
            runtime.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
                         '-subj', '/CN=xdadwal.in', '-keyout', str(certificates/'privkey.pem'),
                         '-out', str(certificates/'fullchain.pem')], timeout=60)
            nginx_config = root / 'nginx.conf'
            text = proxy.render(c, ROOT, https=True)
            text = text.replace('127.0.0.1:3002', 'homepage:3000')
            for name, number in [('seerr',5055),('speedtest',3000),('jellyfin',8096),('radarr',7878),('sonarr',8989),('prowlarr',9696),('qbittorrent',8081),('lidarr',8686),('bazarr',6767),('navidrome',4533)]:
                text = text.replace(f'127.0.0.1:{number}', f'{name}:{number}')
            nginx_config.write_text('events {}\nhttp {\n' + text + '\n}\n')
            runtime.run(docker + ['run', '-d', '--name', nginx_name, '--network', identifier + '_default',
                                 '-p', '127.0.0.1::80', '-p', '127.0.0.1::443',
                                 '-v', f'{nginx_config}:/etc/nginx/nginx.conf:ro',
                                 '-v', f'{certificates}:/etc/letsencrypt/live/ohara:ro', NGINX], timeout=300)
            tls_port = int(runtime.run(docker + ['port', nginx_name, '443'], capture=True).strip().rsplit(':',1)[1])
            http_port = int(runtime.run(docker + ['port', nginx_name, '80'], capture=True).strip().rsplit(':',1)[1])
            # SNI must match a known name; patch socket target while preserving hostname/SNI.
            def tls_request(name, path='/', method='GET', body=None, hdr=None, full=False):
                context = ssl._create_unverified_context()
                raw = socket.create_connection(('127.0.0.1', tls_port), timeout=20)
                wrapped = context.wrap_socket(raw, server_hostname=name)
                conn = http.client.HTTPConnection(name, timeout=20)
                conn.sock = wrapped
                try:
                    conn.request(method, path, body, hdr or {})
                    response = conn.getresponse()
                    result = (response.status, response.read())
                    return result + (response.getheaders(),) if full else result
                finally:
                    conn.close()
            deadline = time.monotonic()+30
            while True:
                try:
                    runtime.run(docker+['exec',nginx_name,'nginx','-t'])
                    status = tls_request(c['HOMEPAGE_HOST'])[0]
                    if status not in (302, 307):
                        raise RuntimeError(f'Homepage not ready through proxy (HTTP {status})')
                    break
                except (OSError, RuntimeError, http.client.HTTPException):
                    if time.monotonic()>deadline:
                        raise
                    time.sleep(1)
            code, body, denied_headers = tls_request(c['HOMEPAGE_HOST'], '/api/services', full=True)
            redirect = dict((k.lower(),v) for k,v in denied_headers).get('location','')
            assert code in (401,403) or (code in (302,307) and '/auth/signin' in redirect), f'Homepage anonymous API returned {code}'
            code, body, csrf_headers = tls_request(c['HOMEPAGE_HOST'], '/api/auth/csrf', full=True)
            assert code == 200, 'Homepage CSRF endpoint failed'
            csrf = json.loads(body)['csrfToken']
            cookie = '; '.join(value.split(';', 1)[0] for key,value in csrf_headers if key.lower() == 'set-cookie')
            hp = credential_files.load(root)[0]
            payload = urllib.parse.urlencode({'csrfToken':csrf, 'password':hp['HOMEPAGE_AUTH_PASSWORD'],
                                               'callbackUrl':'https://'+c['HOMEPAGE_HOST'], 'json':'true'})
            code, body, login_headers = tls_request(c['HOMEPAGE_HOST'], '/api/auth/callback/credentials', 'POST', payload,
                                                   {'Content-Type':'application/x-www-form-urlencoded','Cookie':cookie}, full=True)
            assert code == 200 and 'error' not in json.loads(body).get('url',''), 'Homepage password login failed'
            session = '; '.join(value.split(';', 1)[0] for key,value in login_headers if key.lower() == 'set-cookie')
            assert session, 'Homepage session cookie missing'
            code, body = tls_request(c['HOMEPAGE_HOST'], '/api/services', hdr={'Cookie':session})
            assert code == 200 and b'Seerr' in body and b'Jellyfin' in body, 'Homepage authenticated service list failed'
            assert not any(value.encode() in body for value in private_widget_values), 'Service list exposed widget credentials'
            speed_service = next(service for group in json.loads(body) for service in group['services']
                                 if service['name'] == 'OpenSpeedTest')
            assert not speed_service.get('widgets'), 'Speed test should be a link-only card'
            assert speed_service['href'] == 'https://'+c['SPEED_HOST'], 'Speed test link must use its public HTTPS hostname'
            for service, endpoint, field in [('Jellyfin','CountV2','MovieCount'),
                                              ('Seerr','request/count','pending'),
                                              ('Seerr','issue/count','open'),
                                              ('Navidrome','getNowPlaying','subsonic-response')]:
                query = urllib.parse.urlencode({'group':'Media', 'service':service, 'index':0, 'endpoint':endpoint})
                code, result = tls_request(c['HOMEPAGE_HOST'], '/api/services/proxy?'+query, hdr={'Cookie':session})
                assert code == 200 and field in json.loads(result), f'{service}: native widget API failed'
                assert not any(value.encode() in result for value in private_widget_values), 'Widget API exposed credentials'
                if service == 'Navidrome':
                    assert json.loads(result)['subsonic-response']['status'] == 'ok', 'Navidrome widget authentication failed'
            for resource in ['cpu', 'memory', 'uptime']:
                query = urllib.parse.urlencode({'type':resource})
                code, result = tls_request(c['HOMEPAGE_HOST'], '/api/widgets/resources?'+query, hdr={'Cookie':session})
                assert code == 200 and isinstance(json.loads(result), dict), f'{resource}: resource API failed'
            for target in ['/app/config']:
                query = urllib.parse.urlencode({'type':'disk', 'target':target})
                code, result = tls_request(c['HOMEPAGE_HOST'], '/api/widgets/resources?'+query, hdr={'Cookie':session})
                assert code == 200 and json.loads(result)['drive']['size'] > 0, 'Storage capacity unavailable'
            rejected = urllib.parse.urlencode({'csrfToken':csrf, 'password':'not-the-password',
                                                'callbackUrl':'https://'+c['HOMEPAGE_HOST'], 'json':'true'})
            attempts = [tls_request(c['HOMEPAGE_HOST'], '/api/auth/callback/credentials', 'POST', rejected,
                                    {'Content-Type':'application/x-www-form-urlencoded','Cookie':cookie})[0]
                        for _ in range(8)]
            assert 429 in attempts, 'Homepage proxy login rate limit was not enforced'
            assert request(http_port, c['REQUESTS_HOST'])[0] == 301
            assert tls_request(c['JELLYFIN_HOST'], '/System/Info/Public')[0] == 200
            assert tls_request(c['NAVIDROME_HOST'], '/ping')[0] == 200, 'Navidrome HTTPS route failed'
            assert tls_request(c['NAVIDROME_HOST'], '/api/user')[0] == 401, 'Navidrome API must require login'
            salt = 'disposable-smoke'
            query = urllib.parse.urlencode({
                'u':'admin', 't':hashlib.md5((media_secrets['NAVIDROME_PASSWORD']+salt).encode()).hexdigest(),
                's':salt, 'v':'1.16.1', 'c':'OharaSmoke', 'f':'json'})
            code, response = tls_request(c['NAVIDROME_HOST'], '/rest/getMusicFolders.view?'+query)
            subsonic = json.loads(response)['subsonic-response']
            assert code == 200 and subsonic['status'] == 'ok', 'Navidrome music-client authentication failed'
            assert subsonic['musicFolders']['musicFolder'], 'Navidrome music folder missing'
            assert tls_request(c['REQUESTS_HOST'], '/api/v1/settings/public')[0] == 200
            speed_code, speed_body, speed_headers = tls_request(c['SPEED_HOST'], full=True)
            assert speed_code == 200 and b'OpenSpeedTest' in speed_body
            frame_options = dict((k.lower(),v) for k,v in speed_headers).get('x-frame-options','').upper()
            assert frame_options not in ('DENY','SAMEORIGIN'), 'Speed test response blocks dashboard embedding'
            # Actual 35 MiB upload through proxy verifies the documented body-size requirement.
            result = tls_request(c['SPEED_HOST'], '/upload', 'POST', b'x' * (35*1024*1024))
            assert result[0] == 200, f'speed upload returned {result[0]}'
            # A failed music upstream must not leak replayable Subsonic URL tokens.
            compose(['stop', 'navidrome'])
            failed_path = '/rest/getMusicFolders.view?'+query
            assert tls_request(c['NAVIDROME_HOST'], failed_path)[0] in (502, 504)
            assert request(http_port, c['NAVIDROME_HOST'], failed_path)[0] == 301
            diagnostic = subprocess.run(docker+['logs', nginx_name], stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT, text=True, timeout=30, check=True).stdout
            assert failed_path not in diagnostic, 'Nginx logged music-client URL credentials'
            print('PASS: eleven apps, media API connections and rerun preservation, Homepage password login/session, media/resource widgets and OpenSpeedTest link, private services and login rate limit, Nginx TLS/routes, and 35 MiB speed upload.', flush=True)
        finally:
            runtime.run(docker + ['rm', '-f', nginx_name], timeout=30) if subprocess.run(docker + ['inspect', nginx_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0 else None
            compose(['down', '--remove-orphans'], timeout=90)
            # Linux preserves container UIDs on bind-mounted dummy files. Restore
            # only this generated fixture's data ownership before tempfile cleanup.
            cleanup_image = config.images(root / 'versions.env')['QBITTORRENT_IMAGE']
            runtime.run(docker + ['run', '--rm', '--user', '0:0', '--entrypoint', '/bin/sh',
                                 '-v', f'{root / "data"}:/fixture', cleanup_image,
                                 '-c', 'chown -R "$1:$2" /fixture', 'fixture-cleanup',
                                 str(os.getuid()), str(os.getgid())], timeout=60)

if __name__ == '__main__':
    main()
