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
        with patch.dict(os.environ,{'NTFY_PASSWORD':'never-forward','COMPOSE_FILE':'untrusted.yaml'}), patch.object(orcaslicer.runtime,'run') as run:
            orcaslicer.compose(c,ROOT,['config'])
        env = run.call_args.kwargs['env']
        self.assertNotIn('NTFY_PASSWORD',env)
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
