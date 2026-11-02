"""Security regressions for the optional slicer backend."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts/lib'))
import config
import orcaslicer


class OrcaSlicerTests(unittest.TestCase):
    def test_private_model_and_reject_published_api(self):
        c = config.load(ROOT/'.env.example')
        orcaslicer.check(c,ROOT,static=True)
        model = json.loads(orcaslicer.compose(c,ROOT,['config','--format','json'],capture=True))
        model['services']['orcaslicer']['ports'] = [{'target':3000,'published':'3003','host_ip':'0.0.0.0'}]
        with patch.object(orcaslicer,'compose',return_value=json.dumps(model)):
            with self.assertRaisesRegex(ValueError,'private networking'):
                orcaslicer.check(c,ROOT,static=True)

    def test_no_private_credentials_in_child_environment(self):
        c = config.load(ROOT/'.env.example')
        with patch.dict(os.environ,{'NTFY_PASSWORD':'never-forward','BAMBUDDY_PASSWORD':'owner-secret','BAMBUDDY_USERNAME':'owner','COMPOSE_FILE':'untrusted.yaml'}), patch.object(orcaslicer.runtime,'run') as run:
            orcaslicer.compose(c,ROOT,['config'])
        env = run.call_args.kwargs['env']
        self.assertNotIn('NTFY_PASSWORD',env)
        self.assertNotIn('BAMBUDDY_PASSWORD',env)
        self.assertNotIn('BAMBUDDY_USERNAME',env)
        self.assertNotIn('COMPOSE_FILE',env)
        self.assertIn('/dev/null',run.call_args.args[0])

    def test_reject_state_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)/'bambuddy'
            base.mkdir()
            (base/'orcaslicer').symlink_to(Path(d)/'elsewhere')
            c = config.load(ROOT/'.env.example') | {'BAMBUDDY_ROOT':str(base)}
            with self.assertRaisesRegex(ValueError,'symlink'):
                orcaslicer.storage(c)

    def test_configure_updates_only_approved_fields(self):
        import credentials
        import media
        c = config.load(ROOT/'.env.example')
        before = {'preferred_slicer':'bambu_studio','use_slicer_api':False,
                  'orcaslicer_api_url':'','unrelated':'preserve'}
        desired = {'preferred_slicer':'orcaslicer','use_slicer_api':True,
                   'orcaslicer_api_url':'http://orcaslicer:3000'}
        with tempfile.TemporaryDirectory() as d, patch.object(orcaslicer,'check'), patch.object(credentials,'read',return_value={'BAMBUDDY_USERNAME':'owner','BAMBUDDY_PASSWORD':'existing'}), patch.object(media,'Client') as client:
            api = client.return_value
            api.headers = {}
            api.call.side_effect = [{'access_token':'session'},before,{},before|desired]
            orcaslicer.configure(c,Path(d))
            self.assertEqual(api.call.call_args_list[2].args,('/api/v1/settings/',desired))
            self.assertEqual(api.call.call_args_list[2].kwargs,{'method':'PUT'})
            self.assertEqual(api.headers['Authorization'],'Bearer session')
