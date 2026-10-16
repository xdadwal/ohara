from pathlib import Path
import json
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts/lib'))
import config
import credentials
import runtime

class DnsRemovalTests(unittest.TestCase):
    def test_no_dns_service_or_ports(self):
        c = config.load(ROOT/'.env.example')
        model = json.loads(runtime.compose(c, ROOT, ['config','--no-env-resolution','--format','json'], capture=True))
        self.assertTrue('pihole' not in model['services'], 'Removed DNS service is still configured')
        self.assertEqual(len(model['services']), 8)
        for service in model['services'].values():
            for port in service.get('ports', []):
                self.assertNotIn(int(port['published']), (53,8888))

    def test_legacy_dns_inputs_are_optional_ignored_and_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            path = root/'.env'
            path.write_text((ROOT/'.env.example').read_text()+'\nLAN_IP=192.168.1.111\n')
            self.assertNotIn('LAN_IP', config.load(path))
            (root/'local').mkdir()
            user_file = root/'local/credentials'
            original = 'COPYPARTY_PASSWORD=User-supplied-password-123!\nPIHOLE_PASSWORD=\n'
            user_file.write_text(original)
            user_file.chmod(0o600)
            # Retired fields do not require keeping or choosing a DNS password.
            import credential_fixtures
            credential_fixtures.write(root)
            self.assertEqual(len(credentials.load(root)), 2)
            self.assertEqual(user_file.read_text(), original)

    def test_status_checks_only_remaining_services(self):
        from unittest.mock import patch
        import contextlib
        import io
        output = io.StringIO()
        with patch.object(runtime, 'compose', return_value='[]'), contextlib.redirect_stdout(output):
            self.assertEqual(runtime.status(config.load(ROOT/'.env.example'), ROOT), 1)
        self.assertEqual(output.getvalue().count('container=stopped/missing'), 8)
        self.assertNotIn('pihole', output.getvalue())
