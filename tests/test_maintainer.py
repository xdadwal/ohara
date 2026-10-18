from contextlib import redirect_stdout
import io
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/lib'))
import maintainer


class MaintainerTests(unittest.TestCase):
    def test_capacity_thresholds_and_unavailable_inodes(self):
        for used, expected in ((20, 'ok'), (90, 'warn'), (97, 'fail')):
            stats = SimpleNamespace(f_bavail=100-used, f_blocks=100, f_favail=100, f_files=100)
            self.assertEqual(maintainer.pressure(stats)[0], expected)
        stats.f_bavail = 100
        stats.f_favail = 1
        self.assertEqual(maintainer.pressure(stats)[0], 'fail')
        stats.f_files = 0
        self.assertIsNone(maintainer.pressure(stats)[2])

    def test_tools_default_is_non_mutating(self):
        with patch.object(maintainer.host, 'ensure_packages') as packages, patch.object(maintainer.shutil, 'which', return_value=None):
            self.assertEqual(maintainer.terminal_tools(), 0)
            packages.assert_not_called()

    def test_tools_install_requires_root(self):
        with patch.object(maintainer.os, 'geteuid', return_value=1000), patch.object(maintainer.host, 'ensure_packages') as packages:
            with self.assertRaisesRegex(ValueError, 'sudo'):
                maintainer.terminal_tools(True)
            packages.assert_not_called()

    def test_tools_install_only_selected_packages(self):
        with patch.object(maintainer.os, 'geteuid', return_value=0), patch.object(maintainer.host, 'os_info'), patch.object(Path, 'read_text', return_value='ID=ubuntu'), patch.object(maintainer.host, 'ensure_packages') as packages:
            maintainer.terminal_tools(True)
            packages.assert_called_once_with(['tmux', 'bpytop'])

    def test_missing_configuration_still_checks_host_and_hides_errors(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(maintainer.shutil, 'which', return_value='/bin/tool'), patch.object(maintainer.runtime, 'run', side_effect=RuntimeError('PRIVATE_VALUE')):
            rows = maintainer.collect(Path(temporary))
            self.assertTrue(any(r['check'] == 'configuration' and r['status'] == 'fail' for r in rows))
            self.assertTrue(any(r['check'] == 'nginx' for r in rows))
            self.assertNotIn('PRIVATE_VALUE', json.dumps(rows))

    def test_storage_missing_and_failed_applications_reported(self):
        with tempfile.TemporaryDirectory() as temporary:
            c = dict(DATA_ROOT=temporary+'/absent', MEDIA_ROOT=temporary+'/missing', RUN_UID='1000', RUN_GID='1000')
            with patch.object(maintainer.config, 'load', return_value=c), patch.object(maintainer.shutil, 'which', return_value=None), patch.object(maintainer.runtime, 'status', side_effect=RuntimeError('PRIVATE_VALUE')):
                rows = maintainer.collect(Path(temporary))
            self.assertTrue(any(r['check'] == 'MEDIA_ROOT-storage' and r['status'] == 'fail' for r in rows))
            self.assertTrue(any(r['check'] == 'applications' and r['status'] == 'fail' for r in rows))
            self.assertNotIn('PRIVATE_VALUE', json.dumps(rows))

    def test_json_has_consistent_exit_status_and_no_extra_output(self):
        for state, expected in [('fail', 1), ('warn', 0), ('skip', 0), ('ok', 0)]:
            output = io.StringIO()
            with patch.object(maintainer, 'collect', return_value=[dict(check='test', status=state, detail='message')]), redirect_stdout(output):
                self.assertEqual(maintainer.doctor(Path('/unused'), True), expected)
            self.assertEqual(json.loads(output.getvalue())['exit_code'], expected)

    def test_read_only_diagnostics_never_invokes_mutating_commands(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(maintainer.shutil, 'which', return_value='/bin/tool'), patch.object(maintainer.runtime, 'run', return_value='{}') as run:
            maintainer.collect(Path(temporary))
            for call in run.call_args_list:
                self.assertIn(call.args[0][0], ('systemctl', 'nginx', 'tailscale'))
                self.assertNotIn('set', call.args[0])
                self.assertNotIn('restart', call.args[0])
                self.assertNotIn('enable', call.args[0])

    def test_successful_local_storage_and_private_certificate_permissions(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'downloads').mkdir()
            (root / 'library/music').mkdir(parents=True)
            c = dict(DATA_ROOT=temporary, MEDIA_ROOT=temporary, RUN_UID=str(maintainer.os.getuid()), RUN_GID=str(maintainer.os.getgid()))
            def certificate_visibility(path):
                raise PermissionError('private certificates')
            with patch.object(maintainer.config, 'load', return_value=c), patch.object(maintainer.shutil, 'which', return_value=None), patch.object(maintainer.runtime, 'status', return_value=0), patch.object(Path, 'is_file', certificate_visibility):
                rows = maintainer.collect(root)
            self.assertTrue(any(r['check'] == 'applications' and r['status'] == 'ok' for r in rows))
            self.assertTrue(any(r['check'] == 'permissions-downloads' and r['status'] == 'ok' for r in rows))
            self.assertTrue(any(r['check'] == 'certificates' and r['status'] == 'warn' for r in rows))
