from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts/lib'))
import bambuddy_proxy as p


class BambuddyProxyTests(unittest.TestCase):
    def test_fresh_render_is_lan_only_and_public_requires_explicit_choice(self):
        private=p.render(ROOT)
        self.assertEqual(private.count('if ($ohara_bambuddy_allowed = 0)'),2)
        self.assertIn('192.168.1.0/24 1;',private)
        public=p.render(ROOT,public=True)
        self.assertNotIn('return 403',public)
        self.assertIn('127.0.0.1:8008',public)
        self.assertIn('proxy_set_header X-Forwarded-For $remote_addr;',public)

    def test_public_activation_requires_native_auth_but_not_mfa(self):
        for state in [{},{'requires_setup':True,'auth_enabled':True},{'requires_setup':False,'auth_enabled':False}]:
            with patch.object(p.bambuddy,'client') as client,self.assertRaises(ValueError):
                client.return_value.call.return_value=state;p.require_accounts()
        with patch.object(p.bambuddy,'client') as client:
            client.return_value.call.return_value={'requires_setup':False,'auth_enabled':True}
            p.require_accounts()
            client.return_value.call.assert_called_once_with('/api/v1/auth/status')

    def test_legacy_migration_only_removes_bambuddy(self):
        core=(ROOT/'configs/nginx/deployed/ohara-lan.conf').read_text()
        old=core.replace('maintainerr.xdadwal.in;','maintainerr.xdadwal.in bambuddy.xdadwal.in;',1)
        old+='\nserver {\n    server_name bambuddy.xdadwal.in;\n    location / { proxy_pass http://127.0.0.1:8008; }\n}\n'
        self.assertEqual(p.without_legacy_route(old),core.strip())
        self.assertEqual(p.without_legacy_route(core),core.strip())

    def test_failed_reload_restores_both_files_and_removes_new_site(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);lan=base/'ohara-lan.conf';site=base/'ohara-bambuddy.conf';other=base/'other.conf'
            lan.write_text('old LAN');lan.chmod(0o640);other.write_text('unrelated')
            reloads=0
            def runner(args):
                nonlocal reloads
                if args==['systemctl','reload','nginx']:
                    reloads+=1
                    if reloads==1:raise RuntimeError('fixture reload failure')
            with self.assertRaisesRegex(RuntimeError,'previous route files restored'):
                p.deploy({lan:b'new LAN',site:b'new public'},base/'backup',runner=runner)
            self.assertEqual(lan.read_text(),'old LAN');self.assertEqual(lan.stat().st_mode&0o777,0o640)
            self.assertFalse(site.exists());self.assertEqual(other.read_text(),'unrelated')

    def test_symlink_site_is_rejected_before_writes(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);target=base/'real';target.write_text('keep');link=base/'site';link.symlink_to(target)
            with self.assertRaises(ValueError):p.deploy({link:b'change'},base/'backup',runner=lambda _:None)
            self.assertEqual(target.read_text(),'keep')
