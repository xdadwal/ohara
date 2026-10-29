import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import yaml
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts/lib'))
import bambuddy as b
import config
import credentials


class BambuddyTests(unittest.TestCase):
    def test_optional_compose_has_no_host_access_or_ambient_credentials(self):
        c = config.load(ROOT/'.env.example')
        with patch.dict(os.environ, {'COMPOSE_FILE':'/wrong', 'JELLYFIN_PASSWORD':'ambient-secret'}), patch.object(b, 'require_storage'), patch.object(b, 'proxy_gateway', return_value='172.21.0.1'), patch.object(b.runtime, 'docker_prefix', return_value=['docker']), patch.object(b.runtime, 'run') as run:
            b.compose(c, ROOT, ['up', '-d'])
        self.assertFalse(set(run.call_args.kwargs['env']) & credentials.ALL_KEYS)
        self.assertNotIn('COMPOSE_FILE', run.call_args.kwargs['env'])
        self.assertNotIn(str(ROOT/'.env'), run.call_args.args[0])
        b.check(c, ROOT, static=True)

    def test_wrong_mount_blocks_start_before_docker(self):
        c = config.load(ROOT/'.env.example')
        with patch.object(b.runtime, 'run', return_value=json.dumps({'filesystems':[{'target':'/wrong','fstype':'ext4'}]})), patch.object(b.runtime, 'docker_prefix') as docker, self.assertRaises(ValueError):
            b.compose(c, ROOT, ['up', '-d'])
        docker.assert_not_called()

    def test_symlink_and_overlapping_storage_are_rejected(self):
        c = config.load(ROOT/'.env.example')
        for name in ['media', 'jellyfin', 'immich', 'navidrome', 'seerr']:
            with self.subTest(name=name), self.assertRaises(ValueError):
                b.settings({**c, 'BAMBUDDY_ROOT':c['DATA_ROOT']+'/'+name+'/bambuddy'})
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'link';p.symlink_to(Path(d)/'real')
            with self.assertRaises(ValueError):
                b.settings({**c,'BAMBUDDY_ROOT':str(p)})

    def test_prepare_preserves_existing_state_and_ownership(self):
        with tempfile.TemporaryDirectory() as d:
            c=config.load(ROOT/'.env.example');c.update(DATA_ROOT=d,RUN_UID=str(os.getuid()),RUN_GID=str(os.getgid()))
            base,_=b.settings(c);(base/'data').mkdir(parents=True);(base/'data/bambuddy.db').write_text('keep')
            state=(base/'data').stat()
            with patch.object(b,'require_storage'):
                b.prepare(c,ROOT)
            self.assertEqual((base/'data/bambuddy.db').read_text(),'keep')
            self.assertEqual((base/'data').stat().st_uid,state.st_uid)

    def test_homepage_merge_is_idempotent_and_preserves_widgets(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);path=root/'data/homepage/services.yaml';path.parent.mkdir(parents=True)
            original=[{'Utility':[{'qBittorrent':{'href':'https://existing.invalid','widget':{'password':'private-fixture'}}}]}]
            path.write_text(yaml.safe_dump(original))
            b.homepage({'DATA_ROOT':str(root/'data'),'DOMAIN':'example.com'},root)
            once=path.read_text();b.homepage({'DATA_ROOT':str(root/'data'),'DOMAIN':'example.com'},root)
            self.assertEqual(path.read_text(),once)
            data=yaml.safe_load(once);self.assertEqual(data[0]['Utility'][0],original[0]['Utility'][0])
            self.assertEqual(data[1]['3D Print'][0]['Bambuddy']['href'],'https://bambuddy.example.com')

    def test_status_widget_uses_private_placeholder_and_correct_units(self):
        profile=b.widget_config('example.com', 7)
        self.assertEqual(profile['headers']['X-API-Key'], '{{HOMEPAGE_VAR_BAMBUDDY_API_KEY}}')
        self.assertTrue(profile['url'].endswith('/7/status'))
        fields={m['field']:m for m in profile['mappings']}
        self.assertEqual(fields['remaining_time']['suffix'], 'min')
        self.assertNotIn('temperatures.chamber',fields)
        with self.assertRaises(ValueError):
            b.widget_config('example.com', '../control')

    def test_widget_missing_key_does_not_access_api_or_files(self):
        with patch.object(credentials,'load',return_value=({},{})), patch.object(b.media,'Client') as api:
            with self.assertRaisesRegex(ValueError,'Read Status-only'):
                b.widget({'DOMAIN':'example.com'},ROOT)
            api.assert_not_called()

    def test_widget_detects_printer_preserves_cards_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);path=root/'data/homepage/services.yaml';path.parent.mkdir(parents=True)
            original=[{'3D Print':[{'Bambuddy':{'href':'https://existing.invalid'}}]},
                      {'Utility':[{'Other':{'widget':{'type':'customapi','url':'keep'}}}]}]
            path.write_text(yaml.safe_dump(original))
            class API:
                def call(self, route):
                    return [{'id':7}] if route.endswith('printers/') else {'connected':True}
            with patch.object(credentials,'load',return_value=({'HOMEPAGE_VAR_BAMBUDDY_API_KEY':'test-only-placeholder'},{})), patch.object(b.media,'Client',return_value=API()):
                b.widget({'DATA_ROOT':str(root/'data'),'DOMAIN':'example.com'},root)
                once=path.read_text();b.widget({'DATA_ROOT':str(root/'data'),'DOMAIN':'example.com'},root)
            self.assertEqual(path.read_text(),once)
            data=yaml.safe_load(once)
            self.assertEqual(data[1],original[1])
            self.assertEqual(data[0]['3D Print'][0]['Bambuddy']['href'],'https://existing.invalid')
            self.assertNotIn('test-only-placeholder',once)

    def test_widget_multiple_printers_blocks_before_dashboard_write(self):
        class API:
            def call(self, route):
                return [{'id':1},{'id':2}]
        with patch.object(credentials,'load',return_value=({'HOMEPAGE_VAR_BAMBUDDY_API_KEY':'test-only-placeholder'},{})), patch.object(b.media,'Client',return_value=API()):
            with self.assertRaisesRegex(ValueError,'exactly one printer'):
                b.widget({'DOMAIN':'example.com'},ROOT)

    def test_conflicting_dns_is_preserved_without_writes(self):
        writes=[]
        class API:
            headers={}
            def call(self,path,body=None):
                if body is not None:writes.append((path,body))
                return [{'domain':'bambuddy.example.com','answer':'192.168.1.9'}]
        with patch.object(b.adguard,'settings',return_value=('192.168.1.101','192.168.1.0/24')),patch.object(b.adguard,'password',return_value='private-fixture'),patch.object(b.media,'Client',return_value=API()),self.assertRaises(ValueError):
            b.dns({'DOMAIN':'example.com'},ROOT)
        self.assertFalse(writes)


