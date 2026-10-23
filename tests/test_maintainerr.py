import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts/lib'))
import config
import credentials
import maintainerr as m

class MaintainerrTests(unittest.TestCase):
    def test_compose_is_optional_private_and_credential_free(self):
        c=config.load(ROOT/'.env.example')
        with patch.dict(os.environ,{'COMPOSE_FILE':'/wrong','RADARR_API_KEY':'ambient-secret'}),patch.object(m.runtime,'docker_prefix',return_value=['docker']),patch.object(m.runtime,'run') as run:
            m.compose(c,ROOT,['up','-d'])
            self.assertFalse(set(run.call_args.kwargs['env']) & credentials.ALL_KEYS)
            self.assertNotIn('COMPOSE_FILE',run.call_args.kwargs['env'])
            self.assertIn(str(ROOT/'compose.maintainerr.yaml'),run.call_args.args[0])
        m.check(c,ROOT,static=True)

    def test_prepare_rejects_symlink_and_preserves_existing_files(self):
        with tempfile.TemporaryDirectory() as d:
            c=config.load(ROOT/'.env.example');c.update(DATA_ROOT=d,RUN_UID=str(os.getuid()),RUN_GID=str(os.getgid()))
            p=Path(d)/'maintainerr';p.mkdir();(p/'state').write_text('keep')
            m.prepare(c,ROOT);self.assertEqual((p/'state').read_text(),'keep')
            p.rename(Path(d)/'original');p.symlink_to(Path(d)/'original',target_is_directory=True)
            with self.assertRaises(ValueError):m.prepare(c,ROOT)

    def test_connect_preserves_existing_instances_and_never_writes_rules(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);calls=[]
            current={'media_server_type':'jellyfin'}
            rows={'jellyfin':{'jellyfin_url':'http://jellyfin:8096','jellyfin_api_key':'fixture-jf','jellyfin_user_id':'admin'},'seerr':{'url':'http://seerr:5055','api_key':'fixture-seerr'},'radarr':[{'id':1,'url':'http://radarr:7878','serverName':'Custom','tagExclusions':True}],'sonarr':[{'id':2,'url':'http://sonarr:8989','serverName':'Custom'}]}
            class API:
                def call(self,path,body=None):
                    calls.append((path,body))
                    if body is not None:return {'code':1}
                    if path=='/api/settings':return copy.deepcopy(current)
                    return copy.deepcopy(rows[path.rsplit('/',1)[1]])
            class JF:
                def call(self,path):return [{'Id':'admin','Policy':{'IsAdministrator':True}}]
            values=dict(zip(sorted(m.SERVICE_KEYS),['fixture-jf','fixture-seerr','fixture-radarr','fixture-sonarr']))
            with patch.object(m,'client',return_value=API()),patch.object(m.jellyfin_theme,'client',return_value=JF()),patch.object(m.credentials,'read',return_value=values):
                m.connect({},root)
            writes=[p for p,b in calls if b is not None and '/test' not in p]
            self.assertEqual(writes,[])

    def test_artwork_sets_missing_schedule_without_touching_collection_actions(self):
        for schedule in (None,'0 15 * * * *'):
            with self.subTest(schedule=schedule),tempfile.TemporaryDirectory() as d:
                state={'enabled':False,'cronSchedule':schedule,'posterFrame':{'useFrame':True}}
                calls=[]
                class API:
                    def call(self,path,body=None,method=None):
                        calls.append((path,body,method))
                        if body is not None:state.update(body)
                        return copy.deepcopy(state)
                with patch.object(m,'client',return_value=API()):
                    m.artwork({},Path(d))
                    m.artwork({},Path(d))
                self.assertEqual(state['cronSchedule'],schedule or '0 0 * * * *')
                self.assertTrue(state['posterFrame']['useFrame'])
                self.assertTrue(state['enabled'])
                self.assertEqual(sum(body is not None for _,body,_ in calls),1)
                self.assertTrue(all(path=='/api/overlays/settings' for path,_,_ in calls))

    def test_failed_preflight_does_not_save_connections(self):
        class API:
            def __init__(self):self.writes=[]
            def call(self,path,body=None):
                if body is not None:self.writes.append(path);return {'code':0}
                if path=='/api/settings':return {'media_server_type':None}
                return [] if path.endswith(('sonarr','radarr')) else {}
        class JF:
            def call(self,path):return [{'Id':'admin','Policy':{'IsAdministrator':True}}]
        api=API()
        with patch.object(m,'client',return_value=api),patch.object(m.jellyfin_theme,'client',return_value=JF()),patch.object(m.credentials,'read',return_value={k:'fixture' for k in m.SERVICE_KEYS}),self.assertRaises(ValueError):
            m.connect({},ROOT)
        self.assertEqual(api.writes,['/api/settings/jellyfin/test'])

if __name__=='__main__':unittest.main()
