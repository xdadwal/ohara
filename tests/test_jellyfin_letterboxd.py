import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts/lib'))
import jellyfin_letterboxd as lb


class LetterboxdTests(unittest.TestCase):
    def archive(self,extra=False):
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w') as z:
            z.writestr('LetterboxdSync.dll',b'disposable fixture')
            if extra:z.writestr('../unexpected',b'extra')
        data=stream.getvalue()
        return data,{'zip_sha256':hashlib.sha256(data).hexdigest(),'dll_sha256':hashlib.sha256(b'disposable fixture').hexdigest()}

    def test_release_integrity_and_layout_are_checked_before_install(self):
        data,p=self.archive();lb.verify_release(data,p)
        with self.assertRaises(ValueError):lb.verify_release(data+b'changed',p)
        with self.assertRaises(ValueError):lb.verify_release(data,{**p,'dll_sha256':'0'*64})
        data,p=self.archive(extra=True)
        with self.assertRaises(ValueError):lb.verify_release(data,p)

    def test_different_existing_plugin_is_preserved_without_writes(self):
        profile=lb.profile(ROOT);calls=[]
        class API:
            def call(self,path,body=None):
                calls.append((path,body))
                if path=='/System/Info/Public':return {'Version':profile['tested_jellyfin_version']}
                return [{'Id':profile['id'],'Version':'99.0.0.0','Status':'Active'}]
        with patch.object(lb.theme,'client',return_value=API()),self.assertRaises(ValueError):lb.install({},ROOT)
        self.assertTrue(all(body is None for _,body in calls))

    def test_existing_binary_drift_is_rejected_without_overwriting(self):
        with tempfile.TemporaryDirectory() as d:
            p={'name':'LetterboxdSync','version':'2.2.0.0','dll_sha256':hashlib.sha256(b'reviewed').hexdigest()}
            path=Path(d)/'jellyfin/plugins/LetterboxdSync_2.2.0.0/LetterboxdSync.dll'
            path.parent.mkdir(parents=True);path.write_bytes(b'reviewed')
            lb.verify_installed({'DATA_ROOT':d},p)
            path.write_bytes(b'changed')
            with self.assertRaises(ValueError):lb.verify_installed({'DATA_ROOT':d},p)
            self.assertEqual(path.read_bytes(),b'changed')

    def test_restart_never_interrupts_loaded_playback(self):
        class API:
            def call(self,path):return [{'NowPlayingItem':{'Id':'fixture'},'PlayState':{'IsPaused':True}}]
        with patch.object(lb.theme,'client',return_value=API()),patch.object(lb.runtime,'compose') as compose,self.assertRaises(ValueError):lb.restart({},ROOT)
        compose.assert_not_called()


if __name__=='__main__':unittest.main()
