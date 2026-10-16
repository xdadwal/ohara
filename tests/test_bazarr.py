from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/lib'))
import bazarr


class BazarrTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.data = Path(self.temporary.name)
        self.directory = self.data / 'bazarr/config'
        self.directory.mkdir(parents=True)
        self.values = {'BAZARR_API_KEY': 'true', 'BAZARR_PASSWORD': 'password',
                       'SONARR_API_KEY': 'sonarr-key', 'RADARR_API_KEY': 'radarr-key'}
        self.create = Mock()

    def prepare(self):
        bazarr.prepare(self.data, self.values, self.create, 123, 456)

    def test_private_auth_and_shared_library_integrations(self):
        self.prepare()
        path, content, uid, gid, mode = self.create.call_args.args
        self.assertEqual((path, uid, gid, mode),
                         (self.directory / 'config.yaml', 123, 456, 0o600))
        settings = json.loads(content)
        self.assertEqual(settings['auth'], {'apikey': 'true', 'type': 'form',
                         'username': 'admin', 'password': '5f4dcc3b5aa765d61d8327deb882cf99'})
        self.assertNotIn('"password": "password"', content)
        for name, port in [('sonarr', 8989), ('radarr', 7878)]:
            self.assertEqual(settings[name], {'ip': name, 'port': port, 'ssl': False,
                             'base_url': '/', 'apikey': name + '-key'})
        self.assertEqual(settings['general'], {'use_sonarr': True, 'use_radarr': True,
                         'path_mappings': [], 'path_mappings_movie': [], 'enabled_providers': []})

    def test_quotes_newlines_and_unicode_are_preserved(self):
        self.values['SONARR_API_KEY'] = '"quoted"\\newline\n雪: true'
        self.prepare()
        settings = json.loads(self.create.call_args.args[1])
        self.assertEqual(settings['sonarr']['apikey'], self.values['SONARR_API_KEY'])

    def test_existing_yaml_and_legacy_ini_are_untouched(self):
        for name in ['config.yaml', 'config.ini']:
            with self.subTest(name=name):
                path = self.directory / name
                path.write_bytes(b'existing user settings\n')
                self.prepare()
                self.create.assert_not_called()
                self.assertEqual(path.read_bytes(), b'existing user settings\n')
                path.unlink()

    def test_symlink_configuration_is_rejected(self):
        for name in ['config.yaml', 'config.ini']:
            with self.subTest(name=name):
                path = self.directory / name
                path.symlink_to(self.data / 'missing-target')
                with self.assertRaisesRegex(ValueError, 'Symlink Bazarr'):
                    self.prepare()
                self.create.assert_not_called()
                path.unlink()


if __name__ == '__main__':
    unittest.main()

class BazarrLegacyStartupTests(unittest.TestCase):
    def test_runtime_check_allows_preserved_ini_to_reach_application_migration(self):
        import os
        import shutil
        import config
        import credential_fixtures
        import host
        import runtime
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            shutil.copytree(ROOT/'configs', root/'configs')
            for name in ['compose.yaml', 'versions.env']:
                shutil.copy(ROOT/name, root/name)
            credential_fixtures.write(root)
            c = config.load(ROOT/'.env.example')
            c.update(DATA_ROOT=str(root/'data'), MEDIA_ROOT=str(root/'media'),
                     RUN_UID=str(os.getuid()), RUN_GID=str(os.getgid()))
            host.prepare_storage(c, root)
            (root/'data/seerr').chmod(0o777)
            yaml = root/'data/bazarr/config/config.yaml'
            legacy = yaml.with_suffix('.ini')
            yaml.rename(legacy)
            before = legacy.read_bytes()
            runtime.check(c, root)
            self.assertEqual(legacy.read_bytes(), before)
            self.assertFalse(yaml.exists())
