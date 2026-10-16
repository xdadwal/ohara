from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts/lib'))
import config
import host

class UserCredentialTests(unittest.TestCase):
    def test_shorter_web_passwords_are_accepted_without_weakening_media_or_secrets(self):
        import credentials
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'credentials'
            for key, value, accepted in [('COPYPARTY_PASSWORD', 'chosen08', True),
                                         ('HOMEPAGE_AUTH_PASSWORD', 'chosen08', True),
                                         ('COPYPARTY_PASSWORD', 'short07', False),
                                         ('JELLYFIN_PASSWORD', 'chosen08', False),
                                         ('HOMEPAGE_AUTH_SECRET', 'chosen08', False)]:
                path.write_text(key+'='+value+'\n')
                path.chmod(0o600)
                if accepted:
                    self.assertEqual(credentials.read(path, {key})[key], value)
                else:
                    with self.assertRaises(ValueError):
                        credentials.read(path, {key})

    def test_missing_user_files_fail_before_storage_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            c = config.load(ROOT/'.env.example')
            c.update(DATA_ROOT=str(root/'data'), FILES_ROOT=str(root/'files'), MEDIA_ROOT=str(root/'media'))
            with self.assertRaisesRegex(ValueError, 'user-created|user-supplied'):
                host.prepare_storage(c, root)
            self.assertFalse((root/'data').exists())
            self.assertFalse((root/'local').exists())

    def test_literals_and_private_permissions(self):
        import credentials
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve()/'credentials'
            password = 'User supplied $value#with=punctuation!'
            path.write_text('PASSWORD='+password+'\n')
            path.chmod(0o600)
            self.assertEqual(credentials.read(path, {'PASSWORD'})['PASSWORD'], password)
            path.chmod(0o644)
            with self.assertRaisesRegex(ValueError, '0600'):
                credentials.read(path, {'PASSWORD'})

    def test_missing_and_invalid_values_are_not_echoed(self):
        import credentials
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve()/'credentials'
            path.write_text('PASSWORD=short-private\n')
            path.chmod(0o600)
            with self.assertRaises(ValueError) as caught:
                credentials.read(path, {'PASSWORD'})
            self.assertNotIn('short-private', str(caught.exception))

    def test_invalid_inputs_block_package_and_proxy_changes(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            with patch.object(host.os, 'geteuid', return_value=0), \
                    patch.object(host, 'preflight') as preflight, \
                    patch.object(host, 'ensure_packages') as packages:
                with self.assertRaises(ValueError):
                    host.prepare({}, root)
                preflight.assert_not_called()
                packages.assert_not_called()

    def test_blank_templates_and_symlinks_cannot_be_used(self):
        import credentials
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            path = root/'input'
            path.write_text((ROOT/'configs/credentials/credentials.example').read_text())
            path.chmod(0o600)
            with self.assertRaises(ValueError):
                credentials.read(path, credentials.BASE_KEYS)
            link = root/'link'
            link.symlink_to(path)
            with self.assertRaisesRegex(ValueError, 'Symlink'):
                credentials.read(link, credentials.BASE_KEYS)

    def test_missing_service_config_blocks_upstream_credential_fallback(self):
        import credential_fixtures
        import runtime
        import shutil
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            shutil.copytree(ROOT/'configs', root/'configs')
            for name in ['compose.yaml','versions.env']:
                shutil.copy(ROOT/name, root/name)
            credential_fixtures.write(root)
            c = config.load(ROOT/'.env.example')
            c.update(DATA_ROOT=str(root/'data'), FILES_ROOT=str(root/'files'), MEDIA_ROOT=str(root/'media'))
            host.prepare_storage(c, root)
            (root/'data/qbittorrent/qBittorrent/qBittorrent.conf').unlink()
            with self.assertRaisesRegex(ValueError, 'qBittorrent.conf'):
                runtime.check(c, root)
