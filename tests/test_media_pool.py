import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts/lib'))
import config
import media_pool
import runtime


class MediaPoolTests(unittest.TestCase):
    def test_unmounted_or_wrong_filesystem_never_reaches_docker(self):
        c={'MEDIA_ROOT':'/ohara/mnt','MEDIA_POOL_MOUNT':'/ohara/mnt'}
        for fs in ['ext4','fuse.mergerfs']:
            target='/ohara/mnt' if fs=='ext4' else '/'
            with self.subTest(fs=fs),patch.object(runtime,'run',return_value=json.dumps({'filesystems':[{'target':target,'fstype':fs}]})) as run,patch.object(runtime,'docker_prefix') as docker,self.assertRaises(ValueError):
                runtime.compose(c,ROOT,['up','-d'])
            docker.assert_not_called()
            self.assertEqual(run.call_args.args[0][0],'findmnt')
        with patch.object(runtime,'run',side_effect=RuntimeError('not mounted')),patch.object(runtime,'docker_prefix') as docker,self.assertRaises(RuntimeError):
            runtime.compose(c,ROOT,['start','jellyfin'])
        docker.assert_not_called()

    def test_guard_disabled_for_ordinary_storage(self):
        with patch.object(runtime,'run') as run:
            media_pool.require_mount({'MEDIA_ROOT':'/ordinary/media'})
        run.assert_not_called()

    def test_configuration_rejects_mismatch_or_unsafe_mount(self):
        text=(ROOT/'.env.example').read_text()
        for value in ['/other','/ohara/../mnt','/ohara/mnt;id']:
            with tempfile.TemporaryDirectory() as d:
                p=Path(d)/'.env';p.write_text(text+'\nMEDIA_POOL_MOUNT='+value+'\n')
                with self.assertRaises(ValueError):config.load(p)

    def test_only_media_consumers_change_restart_policy_and_mount_sources(self):
        c=config.load(ROOT/'.env.example');c.update(MEDIA_ROOT='/ohara/mnt',MEDIA_POOL_MOUNT='/ohara/mnt')
        model=json.loads(runtime.compose(c,ROOT,['config','--no-env-resolution','--format','json'],capture=True,docker=['docker']))
        for name,service in model['services'].items():
            if name in media_pool.SERVICES:
                self.assertEqual(service['restart'],'on-failure:5')
                self.assertTrue(any(v['source'].startswith('/ohara/mnt') for v in service['volumes']))
            else:self.assertEqual(service['restart'],'unless-stopped')
        hp_mount=next(v for v in model['services']['homepage']['volumes'] if v['target']=='/media-storage')
        self.assertTrue(hp_mount['read_only'])
        targets={n:[v['target'] for v in model['services'][n]['volumes'] if v['source'].startswith('/ohara/mnt')] for n in media_pool.SERVICES}
        self.assertEqual(targets,{'homepage':['/media-storage'],'jellyfin':['/media'],'navidrome':['/music'],'radarr':['/data'],'sonarr':['/data'],'lidarr':['/data'],'bazarr':['/data/library'],'qbittorrent':['/data']})

    def test_unit_binds_to_pool_without_requiring_it_for_docker(self):
        with patch.object(runtime,'run',return_value='ohara-mnt.mount\n'):
            text=media_pool.unit({'MEDIA_POOL_MOUNT':'/ohara/mnt'},ROOT)
        self.assertIn('RequiresMountsFor=/ohara/mnt',text)
        self.assertIn('BindsTo=ohara-mnt.mount docker.service',text)
        self.assertIn('PartOf=docker.service',text)
        self.assertIn('WantedBy=docker.service',text)

    def test_stop_can_run_without_mount(self):
        with patch.object(media_pool,'require_mount',side_effect=ValueError('absent')),patch.object(runtime,'compose') as compose:
            media_pool.stop({'MEDIA_POOL_MOUNT':'/ohara/mnt'},ROOT)
        self.assertEqual(compose.call_args.args[2][0],'stop')
