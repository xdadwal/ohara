import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('config', ROOT / 'scripts/lib/config.py')
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)

class ConfigurationTests(unittest.TestCase):
    def load(self, text):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '.env'
            path.write_text(text)
            return config.load(path)

    def test_example_valid(self):
        self.assertEqual(config.load(ROOT / '.env.example')['DOMAIN'], 'xdadwal.in')

    def test_unknown_duplicate_and_malformed_values(self):
        base = (ROOT / '.env.example').read_text()
        for suffix in ['UNKNOWN=x', 'DOMAIN=other.in', 'not an assignment']:
            with self.subTest(suffix=suffix), self.assertRaises(ValueError):
                self.load(base + '\n' + suffix)

    def test_values_cannot_execute_or_inject_config(self):
        base = (ROOT / '.env.example').read_text()
        with tempfile.TemporaryDirectory() as directory:
            sentinel = Path(directory) / 'executed'
            for value in [f'$(touch {sentinel})', '`id`', '/tmp/a;id', '/tmp/a/../b', '/']:
                with self.subTest(value=value), self.assertRaises(ValueError):
                    self.load(base.replace('DATA_ROOT=/ohara', 'DATA_ROOT=' + value))
            self.assertFalse(sentinel.exists())

    def test_error_does_not_echo_value(self):
        with self.assertRaises(ValueError) as caught:
            self.load('DOMAIN=private-secret-value;\n')
        self.assertNotIn('private-secret', str(caught.exception))

    def test_hostnames_are_distinct_and_under_domain(self):
        base = (ROOT / '.env.example').read_text()
        for replacement in ['speed.xdadwal.in', 'other.example.com']:
            with self.assertRaises(ValueError):
                self.load(base.replace('seerr.xdadwal.in', replacement))

    def test_exclusive_write_preserves_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config'
            self.assertTrue(config.create_file(path, 'first', 0o600))
            self.assertFalse(config.create_file(path, 'replacement', 0o600))
            self.assertEqual(path.read_text(), 'first')
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

if __name__ == '__main__':
    unittest.main()

class PermissionTests(unittest.TestCase):
    def test_access_is_checked_as_container_user(self):
        import os
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            path.chmod(0o700)
            self.assertTrue(config.directory_writable(path, os.getuid(), os.getgid()))
            self.assertFalse(config.directory_writable(path, os.getuid() + 1, os.getgid() + 1))
            path.chmod(0o777)
            self.assertTrue(config.directory_writable(path, os.getuid() + 1, os.getgid() + 1))
