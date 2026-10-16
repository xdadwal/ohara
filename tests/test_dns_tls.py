from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/lib'))
import config
import dns_godaddy as dns
import dns_tls
import proxy

DATA = {'domain': 'xdadwal.in', 'token': 'private-test-token-123456'}
ENV = {'CERTBOT_DOMAIN': 'xdadwal.in', 'CERTBOT_VALIDATION': 'a' * 43,
       'CERTBOT_REMAINING_CHALLENGES': '0'}


class FakeAPI:
    def __init__(self):
        self.rows = [{'recordId': 'unrelated', 'type': 'TXT', 'name': '_acme-challenge',
                      'data': 'keep-me', 'ttl': 600}]
        self.deleted = []

    def records(self, name):
        return list(self.rows)

    def request(self, method, suffix='', body=None):
        if method == 'POST':
            row = dict(body, recordId=str(len(self.rows)))
            self.rows.append(row)
            return row
        if method == 'DELETE':
            self.deleted.append(suffix[1:])
            self.rows = [r for r in self.rows if '/' + r['recordId'] != suffix]


class DNSTests(unittest.TestCase):
    def test_private_credentials_and_no_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'secret'
            path.write_text(json.dumps(DATA))
            path.chmod(0o600)
            self.assertEqual(dns.credentials(path), DATA)
            path.chmod(0o644)
            with self.assertRaises(ValueError):
                dns.credentials(path)
            alias = path.with_name('alias')
            alias.symlink_to(path)
            with self.assertRaises(OSError):
                dns.credentials(alias)

    def test_rejects_wrong_zone_and_bad_challenge(self):
        for change in ({'CERTBOT_DOMAIN': 'other.in'}, {'CERTBOT_DOMAIN': 'watch.xdadwal.in'},
                       {'CERTBOT_VALIDATION': '../bad'}):
            with self.assertRaises(ValueError):
                dns.challenge(DATA, dict(ENV, **change))
        self.assertEqual(dns.challenge(DATA, dict(ENV, CERTBOT_DOMAIN='*.xdadwal.in'))[0], '_acme-challenge')

    def test_two_challenges_preserve_existing_txt_and_cleanup_only_owned_ids(self):
        api = FakeAPI()
        with tempfile.TemporaryDirectory() as directory, patch.object(dns, 'GoDaddy', return_value=api), patch.object(dns, 'wait_for_dns') as wait:
            state = Path(directory)
            first = dict(ENV, CERTBOT_REMAINING_CHALLENGES='1')
            second = dict(ENV, CERTBOT_VALIDATION='b' * 43)
            dns.run_hook('auth', DATA, state, first)
            wait.assert_not_called()
            dns.run_hook('auth', DATA, state, second)
            self.assertEqual(len(api.rows), 3)
            wait.assert_called_once()
            dns.run_hook('auth', DATA, state, second)
            self.assertEqual(len(api.rows), 3)
            dns.run_hook('cleanup', DATA, state, first)
            self.assertEqual({r['data'] for r in api.rows}, {'keep-me', 'b' * 43})
            dns.run_hook('cleanup', DATA, state, second)
            dns.run_hook('cleanup', DATA, state, second)
            self.assertEqual([r['recordId'] for r in api.rows], ['unrelated'])

    def test_preexisting_matching_value_is_never_deleted(self):
        api = FakeAPI()
        api.rows[0]['data'] = ENV['CERTBOT_VALIDATION']
        with tempfile.TemporaryDirectory() as directory, patch.object(dns, 'GoDaddy', return_value=api), patch.object(dns, 'wait_for_dns'):
            dns.run_hook('auth', DATA, Path(directory), ENV)
            dns.run_hook('cleanup', DATA, Path(directory), ENV)
        self.assertEqual(api.deleted, [])

    def test_propagation_timeout_does_not_report_success(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            (state / 'test.json').write_text(json.dumps({'ready_at': 0, 'value': 'a' * 43}))
            with patch.object(dns.time, 'time', side_effect=[0, 0, 0, 1000]), patch.object(dns.time, 'sleep'), patch.object(dns, 'visible', return_value=False):
                with self.assertRaisesRegex(RuntimeError, 'timed out'):
                    dns.wait_for_dns(DATA, state)

    def test_propagation_requires_both_resolvers_twice(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            (state / 'test.json').write_text(json.dumps({'ready_at': 0, 'value': 'a' * 43}))
            with patch.object(dns.time, 'time', return_value=0), patch.object(dns.time, 'sleep') as sleep, patch.object(dns, 'visible', return_value=True) as visible:
                dns.wait_for_dns(DATA, state)
                self.assertEqual(visible.call_count, 4)
                sleep.assert_called_once_with(30)

    def test_api_errors_hide_response_body_and_token(self):
        import io
        import urllib.error
        error = urllib.error.HTTPError('url', 403, 'denied', {}, io.BytesIO(DATA['token'].encode()))
        with patch.object(dns.urllib.request, 'urlopen', side_effect=error):
            with self.assertRaises(RuntimeError) as caught:
                dns.GoDaddy(DATA).records('_acme-challenge')
        self.assertIn('403', str(caught.exception))
        self.assertNotIn(DATA['token'], str(caught.exception))

    def test_pagination_keeps_all_challenge_values(self):
        api = dns.GoDaddy(DATA)
        rows = [{'type': 'TXT', 'name': '_acme-challenge'}] * 100
        with patch.object(api, 'request', side_effect=[{'items': rows}, {'items': rows[:1]}]) as request:
            self.assertEqual(len(api.records('_acme-challenge')), 101)
            self.assertIn('page=2', request.call_args.args[1])

    def test_installed_options_are_independent_of_checkout(self):
        self.assertNotIn(str(ROOT), ' '.join(dns_tls.options()))
        self.assertNotEqual(dns_tls.installed_paths(), dns_tls.installed_paths(True))

    def test_nginx_conversion_preserves_private_acl_and_localhost(self):
        c = config.load(ROOT / '.env.example')
        old = proxy.render(c, ROOT, https=True)
        old += '\nserver {\n server_name pihole.xdadwal.in;\n allow 192.168.1.0/24;\n deny all;\n ssl_certificate /old/cert;\n ssl_certificate_key /old/key;\n}\n'
        local = '\nserver {\n server_name localhost 127.0.0.1;\n ssl_certificate /local/cert;\n ssl_certificate_key /local/key;\n}\n'
        result = dns_tls.nginx_config(old + local, c, ROOT)
        self.assertIn(local, result)
        self.assertIn('deny all;', result)
        self.assertIn('allow 192.168.1.0/24;', result)
        self.assertNotIn('/old/cert', result)
        self.assertIn('/live/ohara-wildcard/fullchain.pem', result)

    def test_failed_reconfigure_preserves_routes_and_does_not_enable_timer(self):
        c = config.load(ROOT / '.env.example')
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'nginx.conf'
            old = proxy.render(c, ROOT, https=True)
            target.write_text(old)
            certdir = Path(directory) / 'cert'
            certdir.mkdir()
            (certdir / 'fullchain.pem').touch()
            with patch.object(dns_tls.proxy, 'TARGET', target), patch.object(dns_tls, 'CERT_DIR', certdir), patch.object(dns, 'credentials', return_value=DATA), patch.object(dns, 'GoDaddy'), patch.object(dns_tls, 'install'), patch.object(dns_tls, 'run', side_effect=RuntimeError('ACME failed')) as run:
                with self.assertRaisesRegex(RuntimeError, 'ACME failed'):
                    dns_tls.activate(c, ROOT, Path('ignored'), renewal_only=True, agree=True)
                self.assertEqual(target.read_text(), old)
                self.assertEqual(run.call_count, 1)
                self.assertEqual(run.call_args.args[0][:2], ['certbot', 'reconfigure'])

    def test_staging_uses_separate_hooks_and_never_applies_routes(self):
        c = config.load(ROOT / '.env.example')
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'nginx.conf'
            old = proxy.render(c, ROOT, https=False)
            target.write_text(old)
            with patch.object(dns_tls.proxy, 'TARGET', target), patch.object(dns, 'credentials', return_value=DATA), patch.object(dns, 'GoDaddy'), patch.object(dns_tls, 'install') as install, patch.object(dns_tls, 'run') as run, patch.object(proxy, 'apply_config') as apply:
                dns_tls.activate(c, ROOT, Path('ignored'), staging=True, agree=True)
                install.assert_called_once_with(ROOT, DATA, True)
                self.assertEqual(run.call_count, 1)
                args = run.call_args.args[0]
                self.assertIn('--staging', args)
                self.assertIn('/etc/letsencrypt-staging', args)
                self.assertIn('/usr/bin/python3 /usr/local/lib/ohara/dns_godaddy_staging.py auth', args)
                self.assertNotIn(DATA['token'], ' '.join(args))
                apply.assert_not_called()
                self.assertEqual(target.read_text(), old)

    def test_dns_activation_retires_only_known_copyparty_upstream(self):
        c = config.load(ROOT / '.env.example')
        c.update(HOMEPAGE_HOST='ohara.xdadwal.in', PORTFOLIO_PORT='8010')
        old = proxy.render(c, ROOT, https=True)
        retired = ('\nserver {\n    listen 443 ssl;\n    server_name files.xdadwal.in;\n'
                   '    ssl_certificate /old/cert;\n    ssl_certificate_key /old/key;\n'
                   '    location / {\n        proxy_pass http://127.0.0.1:3923;\n    }\n}\n')
        private = ('\nserver {\n    listen 443 ssl;\n    server_name admin.xdadwal.in;\n'
                   '    ssl_certificate /old/cert;\n    ssl_certificate_key /old/key;\n'
                   '    allow 192.168.1.0/24;\n    deny all;\n'
                   '    location / { proxy_pass http://127.0.0.1:7878; }\n}\n')
        result = dns_tls.nginx_config(old + retired + private, c, ROOT)
        self.assertNotIn('server_name files.xdadwal.in;', result)
        self.assertNotIn('127.0.0.1:3923', result)
        self.assertIn('127.0.0.1:8010', result)
        self.assertIn('server_name ohara.xdadwal.in;', result)
        self.assertIn('server_name admin.xdadwal.in;', result)
        self.assertIn('deny all;', result)

    def test_dns_rejects_nested_dashboard_before_api_or_host_changes(self):
        c = config.load(ROOT / '.env.example')
        c['HOMEPAGE_HOST'] = 'nested.ohara.xdadwal.in'
        with patch.object(dns, 'credentials', return_value=DATA), \
                patch.object(dns, 'GoDaddy') as api, patch.object(dns_tls, 'install') as install:
            with self.assertRaisesRegex(ValueError, 'direct subdomains'):
                dns_tls.activate(c, ROOT, Path('ignored'), staging=True, agree=True)
            api.assert_not_called()
            install.assert_not_called()

    def test_dns_migration_adds_music_without_replacing_existing_routes(self):
        c = config.load(ROOT/'.env.example')
        old = proxy.render(c, ROOT, https=True)
        old = old.replace('\n'+proxy.navidrome_config(c, ROOT), '')
        old = old.replace(c['NAVIDROME_HOST']+' ', '')
        old += '\nserver {\n server_name private.xdadwal.in;\n ssl_certificate /old/cert;\n ssl_certificate_key /old/key;\n deny all;\n}\n'
        result = dns_tls.nginx_config(old, c, ROOT)
        self.assertIn('server_name music.xdadwal.in;', result)
        self.assertIn('proxy_pass http://127.0.0.1:4533;', result)
        self.assertIn('deny all;', result)
        self.assertEqual(result.count('server_name music.xdadwal.in;'), 2)
        self.assertIn('listen 80;\n    server_name music.xdadwal.in;', result)
        self.assertIn('/live/ohara-wildcard/', result)

    def test_dns_migration_does_not_overwrite_existing_music_host(self):
        c = config.load(ROOT/'.env.example')
        old = proxy.render(c, ROOT, https=True)
        old = old.replace('\n'+proxy.navidrome_config(c, ROOT), '')
        with self.assertRaisesRegex(ValueError, 'inspect before DNS activation'):
            dns_tls.nginx_config(old, c, ROOT)
