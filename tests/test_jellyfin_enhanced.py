import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts/lib'))
import config
import jellyfin_enhanced as enhanced


class EnhancedTests(unittest.TestCase):
    def profile(self):
        return json.loads((ROOT/'configs/jellyfin/enhanced-qol.json').read_text())

    def settings(self):
        return {**{key:False for key in self.profile()['server']},
                'JellyseerrUrls':'','JellyseerrUrlMappings':'',
                'SonarrInstances':'[]','RadarrInstances':'[]',
                'AutoMovieRequestEnabled':True,'AnalyticsEnabled':False,'DefaultSubtitleFont':7,
                'BookmarksUsePluginPages':True,'Shortcuts':[{'Key':'custom'}]}

    def values(self):
        return {'HOMEPAGE_VAR_SEERR_API_KEY':'fixture-seerr-key',
                'SONARR_API_KEY':'fixture-sonarr-key','RADARR_API_KEY':'fixture-radarr-key'}

    def test_setup_preserves_unrelated_settings_and_existing_navigation(self):
        before=self.settings()
        after=enhanced.build(before,self.profile(),config.load(ROOT/'.env.example'),self.values())
        self.assertTrue(after['AutoMovieRequestEnabled'])
        self.assertFalse(after['AnalyticsEnabled'])
        self.assertEqual(after['DefaultSubtitleFont'],7)
        self.assertEqual(after['Shortcuts'],before['Shortcuts'])
        self.assertFalse(after['BookmarksUseNativeTab'])
        self.assertTrue(after['BookmarksUsePluginPages'])
        self.assertEqual(before,self.settings())
        self.assertTrue(after['DownloadsFilterByUserRequests'])
        self.assertTrue(after['DownloadsHistoryAdminOnly'])

    def test_managed_instances_are_idempotent_and_preserve_other_connections(self):
        rows=json.dumps([{'Name':'Other','Url':'http://other:8989','ApiKey':'original','Enabled':False}])
        result=enhanced.instance(rows,'Ohara','http://sonarr:8989','fixture-key','https://tv.example.com','https://sonarr.example.com')
        again=enhanced.instance(result,'Ohara','http://sonarr:8989','fixture-key','https://tv.example.com','https://sonarr.example.com')
        self.assertEqual(result,again)
        self.assertEqual(json.loads(result)[0],json.loads(rows)[0])
        self.assertEqual(len(json.loads(result)),2)
        self.assertIn('https://tv.example.com|https://sonarr.example.com',json.loads(result)[1]['UrlMappings'])

    def test_invalid_or_disabled_instances_are_not_replaced(self):
        for data in ('not json','{}','[1]',json.dumps([{'Url':'http://sonarr:8989','Enabled':False}])):
            with self.subTest(data=data),self.assertRaises(ValueError):
                enhanced.instance(data,'Ohara','http://sonarr:8989','fixture','https://tv.example.com','https://sonarr.example.com')

    def test_personal_patch_keeps_subtitles_shortcuts_and_other_choices(self):
        before={**{k:False for k in self.profile()['personal']},'SelectedFontSizePresetIndex':9,
                'AutoSkipIntro':True,'IsAdmin':True,'OtherChoice':'keep'}
        result=enhanced.personal(before,self.profile()['personal'])
        self.assertEqual(result['SelectedFontSizePresetIndex'],9)
        self.assertTrue(result['AutoSkipIntro'])
        self.assertEqual(result['OtherChoice'],'keep')
        self.assertNotIn('IsAdmin',result)

    def test_conflicting_operator_mapping_is_preserved(self):
        original='https://tv.example.com|https://custom.example.com'
        self.assertEqual(enhanced.mapping(original,'https://tv.example.com','https://seerr.example.com'),original)

    def test_concurrent_admin_change_is_not_rolled_back_or_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'configs/jellyfin').mkdir(parents=True)
            (root/'configs/jellyfin/enhanced-qol.json').write_text(json.dumps(self.profile()))
            before=self.settings();calls=[];reads=0
            class API:
                def call(self,path,body=None):
                    nonlocal reads
                    if body is not None:
                        calls.append(path)
                        return
                    if path=='/Branding/Configuration':return {'CustomCss':'keep'}
                    if path=='/Users':return []
                    reads+=1
                    return copy.deepcopy(before) if reads==1 else {**before,'operator-change':True}
            with patch.object(enhanced.theme,'client',return_value=API()), \
                    patch.object(enhanced,'identify',return_value={'Id':'fixture'}), \
                    patch.object(enhanced,'validate_services'), \
                    patch.object(enhanced.credentials,'read',return_value=self.values()), \
                    patch.object(enhanced.theme,'state',return_value=None), \
                    self.assertRaisesRegex(ValueError,'changed during setup'):
                enhanced.setup(config.load(ROOT/'.env.example'),root)
            self.assertEqual(calls,[])


if __name__=='__main__':unittest.main()
