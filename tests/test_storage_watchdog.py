"""Safety decisions use synthetic kernel/device state; no real disks or services."""
import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts/lib'))
import storage_watchdog as w


class WatchdogTests(unittest.TestCase):
    def setUp(self):
        self.c = w.load_config(ROOT/'configs/storage/watchdog.example.json')
        self.current = {b['uuid']: {'dev': f'8:{i+1}', 'generation': f'8:{i+1}:10',
                                  'disk': f'/dev/sd{i}'} for i, b in enumerate(self.c['branches'])}
        self.mounted = {b['mount']: {'maj:min': self.current[b['uuid']]['dev'],
                                    'fstype': 'ext4', 'options': 'rw,relatime'} for b in self.c['branches']}
        self.mounted[self.c['pool']] = {'fstype': 'fuse.mergerfs', 'options': 'rw,relatime'}

    def decide(self, state, now, current=None, mounts=None, media='inactive', pool='inactive'):
        return w.decide(self.c, state, self.current if current is None else current,
                        {} if mounts is None else mounts, media, pool, now)

    def test_missing_disk_stops_consumers_and_never_spends_retries(self):
        state = {}
        for now in [0, 60, 600, 3600]:
            self.assertEqual(self.decide(state, now, current={}, media='active'), 'stop')
        self.assertNotIn('attempts', state)

    def test_stable_reconnect_and_bounded_retries(self):
        state = {}
        self.assertEqual(self.decide(state, 0), 'settling')
        self.assertEqual(self.decide(state, 59), 'settling')
        self.assertEqual(self.decide(state, 60), 'recover')
        self.assertEqual(self.decide(state, 359), 'cooldown')
        self.assertEqual(self.decide(state, 360), 'recover')
        self.assertEqual(self.decide(state, 660), 'recover')
        self.assertEqual(self.decide(state, 1200), 'cooldown')
        self.assertEqual(self.decide(state, 3660), 'recover')

    def test_disconnect_resets_settling_but_not_attempt_budget(self):
        state = {}
        self.decide(state, 0)
        self.assertEqual(self.decide(state, 60), 'recover')
        self.assertEqual(self.decide(state, 90, current={}), 'missing')
        self.assertEqual(self.decide(state, 400), 'settling')
        self.assertEqual(self.decide(state, 460), 'recover')
        self.assertEqual(len(state['attempts']), 2)

    def test_healthy_playback_is_not_restarted(self):
        state = {}
        self.assertEqual(self.decide(state, 0, mounts=self.mounted, media='active', pool='active'), 'healthy')
        self.assertNotIn('attempts', state)

    def test_wrong_device_readonly_or_wrong_pool_refuses_recovery(self):
        for where, key, value in [(self.c['branches'][0]['mount'], 'maj:min', '8:99'),
                                  (self.c['branches'][0]['mount'], 'options', 'ro'),
                                  (self.c['pool'], 'fstype', 'ext4')]:
            with self.subTest(key=key):
                mounts = copy.deepcopy(self.mounted);mounts[where][key] = value
                self.assertEqual(self.decide({}, 100, mounts=mounts), 'unsafe')
                self.assertEqual(self.decide({}, 100, mounts=mounts, media='active'), 'unsafe-stop')

    def test_reused_device_number_with_old_mount_refuses_recovery(self):
        state = {}
        self.decide(state, 0, mounts=self.mounted, media='active', pool='active')
        new = copy.deepcopy(self.current)
        new[self.c['branches'][0]['uuid']]['generation'] = '8:1:20'
        self.assertEqual(self.decide(state, 30, current=new, mounts=self.mounted), 'unsafe')

    def test_startup_in_progress_does_not_consume_an_attempt(self):
        state = {}
        self.assertEqual(self.decide(state, 0, media='activating'), 'busy')
        self.assertNotIn('attempts', state)

    def test_missing_disk_never_issues_a_standby_command(self):
        with patch.object(w, 'command') as run:
            w.apply_standby(self.c, {}, {})
            run.assert_not_called()

    def test_standby_is_not_reapplied_on_each_tick(self):
        state = {'standby_generation': self.current[self.c['hdd_uuid']]['generation']}
        with patch.object(w, 'command') as run:
            w.apply_standby(self.c, state, self.current)
            run.assert_not_called()

    def test_standby_refuses_wrong_serial_or_ssd(self):
        for serial, rotational in [('WRONG-DISK', '1'), (self.c['hdd_serial'], '0')]:
            state = {}
            with self.subTest(serial=serial), patch.object(w, 'command', return_value='ID_SERIAL_SHORT='+serial) as run, \
                 patch.object(Path, 'read_text', return_value=rotational):
                w.apply_standby(self.c, state, self.current)
                self.assertEqual(run.call_count, 1)
                self.assertEqual(run.call_args.args[0][0], 'udevadm')

    def test_standby_applies_only_bounded_timeout_and_once(self):
        state = {}
        with patch.object(w, 'command', side_effect=['ID_SERIAL_SHORT='+self.c['hdd_serial'], '']) as run, \
             patch.object(Path, 'read_text', return_value='1'):
            w.apply_standby(self.c, state, self.current)
            w.apply_standby(self.c, state, self.current)
            self.assertEqual(run.call_count, 2)
            run.assert_called_with(['/usr/sbin/hdparm', '-S', '242', self.current[self.c['hdd_uuid']]['disk']], timeout=20)

    def test_live_pool_with_absent_branch_mount_requires_inspection(self):
        mounts = copy.deepcopy(self.mounted)
        mounts.pop(self.c['branches'][0]['mount'])
        self.assertEqual(self.decide({}, 0, mounts=mounts), 'unsafe')
        self.assertEqual(self.decide({}, 0, mounts=mounts, media='active'), 'unsafe-stop')

    def test_stop_and_recover_only_touch_guarded_units(self):
        for action, expected in [('stop', ['stop', '--no-block', 'ohara-media.service', 'ohara-mnt.mount']),
                                 ('recover', ['start', '--no-block', 'ohara-media.service'])]:
            with patch.object(w, 'devices', return_value={}), patch.object(w, 'mounts', return_value={}), \
                 patch.object(w, 'active', return_value='inactive'), patch.object(w, 'decide', return_value=action), \
                 patch.object(w, 'apply_standby'), patch.object(w, 'command') as run:
                w.tick(self.c, {})
                run.assert_called_once_with(['systemctl', *expected])
