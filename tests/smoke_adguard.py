"""Disposable DNS integration check; never reads deployment credentials."""
import base64
import json
import os
import select
import socket
import struct
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts/lib'))
import adguard
import config
import runtime


def main():
    import bcrypt
    prefix = runtime.docker_prefix()
    name = 'ohara-dns-smoke-'+uuid.uuid4().hex[:10]

    def docker(*args, capture=False):
        return runtime.run(prefix+list(args), capture=capture, timeout=120)

    with tempfile.TemporaryDirectory(prefix='ohara-dns-smoke-') as directory:
        base = Path(directory)
        base.chmod(0o755)
        (base/'conf').mkdir()
        (base/'work').mkdir()
        c = config.load(ROOT/'.env.example')
        c.update(ADGUARD_BIND_IP='192.168.1.101', ADGUARD_NETWORK='192.168.1.0/24')
        fixture = 'fixture-only-password-12345'
        data = adguard.initial_config(c, bcrypt.hashpw(fixture.encode(), bcrypt.gensalt()).decode())
        # Only this disposable fixture permits Docker's bridge source address.
        gateway = json.loads(docker('network', 'inspect', 'bridge', capture=True))[0]['IPAM']['Config'][0]['Gateway']
        data['dns']['allowed_clients'] = [gateway]
        data['filters'] = []  # Controlled filter test without a downloaded list.
        data['user_rules'] = ['||blocked.example.test^']
        (base/'conf/AdGuardHome.yaml').write_text(json.dumps(data))
        image = config.images(ROOT/'versions.env')['ADGUARD_IMAGE']
        try:
            docker('run', '-d', '--name', name, '--cap-drop', 'ALL',
                   '--cap-add', 'NET_BIND_SERVICE', '--cap-add', 'NET_RAW',
                   '--security-opt', 'no-new-privileges:true', '--user', f'{os.getuid()}:{os.getgid()}',
                   '-v', str(base/'conf')+':/opt/adguardhome/conf',
                   '-v', str(base/'work')+':/opt/adguardhome/work',
                   '-p', '127.0.0.1::1053/udp', '-p', '127.0.0.1::1053/tcp',
                   '-p', '127.0.0.1::3000/tcp', image)
            ports = json.loads(docker('inspect', '--format', '{{json .NetworkSettings.Ports}}', name, capture=True))
            http_port = ports['3000/tcp'][0]['HostPort']
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            token = base64.b64encode(('admin:'+fixture).encode()).decode()

            def api():
                request = urllib.request.Request(f'http://127.0.0.1:{http_port}/control/status',
                                                 headers={'Authorization': 'Basic '+token})
                with opener.open(request, timeout=2) as response:
                    return json.load(response)

            deadline = time.monotonic()+30
            while True:
                try:
                    assert api()['running'] is True
                    break
                except (OSError, urllib.error.URLError):
                    if time.monotonic() > deadline:
                        raise RuntimeError('Disposable AdGuard did not become ready') from None
                    time.sleep(0.25)
            try:
                opener.open(f'http://127.0.0.1:{http_port}/control/status', timeout=2)
                raise AssertionError('Admin API allowed anonymous access')
            except urllib.error.HTTPError as error:
                assert error.code == 401

            for protocol in ('udp', 'tcp'):
                port = ports[f'1053/{protocol}'][0]['HostPort']

                def query(hostname, kind='A'):
                    args = ['dig', '@127.0.0.1', '-p', port, '+time=3', '+tries=1', '+short', hostname, kind]
                    if protocol == 'tcp':
                        args.append('+tcp')
                    result = subprocess.run(args, capture_output=True, text=True, timeout=8)
                    assert result.returncode == 0, f'{protocol} DNS query failed'
                    return result.stdout.strip()

                for key in ('DOMAIN', 'HOMEPAGE_HOST', 'REQUESTS_HOST', 'SPEED_HOST', 'JELLYFIN_HOST', 'NAVIDROME_HOST'):
                    assert query(c[key]) == c['ADGUARD_BIND_IP'], f'{protocol}: rewrite failed'
                for service in ('adguard', 'radarr', 'sonarr', 'prowlarr', 'qbittorrent', 'lidarr', 'bazarr'):
                    assert query(service+'.'+c['DOMAIN']) == c['ADGUARD_BIND_IP'], f'{protocol}: internal rewrite failed'
                assert query(c['JELLYFIN_HOST'], 'AAAA') == '', 'Rewritten name leaked IPv6'
                assert query('blocked.example.test') == '0.0.0.0', 'Controlled filter failed'
                assert query('example.org'), 'Encrypted upstream lookup failed'
            # Browsers issue parallel lookups; the default subnet-wide limit
            # silently drops bursts even when isolated lookups work.
            labels = b''.join(bytes([len(label)])+label.encode() for label in c['JELLYFIN_HOST'].split('.'))+b'\0'
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.setblocking(False)
                for ident in range(30):
                    packet = struct.pack('!HHHHHH', ident, 0x100, 1, 0, 0, 0)+labels+struct.pack('!HH', 1, 1)
                    sock.sendto(packet, ('127.0.0.1', int(ports['1053/udp'][0]['HostPort'])))
                received = set()
                deadline = time.monotonic()+3
                while len(received) < 30 and time.monotonic() < deadline:
                    ready, _, _ = select.select([sock], [], [], max(0, deadline-time.monotonic()))
                    if not ready:
                        break
                    packet, _ = sock.recvfrom(4096)
                    ident, flags = struct.unpack('!HH', packet[:4])
                    if flags & 15 == 0 and packet.endswith(socket.inet_aton(c['ADGUARD_BIND_IP'])):
                        received.add(ident)
                assert len(received) == 30, f'Parallel LAN DNS requests dropped: {30-len(received)}'
            docker('restart', name)
            ports = json.loads(docker('inspect', '--format', '{{json .NetworkSettings.Ports}}', name, capture=True))
            http_port = ports['3000/tcp'][0]['HostPort']
            deadline = time.monotonic()+20
            while True:
                try:
                    assert api()['running'] is True
                    break
                except (OSError, urllib.error.URLError):
                    if time.monotonic() > deadline:
                        raise RuntimeError('Disposable AdGuard restart failed') from None
                    time.sleep(0.25)
            print('PASS: disposable AdGuard non-root startup, protected API, UDP/TCP rewrites, IPv6 response, filtering, encrypted upstream, parallel DNS burst and restart.')
        finally:
            docker('rm', '-f', name)


if __name__ == '__main__':
    main()
