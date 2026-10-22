import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/lib'))
import config
import credentials
import immich
import immich_oauth


class ImmichOAuthTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        shutil.copytree(ROOT / 'configs/immich', self.root / 'configs/immich')
        self.c = config.load(ROOT / '.env.example')
        self.secret = 'Disposable only $ # = " quote'

    def inputs(self):
        path = self.root / '.env'
        path.write_text('IMMICH_GOOGLE_CLIENT_ID=123456-test.apps.googleusercontent.com\n'
                        'IMMICH_GOOGLE_CLIENT_SECRET=' + self.secret + '\n')
        path.chmod(0o600)

    def test_missing_inputs_leave_configuration_untouched(self):
        with self.assertRaises(ValueError):
            immich_oauth.prepare(self.root, self.c)
        self.assertFalse((self.root / 'local').exists())

    def test_render_enforces_existing_users_only_and_preserves_password_login(self):
        self.inputs()
        policy = json.loads(immich_oauth.render(self.root, self.c))
        self.assertIs(policy['oauth']['enabled'], True)
        self.assertIs(policy['oauth']['autoRegister'], False)
        self.assertIs(policy['oauth']['autoLaunch'], False)
        self.assertIs(policy['passwordLogin']['enabled'], True)
        self.assertIs(policy['machineLearning']['enabled'], False)
        self.assertEqual(policy['oauth']['clientSecret'], self.secret)
        self.assertEqual(policy['oauth']['issuerUrl'], 'https://accounts.google.com')
        self.assertEqual(policy['oauth']['mobileRedirectUri'], 'https://immich.xdadwal.in/api/oauth/mobile-redirect')

    def test_policy_rejects_open_registration_or_owner_lockout(self):
        self.inputs()
        policy = json.loads(immich_oauth.render(self.root, self.c))
        for section, key, value in [('oauth', 'autoRegister', True), ('oauth', 'autoLaunch', True),
                                    ('passwordLogin', 'enabled', False), ('machineLearning', 'enabled', True)]:
            broken = json.loads(json.dumps(policy))
            broken[section][key] = value
            with self.subTest(section=section, key=key), self.assertRaises(ValueError):
                immich_oauth.validate_policy(broken)

    def test_generated_config_and_backup_are_private_and_idempotent(self):
        self.inputs()
        immich_oauth.prepare(self.root, self.c)
        target = self.root / 'local/immich/immich.json'
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)
        self.assertEqual(target.parent.stat().st_mode & 0o777, 0o700)
        immich_oauth.prepare(self.root, self.c)
        self.assertEqual(len(list(target.parent.iterdir())), 1)
        self.secret += ' changed'
        self.inputs()
        immich_oauth.prepare(self.root, self.c)
        backup = next(target.parent.glob('immich-previous-*.json'))
        self.assertEqual(backup.stat().st_mode & 0o777, 0o600)
        self.assertNotEqual(backup.read_text(), target.read_text())

    def test_static_path_never_consumes_private_oauth_configuration(self):
        self.inputs()
        immich_oauth.prepare(self.root, self.c)
        self.assertEqual(immich_oauth.configuration_path(self.root, static=True),
                         self.root / 'configs/immich/immich.json')
        self.assertEqual(immich_oauth.configuration_path(self.root), self.root / 'local/immich/immich.json')

    def test_insecure_or_symlink_generated_config_is_rejected(self):
        self.inputs()
        immich_oauth.prepare(self.root, self.c)
        target = self.root / 'local/immich/immich.json'
        target.chmod(0o644)
        with self.assertRaises(ValueError):
            immich_oauth.configuration_path(self.root)
        target.unlink()
        target.symlink_to(self.root / 'configs/immich/immich.json')
        with self.assertRaises(ValueError):
            immich_oauth.configuration_path(self.root)

    def test_google_credentials_never_enter_compose_environment_or_argv(self):
        self.inputs()
        immich_oauth.prepare(self.root, self.c)
        shutil.copy(ROOT / 'versions.immich.env', self.root)
        with patch.dict(os.environ, {'IMMICH_GOOGLE_CLIENT_SECRET': self.secret}), \
                patch('immich.password', return_value='DisposableDBOnly1234'), \
                patch('immich.runtime.docker_prefix', return_value=['docker']), patch('immich.runtime.run') as run:
            immich.compose(self.c, self.root, ['up', '-d'])
            args, kwargs = run.call_args
            self.assertNotIn('IMMICH_GOOGLE_CLIENT_SECRET', kwargs['env'])
            self.assertNotIn(self.secret, ' '.join(args[0]))
            self.assertEqual(kwargs['env']['IMMICH_CONFIG_PATH'], str(self.root / 'local/immich/immich.json'))

    def test_oauth_inputs_are_ignored_by_unrelated_services(self):
        import credential_fixtures
        self.inputs()
        credential_fixtures.write(self.root)
        homepage, media = credentials.load(self.root)
        self.assertFalse(credentials.IMMICH_OAUTH_KEYS & homepage.keys())
        self.assertFalse(credentials.IMMICH_OAUTH_KEYS & media.keys())

    def test_bad_client_id_does_not_echo_the_input(self):
        self.inputs()
        path = self.root / '.env'
        path.write_text(path.read_text().replace('123456-test.apps.googleusercontent.com', 'private-invalid-input'))
        with self.assertRaises(ValueError) as caught:
            immich_oauth.render(self.root, self.c)
        self.assertNotIn('private-invalid-input', str(caught.exception))

    def test_failed_activation_restores_previous_mode_and_retains_private_candidate(self):
        self.inputs()
        with patch('immich.check'), patch('immich.compose', side_effect=[RuntimeError('failed'), None]) as compose:
            with self.assertRaisesRegex(RuntimeError, 'previous configuration restored'):
                immich.configure_oauth(self.c, self.root)
            self.assertEqual(compose.call_count, 2)
        target = self.root / 'local/immich/immich.json'
        self.assertFalse(target.exists())
        failed = next(target.parent.glob('immich-failed-*.json'))
        self.assertEqual(failed.stat().st_mode & 0o777, 0o600)
        self.assertEqual(immich_oauth.configuration_path(self.root), self.root / 'configs/immich/immich.json')

    def test_failed_update_restores_existing_oauth_configuration(self):
        self.inputs()
        immich_oauth.prepare(self.root, self.c)
        target = self.root / 'local/immich/immich.json'
        original = target.read_bytes()
        self.secret += ' changed'
        self.inputs()
        with patch('immich.check'), patch('immich.compose', side_effect=[RuntimeError('failed'), None]):
            with self.assertRaises(RuntimeError):
                immich.configure_oauth(self.c, self.root)
        self.assertEqual(target.read_bytes(), original)
