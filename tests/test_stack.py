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
        self.assertEqual(set(model['services']), {'homepage', 'seerr', 'speedtest', 'jellyfin', 'radarr', 'sonarr', 'lidarr', 'bazarr', 'prowlarr', 'qbittorrent'})
        model['services']['seerr']['ports'][0]['host_ip'] = '0.0.0.0'
        with self.assertRaises(ValueError):
            runtime.validate_model(model, c)

    def test_new_media_services_are_private_nonroot_and_share_only_needed_media(self):
        c = config.load(ROOT / '.env.example')
        model = json.loads(runtime.compose(c, ROOT, ['config', '--no-env-resolution', '--format', 'json'], capture=True))
        for name, port in [('lidarr', 8686), ('bazarr', 6767)]:
            service = model['services'][name]
            self.assertEqual(service['user'], f"{c['RUN_UID']}:{c['RUN_GID']}")
            self.assertEqual(service['cap_drop'], ['ALL'])
            self.assertIn('no-new-privileges:true', service['security_opt'])
            self.assertEqual(service['tmpfs'], [f"/run:uid={c['RUN_UID']},gid={c['RUN_GID']},exec"])
            ports = service['ports']
            self.assertEqual([(p['host_ip'], int(p['published']), p['target']) for p in ports], [('127.0.0.1', port, port)])
            mounts = {v['target']: v for v in service['volumes']}
            target = '/data' if name == 'lidarr' else '/data/library'
            self.assertEqual(set(mounts), {'/config', target})
            self.assertEqual(mounts[target]['source'], c['MEDIA_ROOT'] + ('' if name == 'lidarr' else '/library'))
            self.assertFalse(mounts[target].get('read_only', False))
            for mount in mounts.values():
                # Compose versions can omit false/default fields in normalized JSON.
                self.assertFalse(mount.get('bind', {}).get('create_host_path', False))
            service['ports'][0]['host_ip'] = '0.0.0.0'
            with self.assertRaisesRegex(ValueError, 'unexpected port exposure'):
                runtime.validate_model(model, c)
            service['ports'][0]['host_ip'] = '127.0.0.1'

    def test_reject_extra_mount_and_privileged_service(self):
        c = config.load(ROOT / '.env.example')
        model = json.loads(runtime.compose(c, ROOT, ['config', '--no-env-resolution', '--format', 'json'], capture=True))
        model['services']['seerr']['privileged'] = True
        with self.assertRaises(ValueError):
            runtime.validate_model(model, c)

if __name__ == '__main__':
    unittest.main()
