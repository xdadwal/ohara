#!/usr/bin/env python3
"""Exercise pinned applications and rendered Nginx using only disposable data."""
import http.client
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
            for name, port in [('homepage',3000),('seerr',5055),('speedtest',3000),('jellyfin',8096),('radarr',7878),('sonarr',8989),('prowlarr',9696),('qbittorrent',8081)]
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
                for path, keys in [(root/'local/homepage.env', {'HOMEPAGE_AUTH_ENABLED','HOMEPAGE_AUTH_SECRET','HOMEPAGE_AUTH_PASSWORD'})]:
                    for value in credential_files.read(path, keys).values():
                        if len(value) > 10:
                            diagnostic = diagnostic.replace(value, '<redacted>')
                print(diagnostic, flush=True)
                raise
            ports = {name: port(name, number) for name, number in [('homepage',3000),('seerr',5055),('speedtest',3000),('jellyfin',8096),('radarr',7878),('sonarr',8989),('prowlarr',9696),('qbittorrent',8081)]}
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
            media_secrets = credential_files.read(root/'local/media-credentials', media.SECRET_KEYS)
            seerr_api = media.Client(urls['seerr'])
            seerr_api.call('/api/v1/auth/jellyfin', {'username':'admin', 'password':media_secrets['JELLYFIN_PASSWORD']})
            assert seerr_api.call('/api/v1/settings/public')['initialized'], 'Seerr wizard was not completed'
            assert sum(library['enabled'] for library in seerr_api.call('/api/v1/settings/jellyfin/library')) == 2
            for name, category in [('radarr','movies'), ('sonarr','tv')]:
                settings = seerr_api.call('/api/v1/settings/'+name)
                assert len(settings) == 1 and settings[0]['isDefault'], 'Seerr duplicate/missing default server'
                assert settings[0]['activeDirectory'] == '/data/library/'+category
                client = media.Client(urls[name], media_secrets[name.upper()+'_API_KEY'])
                clients = client.call('/api/v3/downloadclient')
                assert len(clients) == 1 and clients[0]['enable'], 'Download client was duplicated or disabled'
                assert request(ports[name], 'localhost', '/api/v3/system/status')[0] in (401,403)
            prowlarr = media.Client(urls['prowlarr'], media_secrets['PROWLARR_API_KEY'])
            assert len(prowlarr.call('/api/v1/applications')) == 2, 'Prowlarr application sync duplicated'
            # Render real templates; only upstream addresses differ in this container fixture.
            certificates = root / 'certs'
            certificates.mkdir()
            runtime.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
                         '-subj', '/CN=xdadwal.in', '-keyout', str(certificates/'privkey.pem'),
                         '-out', str(certificates/'fullchain.pem')], timeout=60)
            nginx_config = root / 'nginx.conf'
            text = proxy.render(c, ROOT, https=True)
            text = text.replace('127.0.0.1:3002', 'homepage:3000')
            for name, number in [('seerr',5055),('speedtest',3000),('jellyfin',8096),('radarr',7878),('sonarr',8989),('prowlarr',9696),('qbittorrent',8081)]:
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
                    assert tls_request(c['HOMEPAGE_HOST'])[0] in (302, 307)
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
            hp = credential_files.read(root/'local/homepage.env', {'HOMEPAGE_AUTH_ENABLED','HOMEPAGE_AUTH_SECRET','HOMEPAGE_AUTH_PASSWORD'})
            payload = urllib.parse.urlencode({'csrfToken':csrf, 'password':hp['HOMEPAGE_AUTH_PASSWORD'],
                                               'callbackUrl':'https://'+c['HOMEPAGE_HOST'], 'json':'true'})
            code, body, login_headers = tls_request(c['HOMEPAGE_HOST'], '/api/auth/callback/credentials', 'POST', payload,
                                                   {'Content-Type':'application/x-www-form-urlencoded','Cookie':cookie}, full=True)
            assert code == 200 and 'error' not in json.loads(body).get('url',''), 'Homepage password login failed'
            session = '; '.join(value.split(';', 1)[0] for key,value in login_headers if key.lower() == 'set-cookie')
            assert session, 'Homepage session cookie missing'
            code, body = tls_request(c['HOMEPAGE_HOST'], '/api/services', hdr={'Cookie':session})
            assert code == 200 and b'Seerr' in body and b'Jellyfin' in body, 'Homepage authenticated service list failed'
            speed_service = next(service for group in json.loads(body) for service in group['services']
                                 if service['name'] == 'OpenSpeedTest')
            speed_widget = speed_service['widgets'][0]
            assert speed_widget['type'] == 'iframe', 'Speed test iframe missing from authenticated dashboard'
            assert speed_widget['src'] == 'https://'+c['SPEED_HOST']+'/', 'Speed test must use the browser-reachable HTTPS hostname'
            assert speed_widget['loadingStrategy'] == 'lazy', 'Speed test iframe should load lazily'
            assert not speed_widget.get('refreshInterval'), 'Do not reload or interrupt a running speed test'
            rejected = urllib.parse.urlencode({'csrfToken':csrf, 'password':'not-the-password',
                                                'callbackUrl':'https://'+c['HOMEPAGE_HOST'], 'json':'true'})
            attempts = [tls_request(c['HOMEPAGE_HOST'], '/api/auth/callback/credentials', 'POST', rejected,
                                    {'Content-Type':'application/x-www-form-urlencoded','Cookie':cookie})[0]
                        for _ in range(8)]
            assert 429 in attempts, 'Homepage proxy login rate limit was not enforced'
            assert request(http_port, c['REQUESTS_HOST'])[0] == 301
            assert tls_request(c['JELLYFIN_HOST'], '/System/Info/Public')[0] == 200
            assert tls_request(c['REQUESTS_HOST'], '/api/v1/settings/public')[0] == 200
            speed_code, speed_body, speed_headers = tls_request(c['SPEED_HOST'], full=True)
            assert speed_code == 200 and b'OpenSpeedTest' in speed_body
            frame_options = dict((k.lower(),v) for k,v in speed_headers).get('x-frame-options','').upper()
            assert frame_options not in ('DENY','SAMEORIGIN'), 'Speed test response blocks dashboard embedding'
            # Actual 35 MiB upload through proxy verifies the documented body-size requirement.
            result = tls_request(c['SPEED_HOST'], '/upload', 'POST', b'x' * (35*1024*1024))
            assert result[0] == 200, f'speed upload returned {result[0]}'
            print('PASS: eight apps, media API connections and rerun preservation, Homepage password login/session and OpenSpeedTest iframe configuration, private services and login rate limit, Nginx TLS/routes, and 35 MiB speed upload.', flush=True)
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
