import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts/lib'))
import adguard
import config
import credentials


class AdguardTests(unittest.TestCase):
    def settings(self):
        c = config.load(ROOT/'.env.example')
        c.update(ADGUARD_BIND_IP='192.168.1.101', ADGUARD_NETWORK='192.168.1.0/24')
        return c

    def test_only_valid_lan_addresses_are_accepted(self):
        for address, network in [('0.0.0.0', '0.0.0.0/0'), ('127.0.0.1', '127.0.0.0/8'),
                                 ('8.8.8.8', '8.8.8.0/24'), ('192.168.1.255', '192.168.1.0/24'),
                                 ('192.168.2.1', '192.168.1.0/24'), ('192.168.1.1:53', '192.168.1.0/24')]:
            c = self.settings()
            c.update(ADGUARD_BIND_IP=address, ADGUARD_NETWORK=network)
            with self.subTest(address=address), self.assertRaises(ValueError):
                adguard.settings(c)

    def test_explicit_rewrites_and_no_hostfile_or_dhcp(self):
        c = self.settings()
        c['HOMEPAGE_HOST'] = 'ohara.xdadwal.in'
        data = adguard.initial_config(c, 'test-only-hash')
        rewrites = data['filtering']['rewrites']
        self.assertEqual({r['domain'] for r in rewrites}, {
            'xdadwal.in', 'ohara.xdadwal.in', 'seerr.xdadwal.in', 'speed.xdadwal.in',
            'tv.xdadwal.in', 'music.xdadwal.in', 'immich.xdadwal.in', 'adguard.xdadwal.in',
            'radarr.xdadwal.in', 'sonarr.xdadwal.in', 'prowlarr.xdadwal.in',
            'qbittorrent.xdadwal.in', 'lidarr.xdadwal.in', 'bazarr.xdadwal.in'})
        self.assertTrue(all(r['answer'] == c['ADGUARD_BIND_IP'] and '*' not in r['domain'] for r in rewrites))
        self.assertNotIn('pihole.xdadwal.in', [r['domain'] for r in rewrites])
        self.assertFalse(data['dns']['hostsfile_enabled'])
        self.assertFalse(data['dhcp']['enabled'])
        self.assertEqual(data['dns']['allowed_clients'], ['192.168.1.0/24'])
        self.assertTrue(all(u.startswith('https://') for u in data['dns']['upstream_dns']))
        self.assertFalse(data['dns']['fallback_dns'])

    def test_password_stays_out_of_config_and_container_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            text = (ROOT/'.env.example').read_text()+'\nADGUARD_BIND_IP=192.168.1.101\nADGUARD_NETWORK=192.168.1.0/24\nADGUARD_PASSWORD=fixture-password-12345\n'
            (root/'.env').write_text(text)
            (root/'.env').chmod(0o600)
            (root/'versions.env').write_text((ROOT/'versions.env').read_text())
            c = config.load(root/'.env')
            self.assertNotIn('ADGUARD_PASSWORD', c)
            self.assertEqual(adguard.password(root), 'fixture-password-12345')
            with patch.dict(os.environ, {'ADGUARD_PASSWORD': 'ambient-secret', 'COMPOSE_FILE': '/wrong'}), \
                 patch.object(adguard.runtime, 'docker_prefix', return_value=['docker']), \
                 patch.object(adguard.runtime, 'run') as run:
                adguard.compose(c, root, ['up', '-d'])
                self.assertFalse(set(run.call_args.kwargs['env']) & credentials.ALL_KEYS)
                self.assertNotIn('COMPOSE_FILE', run.call_args.kwargs['env'])
                self.assertNotIn(str(root/'.env'), run.call_args.args[0])

    def test_existing_state_is_preserved_and_symlinks_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            c = self.settings()
            c.update(DATA_ROOT=directory, RUN_UID=str(os.getuid()), RUN_GID=str(os.getgid()))
            base = Path(directory)/'adguard'
            (base/'conf').mkdir(parents=True)
            (base/'work').mkdir()
            target = base/'conf/AdGuardHome.yaml'
            target.write_text('operator-config')
            target.chmod(0o600)
            with patch.object(adguard, 'check'), patch.object(adguard, 'password', return_value='fixture-password-12345'):
                adguard.prepare(c, ROOT)
                self.assertEqual(target.read_text(), 'operator-config')
                target.unlink()
                target.symlink_to(base/'work/elsewhere')
                with self.assertRaisesRegex(ValueError, 'Symlink'):
                    adguard.prepare(c, ROOT)

    def test_missing_password_cannot_create_storage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            c = self.settings()
            c['DATA_ROOT'] = str(root)
            (root/'.env').write_text((ROOT/'.env.example').read_text())
            (root/'.env').chmod(0o600)
            with patch.object(adguard, 'check'), self.assertRaises(ValueError):
                adguard.prepare(c, root)
            self.assertFalse((root/'adguard').exists())

    def test_operator_chosen_short_password_is_preserved_but_empty_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root/'.env'
            path.write_text('ADGUARD_PASSWORD=short\n')
            path.chmod(0o600)
            self.assertEqual(adguard.password(root), 'short')
            path.write_text('ADGUARD_PASSWORD=\n')
            with self.assertRaises(ValueError):
                adguard.password(root)

    def test_optional_compose_ports_validate(self):
        with patch.object(adguard.runtime, 'docker_prefix', return_value=['docker']):
            adguard.check(self.settings(), ROOT)


if __name__ == '__main__':
    unittest.main()
