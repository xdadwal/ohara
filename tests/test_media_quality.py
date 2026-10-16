from pathlib import Path
import copy
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts/lib'))
import credential_fixtures
import media_quality


class QualityTests(unittest.TestCase):
    def test_restricts_nested_groups_and_preserves_custom_scores(self):
        profile = {'upgradeAllowed':True, 'formatItems':[{'id':42, 'score':100}], 'items':[
            {'id':1002, 'items':[{'quality':{'name':n}, 'allowed':True} for n in
                               ['WEBDL-1080p', 'WEBRip-1080p', 'WEBDL-2160p']]},
            *[{'quality':{'name':n}, 'allowed':True} for n in
              ['HDTV-1080p', 'Bluray-1080p', 'Remux-1080p', 'Raw-HD', 'BR-DISK', 'Bluray-720p']]]}
        result = media_quality.configure(copy.deepcopy(profile))
        self.assertFalse(result['upgradeAllowed'])
        self.assertEqual(result['formatItems'], profile['formatItems'])
        def leaves(items):
            return [leaf for x in items for leaf in (leaves(x['items']) if x.get('items') else [x])]
        self.assertEqual({x['quality']['name'] for x in leaves(result['items']) if x['allowed']}, media_quality.ALLOWED)
        self.assertEqual(media_quality.configure(copy.deepcopy(result)), result)

    def test_missing_service_profile_prevents_all_writes(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            credential_fixtures.write(root)
            with patch.object(media_quality, 'Client') as client:
                client.return_value.call.return_value = []
                with self.assertRaisesRegex(ValueError, 'profile missing'):
                    media_quality.apply(root)
                self.assertTrue(all(len(x.args)==1 for x in client.return_value.call.call_args_list))

    def test_applies_size_limits_without_searching_or_editing_titles(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            credential_fixtures.write(root)
            calls = []
            class Client:
                def __init__(self, url, key): self.name = 'radarr' if '7878' in url else 'sonarr'
                def call(self, path, body=None, method=None):
                    calls.append((self.name,path,copy.deepcopy(body),method))
                    if path == '/api/v3/qualityprofile':
                        return [{'id':4,'name':'HD-1080p','items':[{'quality':{'name':n}} for n in media_quality.ALLOWED]}]
                    if path == '/api/v3/qualitydefinition':
                        return [{'id':i,'quality':{'name':n},'weight':i} for i,n in enumerate(sorted(media_quality.ALLOWED),1)]
            with patch.object(media_quality, 'Client', Client): media_quality.apply(root)
            for name,path,body,method in calls:
                if method:
                    self.assertEqual(method, 'PUT')
                    self.assertTrue('/qualitydefinition/' in path or '/qualityprofile/' in path)
                if body and '/qualitydefinition/' in path:
                    self.assertEqual((body['minSize'],body['preferredSize'],body['maxSize']),
                                     (8,30,60) if name=='radarr' else (5,20,40))
