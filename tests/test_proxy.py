from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/lib'))
import re

import config
import proxy


class ProxyTests(unittest.TestCase):
    def test_reusable_routes_match_stable_host_policy(self):
        c = config.load(ROOT / '.env.example')
        c.update(HOMEPAGE_HOST='ohara.xdadwal.in', PORTFOLIO_PORT='8010')
        rendered = proxy.render(c, ROOT, https=True, acme_names={'files.xdadwal.in'})
        deployed = (ROOT / 'configs/nginx/deployed/ohara.conf').read_text()
        # DNS-mode migration appends protected music routes while preserving the
        # existing shared HTTP block and other server ordering.
        self.assertIn('listen [::]:443 ssl;', proxy.navidrome_config(c, ROOT))
        self.assertIn('access_log off;\n    error_log /dev/null;', rendered)
        rendered = rendered.replace('\n' + proxy.navidrome_config(c, ROOT), '')
        rendered = rendered.replace(c['NAVIDROME_HOST'] + ' ', '')
        rendered = rendered.replace('    access_log off;\n    error_log /dev/null;\n', '')
        blocks = re.findall(r'(?ms)^server \{\n.*?^\}\n?', deployed)
        music = [block for block in blocks if 'server_name ' + c['NAVIDROME_HOST'] + ';' in block]
        self.assertEqual(len(music), 2)
        for block in music:
            self.assertIn('access_log off;', block)
            self.assertIn('error_log /dev/null;', block)
            if 'listen 443 ssl;' in block:
                expected = proxy.navidrome_config(c, ROOT)
                self.assertEqual(
                    block.replace('/live/ohara-wildcard/', '/live/ohara/').split(), expected.split()
                )
            else:
                self.assertIn('return 301 https://$host$request_uri;', block)
            deployed = deployed.replace(block, '')
        # Host-specific owner decision: Seerr is LAN-only here, while the reusable
        # template keeps the public route with its image-proxy denial. Remove
        # exactly that difference before comparing the remaining policy.
        guard = '    if ($ohara_lan_allowed = 0) { return 403; }\n'
        seerr = [block for block in blocks if 'server_name seerr.xdadwal.in;' in block]
        self.assertEqual(len(seerr), 2)
        for block in seerr:
            self.assertEqual(block.count(guard), 1)
            if 'listen 443 ssl;' in block:
                deployed = deployed.replace(block, block.replace(guard, ''))
            else:
                self.assertEqual(
                    block.split(),
                    (
                        'server { listen 80; listen [::]:80; server_name seerr.xdadwal.in; '
                        '# Reject before redirects, including callers supplying forged forwarding headers. '
                        'if ($ohara_lan_allowed = 0) { return 403; } '
                        'return 301 https://$host$request_uri; }'
                    ).split(),
                )
                deployed = deployed.replace(block, '')
        # Host-specific: www redirects straight to the apex. The reusable
        # templates have no such route (their HTTP-mode certificate does not
        # list www), so check these two blocks here and leave them out below.
        www = [block for block in blocks if 'server_name www.xdadwal.in;' in block]
        self.assertEqual(len(www), 2)
        for block in www:
            self.assertEqual(block.count('return 301 https://xdadwal.in$request_uri;'), 1)
            self.assertNotIn('proxy_pass', block)
            self.assertNotIn('location', block)
            if 'listen 443 ssl;' in block:
                self.assertIn('/live/ohara-wildcard/fullchain.pem;', block)
            deployed = deployed.replace(block, '')
        shared = 'server_name ohara.xdadwal.in xdadwal.in files.xdadwal.in speed.xdadwal.in tv.xdadwal.in;'
        self.assertEqual(deployed.count(shared), 1)
        deployed = deployed.replace(shared, shared[:-1] + ' seerr.xdadwal.in;')

        def normalize(text):
            # Localhost uses certificates that fresh hosts do not yet have.
            # Ignore only these two explicit host-specific blocks and harmless
            # whitespace/comments/certificate-lineage/host-order differences.
            text = re.sub(
                r'(?ms)^server \{\n(?:(?!^\}).)*server_name localhost 127\.0\.0\.1;(?:(?!^\}).)*^\}\n?',
                '',
                text,
            )
            text = text.replace('/live/ohara-wildcard/', '/live/ohara/')
            text = re.sub(
                r'server_name ([^;]+);',
                lambda m: 'server_name ' + ' '.join(sorted(m[1].split())) + ';',
                text,
            )
            text = re.sub(r'(?m)^\s*#.*$', '', text)
            return re.sub(r'\s+', ' ', text).strip()

        self.assertEqual(normalize(rendered), normalize(deployed))
        self.assertEqual(deployed.count('server_name localhost 127.0.0.1;'), 2)
        self.assertIn('return 302 https://xdadwal.in$request_uri;', deployed)
        # The temporary public-IP probe was removed on 2026-11-26.
        self.assertFalse((ROOT / 'configs/nginx/deployed/ohara-public-ip-test.conf').exists())
        self.assertNotIn('45.120.160.21', deployed)

    def test_portfolio_static_files_are_cached_briefly_and_compressed(self):
        c = config.load(ROOT / '.env.example')
        c.update(PORTFOLIO_PORT='8010')
        rendered = proxy.render(c, ROOT, https=True)
        portfolio = rendered[rendered.index('# Optional portfolio process') :]
        # Directives only: the template's comments mention the words checked below.
        portfolio = re.sub(r'(?m)^\s*#.*\n', '', portfolio)
        for location, age in [
            ('location ^~ /static/img/ {', 604800),
            ('location = /favicon.ico {', 604800),
            ('location ^~ /static/ {', 3600),
        ]:
            block = portfolio[portfolio.index(location) :]
            block = block[: block.index('\n    }\n')]
            self.assertIn('proxy_pass http://127.0.0.1:8010;', block)
            self.assertIn('proxy_set_header Host $host;', block)
            self.assertIn(f'add_header Cache-Control "public, max-age={age}";', block)
        # File names are not versioned, and errors must not be cached.
        self.assertNotIn('immutable', portfolio)
        self.assertNotIn('always', portfolio)
        self.assertEqual(portfolio.count('add_header'), 3)
        # Nothing but the three static locations sets a cache lifetime.
        self.assertEqual(rendered.count('Cache-Control'), 3)
        types = re.search(r'gzip_types ([^;]+);', portfolio)[1].split()
        self.assertIn('text/css', types)
        self.assertNotIn('text/html', types)  # always compressed; listing it warns
        self.assertFalse([t for t in types if t.startswith('image/') and t != 'image/svg+xml'])
        self.assertIn('gzip_vary on;', portfolio)
        # Without a portfolio the settings are not rendered at all.
        self.assertNotIn(
            'gzip_types', proxy.render(config.load(ROOT / '.env.example'), ROOT, https=True)
        )

    def test_bootstrap_never_references_missing_certificates(self):
        text = proxy.render(config.load(ROOT / '.env.example'), ROOT, https=False)
        self.assertNotIn('ssl_certificate', text)
        self.assertNotIn('proxy_pass', text)
        self.assertIn('/.well-known/acme-challenge/', text)

    def test_https_routes_do_not_expose_dns_admin(self):
        text = proxy.render(config.load(ROOT / '.env.example'), ROOT, https=True)
        self.assertNotIn('8888', text)
        self.assertNotIn('pihole', text)
        self.assertIn('client_max_body_size 40m', text)
        self.assertIn('proxy_request_buffering off', text)
        self.assertIn('proxy_set_header X-Forwarded-For $remote_addr;', text)
        self.assertIn('proxy_set_header X-Real-IP $remote_addr;', text)
        self.assertNotIn('$proxy_add_x_forwarded_for', text)

    def test_seerr_imageproxy_is_denied_in_generic_and_deployed_routes(self):
        generic = proxy.render(config.load(ROOT / '.env.example'), ROOT, https=True)
        deployed = (ROOT / 'configs/nginx/deployed/ohara.conf').read_text()
        raw_guard = 'if ($request_uri ~* "^/imageproxy(?:/|$|\\?)") {\n        return 404;\n    }'
        denial = 'location ~* ^/imageproxy(?:/|$) {\n        return 404;\n    }'
        for text in (generic, deployed):
            self.assertIn(raw_guard, text)
            self.assertIn(denial, text)
            self.assertLess(text.index(raw_guard), text.index(denial))
            self.assertLess(text.index(denial), text.index('proxy_pass http://127.0.0.1:5055;'))

    def test_deployed_seerr_route_is_lan_only(self):
        deployed = (ROOT / 'configs/nginx/deployed/ohara.conf').read_text()
        lan = (ROOT / 'configs/nginx/deployed/ohara-lan.conf').read_text()
        guard = 'if ($ohara_lan_allowed = 0) { return 403; }'
        self.assertIn('geo $ohara_lan_allowed {', lan)
        servers = [
            block
            for block in deployed.split('\nserver {')
            if 'server_name seerr.xdadwal.in;' in block
        ]
        self.assertEqual(len(servers), 2)
        for block in servers:
            self.assertIn(guard, block)
            for later in ('return 301', 'proxy_pass', '$request_uri ~*'):
                if later in block:
                    self.assertLess(block.index(guard), block.index(later))
        # The shared ACME/redirect server must not also answer for Seerr.
        shared = [block for block in deployed.split('\nserver {') if 'acme-challenge' in block]
        self.assertTrue(shared)
        self.assertFalse(any('seerr.xdadwal.in' in block for block in shared))

    def test_invalid_candidate_restores_previous_file(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'ohara.conf'
            target.write_text('# Managed by Ohara\nold')
            calls = []

            def failing(args, **kwargs):
                calls.append(args)
                raise RuntimeError('nginx test failed')

            with self.assertRaises(RuntimeError):
                proxy.apply_config('# Managed by Ohara\nnew', target=target, runner=failing)
            self.assertEqual(target.read_text(), '# Managed by Ohara\nold')
            self.assertFalse(any('reload' in c for c in calls))

    def test_reload_failure_restores_previous_file(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'ohara.conf'
            target.write_text('# Managed by Ohara\nold')
            count = 0

            def failing(args, **kwargs):
                nonlocal count
                if 'reload' in args:
                    count += 1
                    if count == 1:
                        raise RuntimeError('reload failed')

            with self.assertRaises(RuntimeError):
                proxy.apply_config('# Managed by Ohara\nnew', target=target, runner=failing)
            self.assertEqual(target.read_text(), '# Managed by Ohara\nold')
            self.assertEqual(count, 2)

    def test_unrelated_site_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'ohara.conf'
            target.write_text('unrelated site')
            with self.assertRaises(ValueError):
                proxy.apply_config('new', target=target)
            self.assertEqual(target.read_text(), 'unrelated site')

    def test_renewal_hook_uses_absolute_installed_commands(self):
        self.assertIn('/usr/sbin/nginx -t', proxy.RENEW_HOOK)
        self.assertIn('&& /usr/bin/systemctl reload nginx', proxy.RENEW_HOOK)
        self.assertNotIn(str(ROOT), proxy.RENEW_HOOK)


if __name__ == '__main__':
    unittest.main()


class AcmeMigrationTests(unittest.TestCase):
    def test_new_names_get_challenge_handler_without_removing_https(self):
        c = config.load(ROOT / '.env.example')
        old = proxy.render(c, ROOT, https=True)
        c['SPEED_HOST'] = 'share.xdadwal.in'
        candidate = proxy.challenge_config(old, c)
        self.assertTrue(candidate.startswith(old))
        addition = candidate[len(old) :]
        self.assertIn('server_name share.xdadwal.in;', addition)
        self.assertIn('/.well-known/acme-challenge/', addition)
        self.assertNotIn('proxy_pass', addition)
        self.assertEqual(proxy.challenge_config(candidate, c), candidate)

    def test_failed_acme_restores_working_routes(self):
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'ohara.conf'
            c = config.load(ROOT / '.env.example')
            old = proxy.render(c, ROOT, https=True)
            target.write_text(old)
            c['SPEED_HOST'] = 'share.xdadwal.in'

            def apply(text):
                target.write_text(text)

            def failed_issuance(args, **kwargs):
                self.assertIn('server_name share.xdadwal.in;', target.read_text())
                raise RuntimeError('ACME failed')

            with (
                patch.object(proxy, 'TARGET', target),
                patch.object(proxy, 'apply_config', side_effect=apply),
                patch.object(proxy, 'run', side_effect=failed_issuance),
            ):
                with self.assertRaisesRegex(RuntimeError, 'ACME failed'):
                    proxy.activate(c, ROOT, accounts_ready=True, agree=True)
            self.assertEqual(target.read_text(), old)
