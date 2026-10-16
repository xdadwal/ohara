from pathlib import Path
import os
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/lib'))
import config
import host
import credential_fixtures
import proxy

class HomepageTests(unittest.TestCase):
    def test_setup_seeds_homepage_and_preserves_edits(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            import shutil
            shutil.copytree(ROOT / 'configs', root / 'configs')
            c = config.load(ROOT / '.env.example')
            c.update(DATA_ROOT=str(root/'data'), FILES_ROOT=str(root/'files'), MEDIA_ROOT=str(root/'media'),
                     RUN_UID=str(os.getuid()), RUN_GID=str(os.getgid()))
            credential_fixtures.write(root)
            host.prepare_storage(c, root)
            settings = root/'data/homepage/settings.yaml'
            secrets = root/'local/homepage.env'
            self.assertTrue(settings.is_file())
            text = secrets.read_text()
            self.assertIn('HOMEPAGE_AUTH_ENABLED=true', text)
            self.assertIn('HOMEPAGE_AUTH_SECRET=', text)
            self.assertIn('HOMEPAGE_AUTH_PASSWORD=', text)
            settings.write_text('title: My edited homepage\n')
            host.prepare_storage(c, root)
            self.assertEqual(settings.read_text(), 'title: My edited homepage\n')
            self.assertEqual(text, secrets.read_text())
            self.assertEqual(secrets.stat().st_mode & 0o777, 0o600)

    def test_apex_is_proxied_and_login_rate_limited(self):
        rendered = proxy.render(config.load(ROOT / '.env.example'), ROOT, https=True)
        self.assertIn('proxy_pass http://127.0.0.1:3002;', rendered)
        self.assertIn('location = /api/auth/callback/credentials', rendered)
        self.assertIn('limit_req zone=ohara_homepage_login', rendered)
        self.assertNotIn('homepage has not been selected', rendered)

if __name__ == '__main__':
    unittest.main()

class HomepageRecoveryTests(unittest.TestCase):
    def test_invalid_inputs_do_not_create_or_change_storage(self):
        import shutil
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            shutil.copytree(ROOT/'configs', root/'configs')
            credential_fixtures.write(root)
            (root/'local/credentials').write_text('malformed\n')
            c = config.load(ROOT/'.env.example')
            c.update(DATA_ROOT=str(root/'data'), FILES_ROOT=str(root/'files'), MEDIA_ROOT=str(root/'media'))
            before = (root/'local/homepage.env').read_bytes()
            with self.assertRaises(ValueError):
                host.prepare_storage(c, root)
            self.assertFalse((root/'data').exists())
            self.assertEqual((root/'local/homepage.env').read_bytes(), before)

class HomepageExposureTests(unittest.TestCase):
    def test_model_rejects_disabled_login_or_wildcard_host(self):
        import json
        import runtime
        c = config.load(ROOT/'.env.example')
        for key,value in [('HOMEPAGE_AUTH_ENABLED','false'),('HOMEPAGE_ALLOWED_HOSTS','*')]:
            model = json.loads(runtime.compose(c,ROOT,['config','--no-env-resolution','--format','json'],capture=True))
            model['services']['homepage']['environment'][key] = value
            with self.assertRaisesRegex(ValueError,'Homepage'):
                runtime.validate_model(model,c)