class ProxyGatewayTests(unittest.TestCase):
    def row(self):
        return {'Driver':'bridge','Labels':{'com.docker.compose.project':'ohara-bambuddy','com.docker.compose.network':'default'},'IPAM':{'Config':[{'Gateway':'172.21.0.1'}]}}

    def test_existing_owned_gateway_is_used_without_modification(self):
        with patch.object(b.runtime,'run',return_value=json.dumps([self.row()])) as run:
            self.assertEqual(b.proxy_gateway(['docker']),'172.21.0.1')
        self.assertEqual(run.call_count,1)

    def test_wrong_network_owner_and_public_gateway_are_rejected(self):
        for kind in ['owner','address']:
            row=self.row()
            if kind=='owner':row['Labels']['com.docker.compose.project']='unrelated'
            else:row['IPAM']['Config'][0]['Gateway']='8.8.8.8'
            with patch.object(b.runtime,'run',return_value=json.dumps([row])),self.assertRaises(ValueError):
                b.proxy_gateway(['docker'])

    def test_missing_bridge_is_created_with_compose_ownership_labels(self):
        with patch.object(b.runtime,'run',side_effect=[RuntimeError('missing'),None,json.dumps([self.row()])]) as run:
            self.assertEqual(b.proxy_gateway(['docker']),'172.21.0.1')
        self.assertIn('com.docker.compose.project=ohara-bambuddy',run.call_args_list[1].args[0])
