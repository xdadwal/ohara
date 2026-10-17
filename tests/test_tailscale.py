from contextlib import ExitStack
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS / 'lib'))
spec = importlib.util.spec_from_file_location('tailscale_setup', SCRIPTS / 'tailscale_setup.py')
ts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ts)


class TailscaleTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / 'etc/apt/sources.list.d').mkdir(parents=True)
        (self.root / 'run/systemd/system').mkdir(parents=True)
        (self.root / 'etc/os-release').write_text('ID=ubuntu\nVERSION_ID="24.04"\n')
        stack = ExitStack()
        self.addCleanup(stack.close)
        self.run = stack.enter_context(patch.object(ts, 'run', return_value='arm64'))
        self.packages = stack.enter_context(patch.object(ts.host, 'ensure_packages'))
        self.installed = stack.enter_context(patch.object(ts.host, 'installed', return_value=False))
        stack.enter_context(patch.object(ts.shutil, 'which', return_value=None))

    def test_dry_run_writes_nothing(self):
        before = sorted(str(p.relative_to(self.root)) for p in self.root.rglob('*'))
        ts.install(True, self.root)
        self.assertEqual(before, sorted(str(p.relative_to(self.root)) for p in self.root.rglob('*')))
        self.packages.assert_not_called()
        self.run.assert_called_once_with(['dpkg', '--print-architecture'], capture=True)

    def test_existing_install_preserves_all_settings(self):
        self.installed.return_value = True
        ts.install(False, self.root)
        self.packages.assert_not_called()
        self.assertEqual(self.run.call_count, 1)
        self.assertFalse((self.root / 'usr').exists())

    def test_competing_source_rejected_before_mutation(self):
        (self.root / 'etc/apt/sources.list').write_text('deb https://pkgs.tailscale.com/stable/ubuntu noble main\n')
        with self.assertRaisesRegex(ValueError, 'Existing Tailscale apt source'):
            ts.install(False, self.root)
        self.packages.assert_not_called()

    def test_install_only_never_enrolls_or_changes_preferences(self):
        def execute(command, **kwargs):
            if command[0] == 'dpkg':
                return 'amd64'
            if command[0] == 'curl':
                Path(command[-1]).write_bytes(b'test signing key')
            return ''
        self.run.side_effect = execute
        ts.install(False, self.root)
        commands = [call.args[0] for call in self.run.call_args_list]
        self.assertEqual(commands[-1], ['systemctl', 'enable', '--now', 'tailscaled'])
        self.assertFalse(any(command[0] == 'tailscale' for command in commands))
        self.assertIn('noble main', (self.root / 'etc/apt/sources.list.d/ohara-tailscale.list').read_text())
        self.assertEqual((self.root / 'usr/share/keyrings/ohara-tailscale.gpg').stat().st_mode & 0o777, 0o644)

    def test_failed_key_download_leaves_no_repository(self):
        def execute(command, **kwargs):
            if command[0] == 'dpkg':
                return 'arm64'
            raise RuntimeError('download failed')
        self.run.side_effect = execute
        with self.assertRaisesRegex(RuntimeError, 'download failed'):
            ts.install(False, self.root)
        self.assertFalse((self.root / 'usr/share/keyrings/ohara-tailscale.gpg').exists())
        self.assertFalse((self.root / 'etc/apt/sources.list.d/ohara-tailscale.list').exists())

    def test_unsupported_os_rejected(self):
        (self.root / 'etc/os-release').write_text('ID=fedora\nVERSION_ID=44\n')
        with self.assertRaises(ValueError):
            ts.install(False, self.root)
        self.run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
