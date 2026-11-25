from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/lib'))
import nginx_site

TEST = [nginx_site.NGINX, '-t']
RELOAD = ['systemctl', 'reload', 'nginx']


class NginxSiteTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.target = Path(temporary.name) / 'ohara-example.conf'
        self.commands = []
        # New files are owned by root; an unprivileged test run cannot chown to it.
        chown = patch.object(nginx_site.os, 'chown')
        self.chown = chown.start()
        self.addCleanup(chown.stop)

    def run_with(self, failing=None):
        def run(args, **kwargs):
            self.commands.append(args)
            if failing is not None and len(self.commands) == failing:
                raise RuntimeError('nginx: command failed')

        return patch.object(nginx_site.runtime, 'run', run)

    def install(self, content=lambda: b'new\n'):
        previous, mode, owner = nginx_site.existing(self.target)
        nginx_site.install(
            self.target, content, previous, mode, owner, prefix='.ohara-test-', failure='failed'
        )

    def leftovers(self):
        return [p.name for p in self.target.parent.iterdir() if p != self.target]

    def test_missing_file_defaults_to_root_owned_0644(self):
        self.assertEqual(nginx_site.existing(self.target), (None, 0o644, (0, 0)))

    def test_existing_file_reports_content_mode_and_owner(self):
        self.target.write_bytes(b'old\n')
        self.target.chmod(0o600)
        state = self.target.stat()
        self.assertEqual(
            nginx_site.existing(self.target), (b'old\n', 0o600, (state.st_uid, state.st_gid))
        )

    def test_success_writes_0644_keeps_owner_then_tests_and_reloads(self):
        self.target.write_bytes(b'old\n')
        self.target.chmod(0o600)
        state = self.target.stat()
        with self.run_with():
            self.install()
        self.assertEqual(self.target.read_bytes(), b'new\n')
        self.assertEqual(self.target.stat().st_mode & 0o777, 0o644)
        self.assertEqual(self.chown.call_args.args[1:], (state.st_uid, state.st_gid))
        self.assertEqual(self.commands, [TEST, RELOAD])
        self.assertEqual(self.leftovers(), [])

    def test_failed_validation_restores_previous_content_and_mode(self):
        self.target.write_bytes(b'old\n')
        self.target.chmod(0o600)
        with self.run_with(failing=1), self.assertRaisesRegex(RuntimeError, '^failed$'):
            self.install()
        self.assertEqual(self.target.read_bytes(), b'old\n')
        self.assertEqual(self.target.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.commands, [TEST, TEST, RELOAD])
        self.assertEqual(self.leftovers(), [])

    def test_failed_reload_removes_a_file_that_did_not_exist_before(self):
        with self.run_with(failing=2), self.assertRaisesRegex(RuntimeError, '^failed$'):
            self.install()
        self.assertFalse(self.target.exists())
        self.assertEqual(self.commands, [TEST, RELOAD, TEST, RELOAD])
        self.assertEqual(self.leftovers(), [])

    def test_unreadable_candidate_is_reported_like_a_failed_install(self):
        self.target.write_bytes(b'old\n')

        def missing():
            raise FileNotFoundError('candidate')

        with self.run_with(), self.assertRaisesRegex(RuntimeError, '^failed$'):
            self.install(missing)
        self.assertEqual(self.target.read_bytes(), b'old\n')
        self.assertEqual(self.commands, [TEST, RELOAD])

    def test_write_failure_leaves_no_temporary_file(self):
        self.chown.side_effect = PermissionError('chown')
        with self.run_with(), self.assertRaisesRegex(RuntimeError, '^failed$'):
            self.install()
        self.assertFalse(self.target.exists())
        self.assertEqual(self.leftovers(), [])


if __name__ == '__main__':
    unittest.main()
