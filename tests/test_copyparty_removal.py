from pathlib import Path
import json
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts/lib'))
import config
import credentials
import credential_fixtures
import host
import proxy
import runtime

class CopypartyRemovalTests(unittest.TestCase):
    def test_only_eleven_apps_and_five_public_hostnames(self):
        c = config.load(ROOT/'.env.example')
        model = json.loads(runtime.compose(c, ROOT, ['config','--no-env-resolution','--format','json'], capture=True))
        self.assertTrue('copyparty' not in model['services'], 'Removed file-sharing service is still configured')
        self.assertEqual(len(model['services']), 11)
        text = proxy.render(c, ROOT, https=True)
        self.assertNotIn('3923', text)
        self.assertNotIn('files.xdadwal.in', text)
        self.assertEqual(len(proxy.configured_names(text)), 5)

    def test_retired_files_settings_and_credentials_are_not_consumed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            path = root/'.env'
            path.write_text((ROOT/'.env.example').read_text()+'\nFILES_ROOT=/old/share\nFILES_HOST=files.xdadwal.in\n')
            c = config.load(path)
            self.assertNotIn('FILES_HOST', c)
            self.assertNotIn('FILES_ROOT', c)
            credential_fixtures.write(root)
            old = root/'local/credentials'
            old.write_text('retired file deliberately not parsed\n')
            before = old.read_bytes()
            self.assertEqual(len(credentials.load(root)), 2)
            c.update(DATA_ROOT=str(root/'data'), MEDIA_ROOT=str(root/'media'))
            host.prepare_storage(c, root)
            self.assertFalse((root/'local/copyparty.conf').exists())
            self.assertFalse((root/'data/copyparty').exists())
            self.assertEqual(old.read_bytes(), before)

    def test_retired_certificate_name_has_only_an_acme_route(self):
        c = config.load(ROOT/'.env.example')
        text = proxy.render(c, ROOT, https=True, acme_names={'files.xdadwal.in'})
        self.assertIn('files.xdadwal.in', proxy.configured_names(text))
        self.assertNotIn('server_name files.xdadwal.in;', text)
        self.assertNotIn('3923', text)
        self.assertIn('server_name files.xdadwal.in jellyfin.xdadwal.in music.xdadwal.in seerr.xdadwal.in speed.xdadwal.in xdadwal.in;', text)
