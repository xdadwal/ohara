#!/usr/bin/env python3
"""Start the pinned Immich release with disposable volumes and machine learning off."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import struct
import zlib
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/lib'))
import config
import immich


def main():
    project = 'ohara-immich-smoke-' + uuid.uuid4().hex[:10]
    with tempfile.TemporaryDirectory(prefix='ohara-immich-smoke-') as directory:
        root = Path(directory)
        shutil.copy(ROOT / 'compose.immich.yaml', root)
        shutil.copy(ROOT / 'versions.immich.env', root)
        shutil.copytree(ROOT / 'configs/immich', root / 'configs/immich')
        # Fixed test input, never installed in the real private configuration.
        (root / '.env').write_text('IMMICH_DB_PASSWORD=DisposableSmokeOnly12345\n')
        (root / '.env').chmod(0o600)
        c = config.load(ROOT / '.env.example')
        override = root / 'smoke.yaml'
        override.write_text('''services:
  immich-server:
    ports: !override
      - "127.0.0.1::2283"
    volumes: !override
      - smoke-library:/data
      - type: bind
        source: ''' + str(root / 'configs/immich/immich.json') + '''
        target: /etc/immich/immich.json
        read_only: true
  database:
    volumes: !override
      - smoke-database:/var/lib/postgresql/data
volumes:
  smoke-library:
  smoke-database:
''')
        def compose(args, **kwargs):
            return immich.compose(c, root, ['-p', project, '-f', str(override)] + args, **kwargs)
        try:
            print('Starting isolated Immich, PostgreSQL and Valkey (no machine learning)...', flush=True)
            compose(['up', '-d', '--wait', '--wait-timeout', '180'], timeout=900)
            port = int(compose(['port', 'immich-server', '2283'], capture=True).strip().rsplit(':', 1)[1])
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            def request(path, body=None, token=None):
                headers = {'Content-Type': 'application/json'}
                if token:
                    headers['Authorization'] = 'Bearer ' + token
                data = None if body is None else json.dumps(body).encode()
                with opener.open(urllib.request.Request(f'http://127.0.0.1:{port}/api/{path}',
                        data=data, headers=headers), timeout=30) as response:
                    return json.load(response)
            assert request('server/ping')['res'] == 'pong'
            request('auth/admin-sign-up', {'email': 'smoke@example.invalid',
                    'password': 'DisposableOwnerOnly12345', 'name': 'Disposable Smoke'})
            session = request('auth/login', {'email': 'smoke@example.invalid', 'password': 'DisposableOwnerOnly12345'})
            policy = request('system-config', token=session['accessToken'])
            assert policy['machineLearning']['enabled'] is False
            assert policy['oauth']['autoRegister'] is False
            assert policy['passwordLogin']['enabled'] is True
            # A tiny generated PNG fixture verifies original-file round trip.
            def chunk(kind, data):
                return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
            image = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 8, 8, 8, 2, 0, 0, 0))
                     + chunk(b'IDAT', zlib.compress((b'\x00' + b'\xff\x00\x00' * 8) * 8)) + chunk(b'IEND', b''))
            boundary = 'ohara-smoke-upload'
            body = b''
            for name in ('fileCreatedAt', 'fileModifiedAt'):
                body += (f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'
                         '2026-10-22T00:00:00.000Z\r\n').encode()
            body += (f'--{boundary}\r\nContent-Disposition: form-data; name="assetData"; filename="smoke.png"\r\n'
                     'Content-Type: image/png\r\n\r\n').encode() + image + f'\r\n--{boundary}--\r\n'.encode()
            headers = {'Authorization': 'Bearer ' + session['accessToken'],
                       'Content-Type': 'multipart/form-data; boundary=' + boundary}
            with opener.open(urllib.request.Request(f'http://127.0.0.1:{port}/api/assets',
                    data=body, headers=headers), timeout=30) as response:
                asset = json.load(response)
            with opener.open(urllib.request.Request(f'http://127.0.0.1:{port}/api/assets/{asset["id"]}/original',
                    headers={'Authorization': 'Bearer ' + session['accessToken']}), timeout=30) as response:
                assert response.read() == image
            services = set(compose(['ps', '--services'], capture=True).split())
            assert services == {'immich-server', 'redis', 'database'}
            print('Immich smoke passed: healthy containers, API, owner login, photo round trip and machine learning disabled.', flush=True)
        finally:
            # Only this randomly named test project and its disposable volumes.
            compose(['down', '--volumes'], timeout=120)


if __name__ == '__main__':
    main()
