from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/lib'))
import config
import proxy
import re

class ProxyTests(unittest.TestCase):
    def test_reusable_routes_match_stable_host_policy(self):
        c = config.load(ROOT/'.env.example')
        c.update(HOMEPAGE_HOST='ohara.xdadwal.in', PORTFOLIO_PORT='8010')
        rendered = proxy.render(c, ROOT, https=True, acme_names={'files.xdadwal.in'})
        deployed = (ROOT/'configs/nginx/deployed/ohara.conf').read_text()
        # New music route/log protection intentionally extend the deployed baseline.
        self.assertIn('listen [::]:443 ssl;', proxy.navidrome_config(c, ROOT))
        self.assertIn('access_log off;\n    error_log /dev/null;', rendered)
        rendered = rendered.replace('\n'+proxy.navidrome_config(c, ROOT), '')
        rendered = rendered.replace(c['NAVIDROME_HOST']+' ', '')
        rendered = rendered.replace('    access_log off;\n    error_log /dev/null;\n', '')
        def normalize(text):
            # Localhost uses certificates that fresh hosts do not yet have.
            # Ignore only these two explicit host-specific blocks and harmless
            # whitespace/comments/certificate-lineage/host-order differences.
            text = re.sub(r'(?ms)^server \{\n(?:(?!^\}).)*server_name localhost 127\.0\.0\.1;(?:(?!^\}).)*^\}\n?', '', text)
            text = text.replace('/live/ohara-wildcard/', '/live/ohara/')
            text = re.sub(r'server_name ([^;]+);', lambda m:'server_name '+' '.join(sorted(m[1].split()))+';',text)
            text = re.sub(r'(?m)^\s*#.*$', '', text)
            return re.sub(r'\s+', ' ', text).strip()
        self.assertEqual(normalize(rendered), normalize(deployed))
        self.assertEqual(deployed.count('server_name localhost 127.0.0.1;'), 2)
        self.assertIn('return 302 https://xdadwal.in$request_uri;', deployed)
        probe = (ROOT/'configs/nginx/deployed/ohara-public-ip-test.conf').read_text()
        self.assertIn('server_name 45.120.160.21;', probe)
        self.assertNotIn('proxy_pass', probe)

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
        addition = candidate[len(old):]
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
            with patch.object(proxy, 'TARGET', target), patch.object(proxy, 'apply_config', side_effect=apply), patch.object(proxy, 'run', side_effect=failed_issuance):
                with self.assertRaisesRegex(RuntimeError, 'ACME failed'):
                    proxy.activate(c, ROOT, accounts_ready=True, agree=True)
            self.assertEqual(target.read_text(), old)
