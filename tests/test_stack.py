import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/lib'))
import config
import runtime

class StackTests(unittest.TestCase):
    def test_normalized_ports(self):
        c = config.load(ROOT / '.env.example')
        model = json.loads(runtime.compose(c, ROOT, ['config', '--no-env-resolution', '--format', 'json'], capture=True))
        runtime.validate_model(model, c)
        self.assertEqual(set(model['services']), {'seerr', 'copyparty', 'pihole', 'speedtest'})
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
