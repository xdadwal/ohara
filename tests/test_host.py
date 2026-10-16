from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/lib'))
import config
import host
import credential_fixtures

class HostTests(unittest.TestCase):
    def test_supported_and_unsupported_hosts(self):
        self.assertEqual(host.os_info('ID=ubuntu\nVERSION_ID="24.04"\n'), ('ubuntu', 'noble'))
        self.assertEqual(host.os_info('ID=debian\nVERSION_ID="13"\n'), ('debian', 'trixie'))
        for text in ['ID=arch\nVERSION_ID=1', 'ID=ubuntu\nVERSION_ID="22.04"']:
            with self.assertRaises(ValueError):
                host.os_info(text)

    def test_prepare_preserves_config_and_owner(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            c = config.load(ROOT / '.env.example')
            c.update(DATA_ROOT=str(root / 'data'), MEDIA_ROOT=str(root / 'media'),
                     RUN_UID=str(__import__('os').getuid()), RUN_GID=str(__import__('os').getgid()))
            credential_fixtures.write(root)
            host.prepare_storage(c, root)
            files = [root / 'local/homepage.env', root / 'local/media-credentials']
            before = [p.read_bytes() for p in files]
            mode = files[0].stat().st_mode
            host.prepare_storage(c, root)
            self.assertEqual(before, [p.read_bytes() for p in files])
            self.assertEqual(mode, files[0].stat().st_mode)

    def test_conflicting_docker_packages_are_not_removed(self):
        calls = []
        def fake(args, **kwargs):
            calls.append(args)
            if args[0] == 'dpkg-query':
                return 'install ok installed'
            return ''
        with patch.object(host, 'run', side_effect=fake), self.assertRaises(RuntimeError):
            host.reject_conflicts()
        self.assertFalse(any('remove' in a for a in calls))

    def test_package_failure_aborts(self):
        with patch.object(host, 'run', side_effect=RuntimeError('install failed')):
            with self.assertRaises(RuntimeError):
                host.ensure_packages(['nginx'])

    def test_existing_packages_do_not_reinstall(self):
        calls = []
        def fake(args, **kwargs):
            calls.append(args)
            return 'install ok installed'
        with patch.object(host, 'run', side_effect=fake):
            host.ensure_packages(['nginx', 'certbot'])
        self.assertTrue(all(c[0] == 'dpkg-query' for c in calls))

    def test_missing_privileges_fails_without_mutation(self):
        with patch.object(host.os, 'geteuid', return_value=1000), self.assertRaises(RuntimeError):
            host.require_root()

    def test_symlink_storage_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'linked'
            path.symlink_to(Path(directory), target_is_directory=True)
            with self.assertRaises(ValueError):
                host.ensure_directory(path, 1000, 1000)

if __name__ == '__main__':
    unittest.main()

class StorageSafetyTests(unittest.TestCase):
    def test_private_symlink_rejected_before_read(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / 'local').mkdir()
            target = root / 'target'
            target.write_text('private-value')
            (root / 'local/homepage.env').symlink_to(target)
            c = config.load(ROOT / '.env.example')
            c.update(DATA_ROOT=str(root/'data'), MEDIA_ROOT=str(root/'media'))
            with self.assertRaisesRegex(ValueError, 'Symlink private'):
                host.prepare_storage(c, root)
            self.assertEqual(target.read_text(), 'private-value')

class PreflightTests(unittest.TestCase):
    def test_missing_ss_does_not_block_fresh_host(self):
        from unittest.mock import MagicMock
        with patch('shutil.which', return_value=None), patch.object(host.socket, 'socket') as sock, patch.object(host, 'run') as runner:
            sock.return_value.__enter__.return_value = MagicMock()
            host.check_web_ports()
            runner.assert_not_called()
            self.assertEqual(sock.return_value.__enter__.return_value.bind.call_count, 2)

    def test_missing_storage_parent_is_not_silently_created(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory).resolve() / 'unmounted' / 'ohara'
            with self.assertRaisesRegex(ValueError, 'parent'):
                host.ensure_directory(missing, 1000, 1000)
            self.assertFalse(missing.parent.exists())
