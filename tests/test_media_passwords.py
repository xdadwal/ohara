from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/lib'))
import credential_fixtures
import credentials
import media
import media_passwords


def set_values(root, **changes):
    path = root/'.env'
    lines = [line for line in path.read_text().splitlines() if line.partition('=')[0] not in changes]
    lines += [f'{key}={value}' for key, value in changes.items()]
    path.write_text('\n'.join(lines)+'\n')
    path.chmod(0o600)


class ShortPasswordOptionTests(unittest.TestCase):
    def test_short_logins_need_the_explicit_option_and_stay_nonempty(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            credential_fixtures.write(root)
            set_values(root, RADARR_PASSWORD='short1')
            with self.assertRaisesRegex(ValueError, 'RADARR_PASSWORD: supply at least 16'):
                credentials.load(root)
            set_values(root, MEDIA_ALLOW_SHORT_PASSWORD='true')
            _, values = credentials.load(root)
            self.assertEqual(values['RADARR_PASSWORD'], 'short1')
            for key in credentials.SHORT_OK_MEDIA_KEYS:
                set_values(root, **{key: 'tiny'})
            credentials.load(root)
            set_values(root, QBITTORRENT_PASSWORD='')
            with self.assertRaisesRegex(ValueError, 'QBITTORRENT_PASSWORD: supply at least 1'):
                credentials.load(root)

    def test_option_does_not_weaken_other_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            credential_fixtures.write(root)
            set_values(root, MEDIA_ALLOW_SHORT_PASSWORD='true')
            for key in ('JELLYFIN_PASSWORD', 'NAVIDROME_PASSWORD', 'HOMEPAGE_AUTH_SECRET'):
                original = (root/'.env').read_text()
                set_values(root, **{key: 'tiny'})
                with self.assertRaisesRegex(ValueError, key):
                    credentials.load(root)
                (root/'.env').write_text(original)
            set_values(root, RADARR_API_KEY='abc')
            with self.assertRaisesRegex(ValueError, 'RADARR_API_KEY'):
                credentials.load(root)

    def test_public_navidrome_needs_its_own_option(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            credential_fixtures.write(root)
            set_values(root, MEDIA_ALLOW_SHORT_PASSWORD='true', NAVIDROME_PASSWORD='tiny')
            with self.assertRaisesRegex(ValueError, 'NAVIDROME_PASSWORD: supply at least 16'):
                credentials.load(root)
            set_values(root, NAVIDROME_ALLOW_SHORT_PASSWORD='true', MEDIA_ALLOW_SHORT_PASSWORD='false',
                       RADARR_PASSWORD='tiny')
            with self.assertRaisesRegex(ValueError, 'RADARR_PASSWORD: supply at least 16'):
                credentials.load(root)
            set_values(root, MEDIA_ALLOW_SHORT_PASSWORD='true')
            self.assertEqual(credentials.load(root)[1]['NAVIDROME_PASSWORD'], 'tiny')

    def test_option_value_is_validated(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            credential_fixtures.write(root)
            for option in ('MEDIA_ALLOW_SHORT_PASSWORD', 'NAVIDROME_ALLOW_SHORT_PASSWORD'):
                original = (root/'.env').read_text()
                set_values(root, **{option: 'yes'})
                with self.assertRaisesRegex(ValueError, option+' must be true or false'):
                    credentials.load(root)
                (root/'.env').write_text(original)


class SetupOnlyPasswordTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        credential_fixtures.write(self.root)
        path = self.root/'.env'
        path.write_text('\n'.join(line for line in path.read_text().splitlines()
                                  if line.partition('=')[0] not in credentials.SETUP_ONLY_KEYS)+'\n')

    def test_runtime_commands_load_without_setup_only_passwords(self):
        _, values = credentials.load(self.root)
        self.assertFalse(credentials.SETUP_ONLY_KEYS & set(values))
        self.assertIn('QBITTORRENT_PASSWORD', values)
        self.assertIn('NAVIDROME_PASSWORD', values)

    def test_runtime_passwords_stay_required(self):
        for key in ('QBITTORRENT_PASSWORD', 'NAVIDROME_PASSWORD', 'HOMEPAGE_AUTH_PASSWORD'):
            path = self.root/'.env'
            original = path.read_text()
            path.write_text('\n'.join(l for l in original.splitlines() if not l.startswith(key+'='))+'\n')
            with self.assertRaisesRegex(ValueError, key):
                credentials.load(self.root)
            path.write_text(original)

    def test_fresh_bazarr_needs_its_password_before_storage_changes(self):
        import shutil
        import config
        import host
        shutil.copytree(ROOT/'configs', self.root/'configs')
        c = config.load(ROOT/'.env.example')
        c.update(DATA_ROOT=str(self.root/'data'), MEDIA_ROOT=str(self.root/'media'))
        with self.assertRaisesRegex(ValueError, 'First Bazarr setup needs BAZARR_PASSWORD'):
            host.prepare_storage(c, self.root)
        self.assertFalse((self.root/'data').exists())

    def test_owner_setup_names_missing_logins_and_verify_skips_them(self):
        import config
        c = config.load(ROOT/'.env.example')
        (self.root/'local').mkdir(exist_ok=True)
        with self.assertRaisesRegex(ValueError, 'Owner media setup needs JELLYFIN_PASSWORD, LIDARR_PASSWORD'):
            media.connect(c, self.root, 'owner@example.com', urls={n: 'http://127.0.0.1:9' for n in
                          ('radarr', 'sonarr', 'prowlarr', 'lidarr', 'qbittorrent', 'jellyfin', 'seerr', 'navidrome')})
        output = []
        with patch.object(media_passwords, 'login_ok', lambda *a, **k: True):
            self.assertEqual(media_passwords.verify(self.root, out=output.append), [])
        self.assertIn('radarr: not in .env (setup-only); skipped', output)
        self.assertIn('qbittorrent: login ok', output)


class Services:
    """Fake Arr/Bazarr/qBittorrent state: current login passwords and clients."""
    def __init__(self, passwords):
        self.passwords = dict(passwords)
        self.clients = {name: ([{'id': 3, 'name': 'Ohara qBittorrent', 'implementation': 'QBittorrent',
                                 'fields': [{'name': 'host', 'value': 'qbittorrent'},
                                            {'name': 'password', 'value': '********'}]}]
                               if name != 'prowlarr' else []) for name in media_passwords.ARR}
        self.tested = []
        self.qb_session = False
        services = self

        class Client:
            def __init__(self, url, key=None):
                self.headers = {}
                self.name = next(name for name, base in media_passwords.default_urls().items() if base == url)

            def call(self, path, body=None, method=None, form=False):
                name = self.name
                if path.endswith('/config/host'):
                    if method == 'PUT':
                        self_check = body['password'] == body['passwordConfirmation']
                        assert self_check, 'confirmation must match'
                        services.passwords[name] = body['password']
                    return {'username': 'admin', 'password': '********', 'authenticationMethod': 'forms'}
                if path == '/api/system/settings':
                    assert self.headers.get('X-API-KEY') and form
                    services.passwords['bazarr'] = body['settings-auth-password']
                    return None
                if path == '/api/v2/auth/login':
                    services.qb_session = body['password'] == services.passwords['qbittorrent']
                    return None
                if path == '/api/v2/app/setPreferences':
                    assert services.qb_session, 'qBittorrent needs a session from the previous password'
                    services.passwords['qbittorrent'] = json.loads(body['json'])['web_ui_password']
                    return None
                if path.endswith('/downloadclient'):
                    return json.loads(json.dumps(services.clients[name]))
                if path.endswith('/downloadclient/test'):
                    services.tested.append((name, dict((f['name'], f['value']) for f in body['fields'])['password']))
                    return None
                if '/downloadclient/' in path and method == 'PUT':
                    services.clients[name] = [body]
                    return None
                if path == '/api/user/nd-admin':
                    assert self.headers.get('X-ND-Authorization') == 'Bearer nd-token'
                    if method == 'PUT':
                        assert body['currentPassword'] == services.passwords['navidrome'], 'current password required'
                        services.passwords['navidrome'] = body['password']
                        services.navidrome_user = body
                        return body
                    return {'id': 'nd-admin', 'userName': 'admin', 'isAdmin': True, 'name': 'Owner'}
                raise AssertionError('unexpected call '+path)
        self.Client = Client

    def login_ok(self, name, url, password, username='admin'):
        return self.passwords[name] == password

    def navidrome_session(self, url, password, username='admin'):
        if self.passwords['navidrome'] != password:
            return None
        return {'id': 'nd-admin', 'token': 'nd-token', 'username': 'admin'}


class RotationTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        credential_fixtures.write(self.root)
        _, self.old = credentials.load(self.root)
        self.previous = self.root/'previous.env'
        self.previous.write_text((self.root/'.env').read_text())
        self.previous.chmod(0o600)
        self.services = Services({name: self.old[name.upper()+'_PASSWORD'] for name in media_passwords.ROTATABLE})

    def run_rotate(self, previous):
        output = []
        with patch.object(media, 'Client', self.services.Client), \
                patch.object(media_passwords, 'login_ok', self.services.login_ok), \
                patch.object(media_passwords, '_navidrome_session', self.services.navidrome_session):
            media_passwords.rotate(self.root, previous, out=output.append)
        return output

    def test_rotation_applies_new_values_and_updates_download_clients(self):
        new = {name.upper()+'_PASSWORD': 'new-'+name for name in media_passwords.ROTATABLE}
        set_values(self.root, MEDIA_ALLOW_SHORT_PASSWORD='true', NAVIDROME_ALLOW_SHORT_PASSWORD='true', **new)
        output = self.run_rotate(self.previous)
        self.assertEqual(self.services.navidrome_user['name'], 'Owner')
        for name in media_passwords.ROTATABLE:
            self.assertEqual(self.services.passwords[name], 'new-'+name)
        self.assertEqual(sorted(self.services.tested), [(n, 'new-qbittorrent') for n in ('lidarr', 'radarr', 'sonarr')])
        for name in ('radarr', 'sonarr', 'lidarr'):
            fields = {f['name']: f['value'] for f in self.services.clients[name][0]['fields']}
            self.assertEqual(fields, {'host': 'qbittorrent', 'password': 'new-qbittorrent'})
        text = '\n'.join(output)
        for value in list(new.values()) + list(self.old.values()):
            self.assertNotIn(value, text)

    def test_rerun_skips_services_already_using_new_values(self):
        set_values(self.root, MEDIA_ALLOW_SHORT_PASSWORD='true', SONARR_PASSWORD='new-sonarr')
        self.run_rotate(None)
        self.assertEqual(self.services.passwords['sonarr'], 'new-sonarr')
        output = self.run_rotate(None)
        self.assertEqual(sum('already uses' in line for line in output), 7)

    def test_qbittorrent_change_requires_previous_copy(self):
        set_values(self.root, MEDIA_ALLOW_SHORT_PASSWORD='true', QBITTORRENT_PASSWORD='new-qb')
        with self.assertRaisesRegex(ValueError, '--previous-env'):
            self.run_rotate(None)
        self.assertEqual(self.services.passwords['qbittorrent'], self.old['QBITTORRENT_PASSWORD'])

    def test_navidrome_change_requires_previous_copy_and_matching_old_value(self):
        set_values(self.root, NAVIDROME_ALLOW_SHORT_PASSWORD='true', NAVIDROME_PASSWORD='new-nd')
        with self.assertRaisesRegex(ValueError, 'Navidrome needs --previous-env'):
            self.run_rotate(None)
        self.services.passwords['navidrome'] = 'something else'
        with self.assertRaisesRegex(RuntimeError, 'navidrome: the previous password was rejected'):
            self.run_rotate(self.previous)
        self.assertEqual(self.services.passwords['navidrome'], 'something else')

    def test_wrong_previous_copy_changes_nothing_in_qbittorrent(self):
        set_values(self.root, MEDIA_ALLOW_SHORT_PASSWORD='true', QBITTORRENT_PASSWORD='new-qb')
        self.services.passwords['qbittorrent'] = 'something else'
        with self.assertRaisesRegex(RuntimeError, 'previous password was rejected'):
            self.run_rotate(self.previous)
        self.assertEqual(self.services.passwords['qbittorrent'], 'something else')

    def test_verify_reports_rejected_logins_without_values(self):
        set_values(self.root, MEDIA_ALLOW_SHORT_PASSWORD='true', LIDARR_PASSWORD='not applied')
        output = []
        with patch.object(media_passwords, 'login_ok', self.services.login_ok):
            failed = media_passwords.verify(self.root, out=output.append)
        self.assertEqual(failed, ['lidarr'])
        self.assertIn('lidarr: LOGIN REJECTED', output)
        self.assertNotIn('not applied', '\n'.join(output))


if __name__ == '__main__':
    unittest.main()
