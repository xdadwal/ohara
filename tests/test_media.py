from pathlib import Path
import os
import sys
import tempfile
import unittest
from unittest.mock import patch
import copy
import json

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/lib'))
import config
import host
import credential_fixtures
import media

class MediaTests(unittest.TestCase):
    def test_storage_policy_preserves_torrents_and_custom_settings_on_rerun(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            credential_fixtures.write(root)
            preferences = {'auto_tmm_enabled': False, 'unrelated': 'preserved'}
            categories = {'movies': {'savePath': '/data/downloads/complete/movies'}}
            settings = {'radarr': {'copyUsingHardlinks': False, 'recycleBin': '', 'custom': 42},
                        'sonarr': {'copyUsingHardlinks': True, 'recycleBin': '/data/custom-bin',
                                   'recycleBinCleanupDays': 30}}
            calls = []
            cleanup = {'radarr': True, 'sonarr': True}
            class Client:
                def __init__(self, url, key=None):
                    self.headers = {}
                    self.name = next(n for n, p in [('radarr','7878'), ('sonarr','8989'), ('qbittorrent','8081')] if p in url)
                def call(self, path, body=None, method=None, form=False):
                    calls.append(path)
                    if path.endswith('/preferences'): return copy.deepcopy(preferences)
                    if path.endswith('/setPreferences'):
                        # A zero seed limit must never be enabled while Arr can
                        # delete a completed torrent and its original files.
                        if any(cleanup.values()):
                            raise AssertionError('Cleanup must be disabled before seeding limits')
                        preferences.update(json.loads(body['json']))
                    if path.endswith('/categories'): return copy.deepcopy(categories)
                    if path == '/api/v3/downloadclient':
                        return [{'id':1, 'name':'Ohara qBittorrent', 'removeCompletedDownloads':cleanup[self.name]}]
                    if path == '/api/v3/downloadclient/1': cleanup[self.name] = body['removeCompletedDownloads']
                    if path.endswith('/createCategory'): categories[body['category']] = {'savePath': body['savePath']}
                    if path.endswith('/mediamanagement'):
                        if body is not None: settings[self.name] = copy.deepcopy(body)
                        return copy.deepcopy(settings[self.name])
            with patch.object(media, 'Client', Client):
                media.configure_storage(root)
                media.configure_storage(root)
            self.assertTrue(preferences['auto_tmm_enabled'])
            self.assertTrue(preferences['max_ratio_enabled'])
            self.assertEqual(preferences['max_ratio'], 0)
            self.assertEqual(preferences['max_ratio_act'], 0)
            self.assertTrue(preferences['max_seeding_time_enabled'])
            self.assertEqual(preferences['max_seeding_time'], 0)
            self.assertEqual(preferences['unrelated'], 'preserved')
            self.assertEqual(settings['radarr']['recycleBin'], '/data/recycle-bin/movies')
            self.assertEqual(settings['radarr']['recycleBinCleanupDays'], 7)
            self.assertEqual(settings['radarr']['custom'], 42)
            self.assertTrue(settings['radarr']['copyUsingHardlinks'])
            self.assertEqual(settings['sonarr']['recycleBin'], '/data/custom-bin')
            self.assertEqual(settings['sonarr']['recycleBinCleanupDays'], 30)
            self.assertEqual(calls.count('/api/v2/app/setPreferences'), 1)
            self.assertEqual(calls.count('/api/v2/torrents/createCategory'), 1)
            self.assertFalse(any('/torrents/set' in p for p in calls))
            categories['movies']['savePath'] = '/data/custom-downloads'
            with patch.object(media, 'Client', Client), self.assertRaisesRegex(ValueError, 'review relocation'):
                media.configure_storage(root)

    def test_old_configuration_has_media_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '.env'
            path.write_text('\n'.join(line for line in (ROOT/'.env.example').read_text().splitlines()
                                     if not line.startswith(('MEDIA_ROOT=', 'JELLYFIN_HOST='))))
            c = config.load(path)
            self.assertEqual(c['MEDIA_ROOT'], c['DATA_ROOT'] + '/media')
            self.assertEqual(c['JELLYFIN_HOST'], 'tv.xdadwal.in')

    def test_media_credentials_and_existing_configuration_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            import shutil
            shutil.copytree(ROOT/'configs', root/'configs')
            c = config.load(ROOT/'.env.example')
            c.update(DATA_ROOT=str(root/'data'), MEDIA_ROOT=str(root/'media'),
                     RUN_UID=str(os.getuid()), RUN_GID=str(os.getgid()))
            credential_fixtures.write(root)
            host.prepare_storage(c, root)
            credentials = root/'.env'
            before = credentials.read_bytes()
            self.assertEqual(credentials.stat().st_mode & 0o777, 0o600)
            self.assertTrue((root/'media/library/movies').is_dir())
            self.assertTrue((root/'media/library/tv').is_dir())
            self.assertTrue((root/'media/recycle-bin/movies').is_dir())
            self.assertTrue((root/'media/recycle-bin/tv').is_dir())
            arr = root/'data/radarr/config.xml'
            arr.write_text(arr.read_text() + '\n<!-- operator edit -->\n')
            edited = arr.read_bytes()
            host.prepare_storage(c, root)
            self.assertEqual(credentials.read_bytes(), before)
            self.assertEqual(arr.read_bytes(), edited)

    def test_public_media_admin_exposure_is_rejected(self):
        import json
        import runtime
        c = config.load(ROOT/'.env.example')
        model = json.loads(runtime.compose(c, ROOT, ['config', '--no-env-resolution', '--format', 'json'], capture=True))
        for name in ['radarr', 'sonarr', 'prowlarr', 'qbittorrent', 'jellyfin']:
            original = model['services'][name]['ports'][0]['host_ip']
            model['services'][name]['ports'][0]['host_ip'] = '0.0.0.0'
            with self.subTest(service=name), self.assertRaises(ValueError):
                runtime.validate_model(model, c)
            model['services'][name]['ports'][0]['host_ip'] = original
        for name in ['jellyfin', 'radarr', 'sonarr', 'prowlarr', 'qbittorrent']:
            self.assertEqual(model['services'][name].get('user'), c['RUN_UID']+':'+c['RUN_GID'])
        library = next(v for v in model['services']['jellyfin']['volumes'] if v['target']=='/media')
        self.assertFalse(library.get('read_only', False))
        for name in ['radarr', 'sonarr', 'qbittorrent']:
            self.assertEqual([v['source'] for v in model['services'][name]['volumes'] if v['target']=='/data'], [c['MEDIA_ROOT']])

    def test_new_hostname_is_in_certificate_and_proxy(self):
        import proxy
        c = config.load(ROOT/'.env.example')
        rendered = proxy.render(c, ROOT, https=True)
        self.assertIn(c['JELLYFIN_HOST'], proxy.configured_names(rendered))
        self.assertIn('proxy_pass http://127.0.0.1:8096;', rendered)
        for port in [7878,8989,9696,8081]:
            self.assertNotIn('proxy_pass http://127.0.0.1:'+str(port), rendered)

    def test_music_storage_and_private_lidarr_config_are_preserved(self):
        import shutil
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            shutil.copytree(ROOT/'configs', root/'configs')
            c = config.load(ROOT/'.env.example')
            c.update(DATA_ROOT=str(root/'data'), MEDIA_ROOT=str(root/'media'),
                     RUN_UID=str(os.getuid()), RUN_GID=str(os.getgid()))
            credential_fixtures.write(root)
            host.prepare_storage(c, root)
            self.assertTrue((root/'media/library/music').is_dir())
            self.assertTrue((root/'media/downloads/complete/music').is_dir())
            path = root/'data/lidarr/config.xml'
            self.assertIn('<AuthenticationMethod>Forms</AuthenticationMethod>', path.read_text())
            path.write_text(path.read_text()+'\n<!-- keep operator edits -->\n')
            before = path.read_bytes()
            host.prepare_storage(c, root)
            self.assertEqual(path.read_bytes(), before)

    def test_missing_added_service_credentials_fail_before_storage_changes(self):
        import shutil
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            shutil.copytree(ROOT/'configs', root/'configs')
            c = config.load(ROOT/'.env.example')
            c.update(DATA_ROOT=str(root/'data'), MEDIA_ROOT=str(root/'media'))
            credential_fixtures.write(root)
            path = root/'.env'
            path.write_text('\n'.join(line for line in path.read_text().splitlines()
                                      if not line.startswith('LIDARR_API_KEY='))+'\n')
            with self.assertRaisesRegex(ValueError, 'LIDARR_API_KEY'):
                host.prepare_storage(c, root)
            self.assertFalse((root/'data').exists())
