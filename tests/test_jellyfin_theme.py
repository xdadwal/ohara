import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts/lib'))
import config
import jellyfin_theme as theme


class ThemeTests(unittest.TestCase):
    def test_client_uses_jellyfin_authorization_header(self):
        class API:
            def __init__(self):self.headers={}
            def call(self,path):
                self.path=path
                return []
        api=API()
        with patch.object(theme.credentials,'read',return_value={'HOMEPAGE_VAR_JELLYFIN_API_KEY':'fixture-api-token'}), \
                patch.object(theme.media,'Client',return_value=api):
            self.assertIs(theme.client(ROOT),api)
        self.assertIn('Token="fixture-api-token"',api.headers['Authorization'])
        self.assertNotIn('X-Emby-Token',api.headers)
        self.assertEqual(api.path,'/Users')

    def test_css_keeps_existing_branding_and_install_is_idempotent(self):
        original = '.pageTitle { background-image: url(/my-logo.png); }'
        result = theme.css(original)
        self.assertIn(original, result)
        self.assertEqual(theme.css(result), result)
        self.assertEqual(theme.css(result, remove=True), original)

    def test_index_preserves_application_scripts_and_injects_once(self):
        original = '<html><body><script src="main.js"></script></body></html>'
        result = theme.inject(original)
        self.assertIn('<script src="main.js"></script>', result)
        self.assertEqual(result.count('data-abyss-spotlight'), 1)
        self.assertEqual(theme.inject(result), result)
        with self.assertRaises(ValueError):
            theme.inject('not a web index')

    def test_enabled_overlay_rejects_image_drift_and_changed_files(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)/'jellyfin-theme'
            (base/'ui').mkdir(parents=True)
            names = ['index.html']+['ui/'+name for name in theme.FILES]
            for name in names:
                (base/name).write_bytes(b'fixture')
            manifest = {'schema':1,'enabled':True,'image':config.images(ROOT/'versions.env')['JELLYFIN_IMAGE'],
                        'files':{name:hashlib.sha256(b'fixture').hexdigest() for name in names}}
            (base/'manifest.json').write_text(json.dumps(manifest))
            c = {'DATA_ROOT':directory}
            self.assertEqual(theme.override(c, ROOT), ['-f',str(ROOT/'compose.jellyfin-theme.yaml')])
            (base/'index.html').write_bytes(b'operator edit')
            with self.assertRaisesRegex(ValueError,'changed or are missing'):
                theme.override(c,ROOT)
            manifest['image'] = 'different-image'
            (base/'manifest.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError,'image changed'):
                theme.override(c,ROOT)

    def test_display_changes_preserve_home_order_and_private_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            user_id = 'a'*32
            old_branding = {'CustomCss':'.my-logo { color: red; }','LoginDisclaimer':'Keep this','SplashscreenEnabled':False}
            old_prefs = {'Id':'settings','CustomPrefs':{'homesection0':'smalllibrarytiles','appTheme':'blue','extra':'keep'}}
            writes = {}
            class API:
                def call(self,path,body=None):
                    if body is not None:
                        writes[path] = body
                        return
                    if path=='/Branding/Configuration':return copy.deepcopy(old_branding)
                    if path=='/Users':return [{'Id':user_id}]
                    return copy.deepcopy(old_prefs)
            backup = theme.apply(API(),root)
            branding = writes['/System/Configuration/Branding']
            self.assertEqual(branding['LoginDisclaimer'],'Keep this')
            self.assertFalse(branding['SplashscreenEnabled'])
            self.assertIn(old_branding['CustomCss'],branding['CustomCss'])
            prefs = next(v for k,v in writes.items() if k.startswith('/DisplayPreferences'))['CustomPrefs']
            self.assertEqual(prefs,{'homesection0':'smalllibrarytiles','appTheme':'dark','dashboardTheme':'dark','extra':'keep'})
            self.assertEqual(json.loads((backup/'branding.json').read_text()),old_branding)
            self.assertEqual((backup/'branding.json').stat().st_mode&0o777,0o600)
            self.assertEqual(backup.stat().st_mode&0o777,0o700)

    def test_api_failure_restores_branding_even_if_preference_restore_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            branding = {'CustomCss':'original logo CSS','LoginDisclaimer':'keep'}
            brand_writes = []
            class API:
                def call(self,path,body=None):
                    if body is not None:
                        if path.startswith('/DisplayPreferences'):
                            raise RuntimeError('fixture failure')
                        brand_writes.append(copy.deepcopy(body))
                        return
                    if path=='/Branding/Configuration':return copy.deepcopy(branding)
                    if path=='/Users':return [{'Id':'b'*32}]
                    return {'CustomPrefs':{'homesection0':'keep'}}
            with self.assertRaisesRegex(RuntimeError,'rollback incomplete'):
                theme.apply(API(),Path(directory))
            self.assertEqual(brand_writes[-1],branding)


if __name__=='__main__':
    unittest.main()
