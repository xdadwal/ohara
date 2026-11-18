"""Exercise the actual host Nginx baselines in a disposable offline container."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts/lib'))
import runtime
import bambuddy_proxy

IMAGE = 'nginx@sha256:ed84151ed2d47ef93c0939eb9b9754c6990db6092cd2081e11988a47a83d47ea'
NAMES = ('adguard', 'radarr', 'sonarr', 'prowlarr', 'qbittorrent', 'lidarr', 'bazarr', 'maintainerr')


def main():
    docker = runtime.docker_prefix()
    name = 'ohara-lan-smoke-'+uuid.uuid4().hex[:10]
    with tempfile.TemporaryDirectory(prefix='ohara-lan-smoke-') as directory:
        base = Path(directory)
        base.chmod(0o755)
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                        '-keyout', str(base/'key.pem'), '-out', str(base/'cert.pem'),
                        '-days', '1', '-subj', '/CN=disposable.invalid'],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # Disposable test keys only; never reads production certificates/credentials.
        (base/'key.pem').chmod(0o644)
        blocks = []
        # Exercise the exact managed routes together with their shared maps.
        for filename in ('ohara-lan.conf', 'ohara.conf', 'ohara-bambuddy.conf'):
            data = (ROOT/'configs/nginx/deployed'/filename).read_text()
            data = re.sub(r'ssl_certificate\s+[^;]+;', 'ssl_certificate /fixture/cert.pem;', data)
            data = re.sub(r'ssl_certificate_key\s+[^;]+;', 'ssl_certificate_key /fixture/key.pem;', data)
            data = re.sub(r'proxy_pass http://127\.0\.0\.1:\d+;', 'proxy_pass http://127.0.0.1:18081;', data)
            blocks.append(data)
        (base/'nginx.conf').write_text('events {}\nhttp {\n'+''.join(blocks)+
                                       '\nserver { listen 127.0.0.1:18081; return 200 "fixture backend"; }\n}\n')
        mount = ['-v', str(base)+':/fixture:ro']
        runtime.run(docker+['run', '--rm', '--network', 'none']+mount+[IMAGE, 'nginx', '-t', '-c', '/fixture/nginx.conf'])
        try:
            runtime.run(docker+['run', '-d', '--name', name, '--network', 'none']+mount+
                        [IMAGE, 'nginx', '-c', '/fixture/nginx.conf', '-g', 'daemon off;'])
            # docker run -d returns before Nginx necessarily opens its listeners.
            # Wait only for startup; route and access-control assertions stay strict.
            runtime.run(docker+['exec', name, 'curl', '--noproxy', '*', '-fsS',
                                '--retry', '20', '--retry-connrefused', '--retry-delay', '1',
                                '--retry-max-time', '30', '--max-time', '5',
                                'http://127.0.0.1:18081/'], timeout=40)

            def status(hostname, interface, tls, forged=False, path='/'):
                port = '443' if tls else '80'
                command = docker+['exec', name, 'curl', '--noproxy', '*', '-ksS',
                                  '--max-time', '5', '--interface', interface,
                                  '--path-as-is',
                                  '--resolve', hostname+':'+port+':127.0.0.1',
                                  '-o', '/dev/null', '-w', '%{http_code}']
                if forged:
                    command += ['-H', 'X-Forwarded-For: 192.168.1.5', '-H', 'X-Real-IP: 192.168.1.5']
                command += [('https' if tls else 'http')+'://'+hostname+path]
                return runtime.run(command, capture=True).strip()

            for service in NAMES:
                hostname = service+'.xdadwal.in'
                assert status(hostname, '127.0.0.1', True) == '200', hostname+' allowed proxy failed'
                assert status(hostname, '127.0.0.1', False) == '301', hostname+' redirect failed'
                for tls in (False, True):
                    assert status(hostname, '127.0.0.2', tls) == '403', hostname+' external source accepted'
                    assert status(hostname, '127.0.0.2', tls, True) == '403', hostname+' forged header bypass'
            for hostname in ('xdadwal.in', 'ohara.xdadwal.in', 'tv.xdadwal.in', 'speed.xdadwal.in', 'music.xdadwal.in', 'bambuddy.xdadwal.in'):
                assert status(hostname, '127.0.0.2', True) == '200', 'Existing public route changed: '+hostname
            assert status('bambuddy.xdadwal.in', '127.0.0.2', False) == '301'
            # Seerr is LAN-only on this host; the image-proxy denial stays for LAN clients.
            imageproxy = ('/imageproxy', '/imageproxy/', '/imageproxy//example',
                          '/imageproxy/%2e%2e', '/ImageProxy/example',
                          '/public/%2e%2e/imageproxy/x')
            assert status('seerr.xdadwal.in', '127.0.0.1', True, path='/discover') == '200'
            assert status('seerr.xdadwal.in', '127.0.0.1', False) == '301'
            for path in imageproxy:
                code = status('seerr.xdadwal.in', '127.0.0.1', True, path=path)
                assert code == '404', f'Seerr containment returned {code} for {path}'
            for tls in (False, True):
                for path in ('/', '/discover', '/api/v1/status')+imageproxy:
                    for forged in (False, True):
                        code = status('seerr.xdadwal.in', '127.0.0.2', tls, forged, path=path)
                        assert code == '403', f'Seerr external source got {code} for {path}'
            runtime.run(docker+['stop', name])
            onboarding = bambuddy_proxy.render(ROOT)
            onboarding = re.sub(r'ssl_certificate\s+[^;]+;', 'ssl_certificate /fixture/cert.pem;', onboarding)
            onboarding = re.sub(r'ssl_certificate_key\s+[^;]+;', 'ssl_certificate_key /fixture/key.pem;', onboarding)
            onboarding = re.sub(r'proxy_pass http://127\.0\.0\.1:\d+;', 'proxy_pass http://127.0.0.1:18081;', onboarding)
            (base/'nginx.conf').write_text('events {}\nhttp {\n'+''.join(blocks[:2])+onboarding+
                                           '\nserver { listen 127.0.0.1:18081; return 200 "fixture backend"; }\n}\n')
            runtime.run(docker+['start', name])
            runtime.run(docker+['exec', name, 'curl', '--noproxy', '*', '-fsS', '--retry', '20',
                                '--retry-connrefused', '--retry-delay', '1', '--retry-max-time', '30',
                                '--max-time', '5', 'http://127.0.0.1:18081/'], timeout=40)
            assert status('bambuddy.xdadwal.in', '127.0.0.1', True) == '200'
            for tls in (False, True):
                assert status('bambuddy.xdadwal.in', '127.0.0.2', tls) == '403'
                assert status('bambuddy.xdadwal.in', '127.0.0.2', tls, True) == '403'
            print('PASS: eight admin proxies and Seerr are LAN-only; six public routes preserved; Bambuddy public and fresh LAN-only onboarding modes verified.')
        finally:
            runtime.run(docker+['rm', '-f', name])


if __name__ == '__main__':
    main()
