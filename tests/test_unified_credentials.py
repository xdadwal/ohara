from pathlib import Path
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts/lib'))
import config
import credentials
import credential_fixtures
import credential_migration
import runtime


class UnifiedCredentialsTests(unittest.TestCase):
    def fixture(self, root):
        root.mkdir(exist_ok=True)
        (root/'.env').write_text((ROOT/'.env.example').read_text())
        credential_fixtures.write(root)

    def legacy(self, root):
        self.fixture(root)
        hp, media = credentials.load(root)
        (root/'.env').write_text((ROOT/'.env.example').read_text())
        for filename, values in [('homepage.env',hp),('media-credentials',media)]:
            path = root/'local'/filename
            path.write_text(''.join(k+'='+v+'\n' for k,v in values.items()))
            path.chmod(0o600)
        return hp, media

    def test_migration_preserves_values_backs_up_and_removes_old_inputs(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()/'repo'
            before = self.legacy(root)
            original = (root/'.env').read_bytes()
            backup = Path(d).resolve()/'backup'
            credential_migration.migrate(root, backup)
            self.assertEqual(credentials.load(root), before)
            self.assertEqual((backup/'deployment.env').read_bytes(), original)
            self.assertEqual((root/'.env').stat().st_mode & 0o777, 0o600)
            self.assertFalse((root/'local/homepage.env').exists())
            self.assertFalse((root/'local/media-credentials').exists())
            self.assertEqual(backup.stat().st_mode & 0o777, 0o700)
            self.assertIsNone(credential_migration.migrate(root))

    def historical_legacy(self, root):
        hp, media = self.legacy(root)
        added = {key for key in media if key.startswith(('LIDARR_', 'BAZARR_', 'NAVIDROME_'))}
        legacy = root/'local/media-credentials'
        legacy.write_text(''.join(key+'='+value+'\n' for key, value in media.items() if key not in added))
        return hp, media, added

    def test_historical_media_migration_uses_new_service_credentials_from_env(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()/'repo'
            hp, media, added = self.historical_legacy(root)
            with (root/'.env').open('a') as stream:
                stream.write(''.join(key+'='+media[key]+'\n' for key in sorted(added)))
            original = (root/'.env').read_bytes()
            legacy_original = (root/'local/media-credentials').read_bytes()
            backup = Path(d).resolve()/'backup'
            credential_migration.migrate(root, backup)
            self.assertEqual(credentials.load(root), (hp, media))
            self.assertEqual((backup/'deployment.env').read_bytes(), original)
            self.assertEqual((backup/'media-credentials').read_bytes(), legacy_original)
            self.assertFalse((root/'local/media-credentials').exists())
            self.assertFalse((root/'local/homepage.env').exists())

    def test_historical_media_missing_new_credentials_does_not_mutate_inputs(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()/'repo'
            self.historical_legacy(root)
            paths = [root/'.env', root/'local/homepage.env', root/'local/media-credentials']
            originals = {path: path.read_bytes() for path in paths}
            backup = Path(d).resolve()/'backup'
            with self.assertRaisesRegex(ValueError, 'missing required keys'):
                credential_migration.migrate(root, backup)
            for path, original in originals.items():
                self.assertEqual(path.read_bytes(), original)
            self.assertFalse(backup.exists())
            self.assertEqual(list(root.glob('.env-migrate-*')), [])

    def test_conflict_and_missing_input_preserve_originals(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()/'repo'
            self.legacy(root)
            with (root/'.env').open('a') as stream:
                stream.write('HOMEPAGE_AUTH_PASSWORD=Different password value\n')
            before = (root/'.env').read_bytes()
            with self.assertRaisesRegex(ValueError, 'Conflicting'):
                credential_migration.migrate(root, Path(d).resolve()/'backup')
            self.assertEqual((root/'.env').read_bytes(), before)
            (root/'local/media-credentials').unlink()
            with self.assertRaises(ValueError):
                credential_migration.migrate(root, Path(d).resolve()/'backup')
            self.assertEqual((root/'.env').read_bytes(), before)
            self.assertTrue((root/'local/homepage.env').exists())

    def test_config_never_returns_secrets_and_unknown_duplicates_fail(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            self.fixture(root)
            self.assertFalse(set(config.load(root/'.env')) & credentials.ALL_KEYS)
            self.assertIn('$ # = !', credentials.load(root)[0]['HOMEPAGE_AUTH_PASSWORD'])
            with (root/'.env').open('a') as stream:
                stream.write('HOMEPAGE_AUTH_PASSWORD=Duplicate password\n')
            with self.assertRaises(ValueError): config.load(root/'.env')
            with self.assertRaises(ValueError): credentials.load(root)

    def test_compose_allowlists_homepage_and_static_does_not_load_credentials(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            self.fixture(root)
            (root/'versions.env').write_text((ROOT/'versions.env').read_text())
            hp, media = credentials.load(root)
            c = config.load(root/'.env')
            with patch.dict(os.environ, {'RADARR_PASSWORD':'ambient-secret',
                                        'HOMEPAGE_AUTH_PASSWORD':'ambient-password',
                                        'HOMEPAGE_VAR_NAVIDROME_TOKEN':'ambient-token'}), patch.object(runtime, 'run') as run:
                runtime.compose(c, root, ['up','-d'], docker=['docker'])
                env = run.call_args.kwargs['env']
                self.assertEqual(env['HOMEPAGE_AUTH_PASSWORD'], hp['HOMEPAGE_AUTH_PASSWORD'])
                self.assertFalse(set(env) & set(media))
                for name in ('RADARR','SONARR','LIDARR'):
                    self.assertEqual(env['HOMEPAGE_VAR_'+name+'_API_KEY'],media[name+'_API_KEY'])
                self.assertEqual(env['HOMEPAGE_VAR_QBITTORRENT_PASSWORD'],media['QBITTORRENT_PASSWORD'])
                self.assertNotIn(media['NAVIDROME_PASSWORD'],env.values())
                self.assertNotIn(media['RADARR_PASSWORD'],env.values())
                self.assertEqual(env['HOMEPAGE_VAR_NAVIDROME_TOKEN'],
                                 credentials.navidrome_widget_environment(media)['HOMEPAGE_VAR_NAVIDROME_TOKEN'])
                self.assertNotIn(media['NAVIDROME_PASSWORD'], env.values())
                self.assertNotIn(str(root/'.env'), run.call_args.args[0])
                runtime.compose(c, root, ['config','--no-env-resolution'], docker=['docker'])
                self.assertFalse(set(run.call_args.kwargs['env']) & credentials.ALL_KEYS)
                self.assertFalse(set(run.call_args.kwargs['env']) & credentials.DERIVED_WIDGET_KEYS)
            (root/'.env').chmod(0o644)
            with self.assertRaisesRegex(ValueError, '0600'): credentials.load(root)
