import importlib.util
import json
from pathlib import Path
import sys
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/lib'))
import config
import runtime

class StackTests(unittest.TestCase):
    def test_static_check_without_private_configuration(self):
        c = config.load(ROOT / '.env.example')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ['compose.yaml', 'versions.env']:
                shutil.copy(ROOT / name, root / name)
            runtime.check(c, root, static=True)
            with self.assertRaisesRegex(ValueError, 'private config'):
                runtime.check(c, root)
            self.assertFalse((root / 'local').exists())

    def test_normalized_ports(self):
        c = config.load(ROOT / '.env.example')
        model = json.loads(runtime.compose(c, ROOT, ['config', '--no-env-resolution', '--format', 'json'], capture=True))
        runtime.validate_model(model, c)
        self.assertEqual(set(model['services']), {'homepage', 'seerr', 'copyparty', 'speedtest', 'jellyfin', 'radarr', 'sonarr', 'prowlarr', 'qbittorrent'})
        model['services']['seerr']['ports'][0]['host_ip'] = '0.0.0.0'
        with self.assertRaises(ValueError):
            runtime.validate_model(model, c)

    def test_reject_extra_mount_and_privileged_service(self):
        c = config.load(ROOT / '.env.example')
        model = json.loads(runtime.compose(c, ROOT, ['config', '--no-env-resolution', '--format', 'json'], capture=True))
        model['services']['seerr']['privileged'] = True
        with self.assertRaises(ValueError):
            runtime.validate_model(model, c)

if __name__ == '__main__':
    unittest.main()
