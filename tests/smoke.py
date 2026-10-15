#!/usr/bin/env python3
"""Exercise pinned applications and rendered Nginx using only disposable data."""
import base64
import http.client
import json
import os
from pathlib import Path
import shutil
import socket
import ssl
import struct
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
        c.update(DATA_ROOT=str(root / 'data'), FILES_ROOT=str(root / 'files'),
                 RUN_UID=str(os.getuid() or 1000), RUN_GID=str(os.getgid() or 1000))
        host.prepare_storage(c, root)
        # Real container runs as 1000 in both production and disposable Linux CI.
        if os.geteuid() == 0:
            os.chown(root / 'data/seerr', 1000, 1000)
        for path in [root / 'data', root / 'files', root / 'data/seerr', root / 'data/copyparty', root / 'data/homepage']:
            path.chmod(0o777)  # disposable fixture only, never a production setup behavior
        (root / 'local/copyparty.conf').chmod(0o644)
        override = root / 'smoke.yaml'
        override.write_text('services:\n' + '\n'.join(
            f'  {name}:\n    ports: !override\n      - "127.0.0.1::{port}"'
            for name, port in [('homepage',3000),('seerr',5055),('copyparty',3923),('speedtest',3000)]
        ) + '\n  pihole:\n    ports: !override\n      - "127.0.0.1::80"\n      - "127.0.0.1::53/udp"\n      - "127.0.0.1::53/tcp"\n')
        def compose(args, capture=False, timeout=120):
            return runtime.compose(c, root, ['-p', identifier, '-f', str(override)] + args,
                                   capture=capture, timeout=timeout, docker=docker)
        def port(service, internal, udp=False):
            args = ['port'] + (['--protocol', 'udp'] if udp else []) + [service, str(internal)]
            return int(compose(args, True).strip().rsplit(':', 1)[1])
        nginx_name = identifier + '-proxy'
        try:
            print('Starting isolated application stack...', flush=True)
            try:
                compose(['up', '-d', '--wait', '--wait-timeout', '180'], timeout=900)
            except RuntimeError:
                diagnostic = compose(['logs', '--no-color', '--tail', '25', 'homepage'], capture=True)
                for path, keys in [(root/'local/homepage.env', {'HOMEPAGE_AUTH_ENABLED','HOMEPAGE_AUTH_SECRET','HOMEPAGE_AUTH_PASSWORD'})]:
                    for value in config.parse(path, keys).values():
                        if len(value) > 10:
                            diagnostic = diagnostic.replace(value, '<redacted>')
                print(diagnostic, flush=True)
                raise
            ports = {name: port(name, number) for name, number in [('homepage',3000),('seerr',5055),('copyparty',3923),('speedtest',3000),('pihole',80)]}
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
            credentials = config.parse(root / 'local/credentials', {'COPYPARTY_PASSWORD', 'PIHOLE_PASSWORD'})
            auth = 'Basic ' + base64.b64encode(('admin:' + credentials['COPYPARTY_PASSWORD']).encode()).decode()
            headers = {'Authorization': auth}
            code, _ = request(ports['copyparty'], 'localhost', '/probe.txt', 'PUT', b'ohara probe', headers)
            assert code in (200,201,204), f'authenticated upload returned {code}'
            code, content = request(ports['copyparty'], 'localhost', '/probe.txt', headers=headers)
            assert code == 200 and content == b'ohara probe', 'authenticated download failed'
            code, content = request(ports['copyparty'], 'localhost', '/probe.txt')
            assert code in (401,403,404), f'anonymous file read returned {code}'
            code, _ = request(ports['copyparty'], 'localhost', '/anonymous.txt', 'PUT', b'blocked')
            assert code in (401,403,404), f'anonymous write returned {code}'
            # UDP DNS to a deterministic local record avoids dependence on upstream internet DNS.
            compose(['exec', '-T', 'pihole', 'pihole-FTL', '--config', 'dns.hosts', '["192.168.1.123 smoke.test"]'])
            compose(['exec', '-T', 'pihole', 'pihole', 'reloaddns'])
            time.sleep(2)
            query = struct.pack('!HHHHHH', 1234, 0x100, 1, 0, 0, 0) + b'\x05smoke\x04test\0\0\x01\0\x01'
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.settimeout(10)
                sock.sendto(query, ('127.0.0.1', port('pihole', 53, True)))
                answer = sock.recv(4096)
                assert b'\xc0\xa8\x01\x7b' in answer, 'DNS did not return local fixture address'
            # Render real templates; only upstream addresses differ in this container fixture.
            certificates = root / 'certs'
            certificates.mkdir()
            runtime.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
                         '-subj', '/CN=xdadwal.in', '-keyout', str(certificates/'privkey.pem'),
                         '-out', str(certificates/'fullchain.pem')], timeout=60)
            nginx_config = root / 'nginx.conf'
            text = proxy.render(c, ROOT, https=True)
            text = text.replace('127.0.0.1:3002', 'homepage:3000')
            for name, number in [('seerr',5055),('copyparty',3923),('speedtest',3000)]:
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
                    assert tls_request(c['DOMAIN'])[0] in (302, 307)
                    break
                except (OSError, RuntimeError, http.client.HTTPException):
                    if time.monotonic()>deadline:
                        raise
                    time.sleep(1)
            code, body, denied_headers = tls_request(c['DOMAIN'], '/api/services', full=True)
            redirect = dict((k.lower(),v) for k,v in denied_headers).get('location','')
            assert code in (401,403) or (code in (302,307) and '/auth/signin' in redirect), f'Homepage anonymous API returned {code}'
            code, body, csrf_headers = tls_request(c['DOMAIN'], '/api/auth/csrf', full=True)
            assert code == 200, 'Homepage CSRF endpoint failed'
            csrf = json.loads(body)['csrfToken']
            cookie = '; '.join(value.split(';', 1)[0] for key,value in csrf_headers if key.lower() == 'set-cookie')
            hp = config.parse(root/'local/homepage.env', {'HOMEPAGE_AUTH_ENABLED','HOMEPAGE_AUTH_SECRET','HOMEPAGE_AUTH_PASSWORD'})
            payload = urllib.parse.urlencode({'csrfToken':csrf, 'password':hp['HOMEPAGE_AUTH_PASSWORD'],
                                               'callbackUrl':'https://'+c['DOMAIN'], 'json':'true'})
            code, body, login_headers = tls_request(c['DOMAIN'], '/api/auth/callback/credentials', 'POST', payload,
                                                   {'Content-Type':'application/x-www-form-urlencoded','Cookie':cookie}, full=True)
            assert code == 200 and 'error' not in json.loads(body).get('url',''), 'Homepage password login failed'
            session = '; '.join(value.split(';', 1)[0] for key,value in login_headers if key.lower() == 'set-cookie')
            assert session, 'Homepage session cookie missing'
            code, body = tls_request(c['DOMAIN'], '/api/services', hdr={'Cookie':session})
            assert code == 200 and b'Seerr' in body and b'Copyparty' in body, 'Homepage authenticated service list failed'
            rejected = urllib.parse.urlencode({'csrfToken':csrf, 'password':'not-the-password',
                                                'callbackUrl':'https://'+c['DOMAIN'], 'json':'true'})
            attempts = [tls_request(c['DOMAIN'], '/api/auth/callback/credentials', 'POST', rejected,
                                    {'Content-Type':'application/x-www-form-urlencoded','Cookie':cookie})[0]
                        for _ in range(8)]
            assert 429 in attempts, 'Homepage proxy login rate limit was not enforced'
            assert request(http_port, c['FILES_HOST'])[0] == 301
            assert tls_request(c['REQUESTS_HOST'], '/api/v1/settings/public')[0] == 200
            assert tls_request(c['FILES_HOST'], '/probe.txt', hdr=headers) == (200, b'ohara probe')
            assert tls_request(c['FILES_HOST'], '/probe.txt')[0] in (401,403,404)
            assert tls_request(c['SPEED_HOST'])[0] == 200
            # Actual 35 MiB upload through proxy verifies the documented body-size requirement.
            result = tls_request(c['SPEED_HOST'], '/upload', 'POST', b'x' * (35*1024*1024))
            assert result[0] == 200, f'speed upload returned {result[0]}'
            print('PASS: five apps, Homepage password login/session, private services and login rate limit, authenticated file upload/download, anonymous denial, LAN DNS fixture, Nginx TLS/routes, and 35 MiB speed upload.', flush=True)
        finally:
            runtime.run(docker + ['rm', '-f', nginx_name], timeout=30) if subprocess.run(docker + ['inspect', nginx_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0 else None
            compose(['down', '--remove-orphans'], timeout=90)
            # Linux preserves container UIDs on bind-mounted dummy files. Restore
            # only this generated fixture's data ownership before tempfile cleanup.
            cp_image = config.images(root / 'versions.env')['COPYPARTY_IMAGE']
            runtime.run(docker + ['run', '--rm', '--user', '0:0', '--entrypoint', '/bin/ash',
                                 '-v', f'{root / "data"}:/fixture', cp_image,
                                 '-c', 'chown -R "$1:$2" /fixture', 'fixture-cleanup',
                                 str(os.getuid()), str(os.getgid())], timeout=60)

if __name__ == '__main__':
    main()
