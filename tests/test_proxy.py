from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/lib'))
import config
import proxy

class ProxyTests(unittest.TestCase):
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
