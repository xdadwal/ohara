from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/lib'))
import config
import credential_fixtures
import credentials
import host
import media


def write_env(root, drop=(), **changes):
    path = root / '.env'
    lines = [
        l
        for l in path.read_text().splitlines()
        if l.partition('=')[0] not in set(drop) | set(changes)
    ]
    lines += [f'{k}={v}' for k, v in changes.items()]
    path.write_text('\n'.join(lines) + '\n')
    path.chmod(0o600)


class SetupOnlyPasswordTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        credential_fixtures.write(self.root)

    def test_runtime_commands_ignore_setup_only_passwords(self):
        write_env(self.root, drop=credentials.SETUP_ONLY_KEYS)
        _, values = credentials.load(self.root)
        self.assertFalse(credentials.SETUP_ONLY_KEYS & set(values))

    def test_existing_logins_may_be_short_but_not_empty(self):
        write_env(
            self.root, QBITTORRENT_PASSWORD='short', NAVIDROME_PASSWORD='tiny', RADARR_PASSWORD='x'
        )
        _, values = credentials.load(self.root)
        self.assertEqual(values['QBITTORRENT_PASSWORD'], 'short')
        for key in ('QBITTORRENT_PASSWORD', 'NAVIDROME_PASSWORD'):
            original = (self.root / '.env').read_text()
            write_env(self.root, drop=[key])
            with self.assertRaisesRegex(ValueError, key):
                credentials.load(self.root)
            write_env(self.root, **{key: ''})
            with self.assertRaisesRegex(ValueError, key):
                credentials.load(self.root)
            (self.root / '.env').write_text(original)

    def test_other_inputs_keep_their_rules(self):
        for key, value in [
            ('HOMEPAGE_AUTH_SECRET', 'short'),
            ('HOMEPAGE_AUTH_PASSWORD', 'short'),
            ('RADARR_API_KEY', 'abc'),
        ]:
            original = (self.root / '.env').read_text()
            write_env(self.root, **{key: value})
            with self.assertRaisesRegex(ValueError, key):
                credentials.load(self.root)
            (self.root / '.env').write_text(original)

    def storage(self):
        shutil.copytree(ROOT / 'configs', self.root / 'configs')
        c = config.load(ROOT / '.env.example')
        c.update(DATA_ROOT=str(self.root / 'data'), MEDIA_ROOT=str(self.root / 'media'))
        return c

    def test_fresh_storage_needs_new_logins_before_creating_anything(self):
        c = self.storage()
        write_env(self.root, drop=['BAZARR_PASSWORD'])
        with self.assertRaisesRegex(ValueError, 'First Bazarr setup needs BAZARR_PASSWORD'):
            host.prepare_storage(c, self.root)
        self.assertFalse((self.root / 'data').exists())
        write_env(
            self.root, BAZARR_PASSWORD='Disposable test only bazarr', QBITTORRENT_PASSWORD='short'
        )
        with self.assertRaisesRegex(
            ValueError, 'QBITTORRENT_PASSWORD: First qBittorrent setup creates'
        ):
            host.prepare_storage(c, self.root)
        self.assertFalse((self.root / 'data').exists())

    def test_existing_storage_needs_no_setup_only_passwords(self):
        c = self.storage()
        for path in ('bazarr/config/config.yaml', 'qbittorrent/qBittorrent/qBittorrent.conf'):
            target = Path(c['DATA_ROOT']) / path
            target.parent.mkdir(parents=True)
            target.write_text('existing\n')
        write_env(self.root, drop=['BAZARR_PASSWORD'], QBITTORRENT_PASSWORD='short')
        with patch('media.prepare') as prepare:
            host.prepare_storage(c, self.root)
        prepare.assert_called_once()
        self.assertEqual(
            (Path(c['DATA_ROOT']) / 'bazarr/config/config.yaml').read_text(), 'existing\n'
        )

    def test_owner_setup_requires_only_logins_it_creates(self):
        c = config.load(ROOT / '.env.example')
        (self.root / 'local').mkdir(exist_ok=True)
        write_env(self.root, drop=credentials.SETUP_ONLY_KEYS)
        urls = {
            n: 'http://127.0.0.1:9'
            for n in (
                'radarr',
                'sonarr',
                'prowlarr',
                'lidarr',
                'qbittorrent',
                'jellyfin',
                'seerr',
                'navidrome',
            )
        }
        with patch.object(media, '_jellyfin_wizard_done', lambda url: True):
            with self.assertRaisesRegex(ValueError, 'LIDARR_PASSWORD in .env'):
                media.connect(c, self.root, 'owner@example.com', urls=urls)
            (self.root / 'local/media-state.json').write_text(
                '{"radarr-auth": true, "sonarr-auth": true, "prowlarr-auth": true, "lidarr-auth": true}'
            )
            with self.assertRaisesRegex(ValueError, 'Owner media setup needs JELLYFIN_PASSWORD'):
                media.connect(c, self.root, 'owner@example.com', urls=urls)
        write_env(self.root, JELLYFIN_PASSWORD='short')
        with (
            patch.object(media, '_jellyfin_wizard_done', lambda url: False),
            self.assertRaisesRegex(ValueError, 'JELLYFIN_PASSWORD: Owner media setup creates'),
        ):
            media.connect(c, self.root, 'owner@example.com', urls=urls)


if __name__ == '__main__':
    unittest.main()
