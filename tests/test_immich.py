import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/lib'))
import config
import credentials
import immich


class ImmichTests(unittest.TestCase):
    def setUp(self):
        self.c = config.load(ROOT / '.env.example')

    def test_optional_inputs_do_not_become_main_stack_requirements(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '.env'
            path.write_text((ROOT / '.env.example').read_text() + '\nIMMICH_LIBRARY_ROOT=/photos/immich\nIMMICH_DB_PASSWORD=onlyForDisposableTests1234\n')
            path.chmod(0o600)
            self.assertEqual(config.load(path)['IMMICH_LIBRARY_ROOT'], '/photos/immich')
            self.assertEqual(immich.password(Path(directory)), 'onlyForDisposableTests1234')

    def test_widget_key_is_optional_and_only_returned_to_homepage(self):
        import credential_fixtures
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.env').write_text((ROOT / '.env.example').read_text())
            credential_fixtures.write(root)
            with (root / '.env').open('a') as stream:
                stream.write('HOMEPAGE_VAR_IMMICH_API_KEY=DisposableWidgetKeyOnly12345\nIMMICH_DB_PASSWORD=TestOnly7\n')
            config.load(root / '.env')
            homepage, media = credentials.load(root)
            self.assertEqual(homepage['HOMEPAGE_VAR_IMMICH_API_KEY'], 'DisposableWidgetKeyOnly12345')
            self.assertNotIn('HOMEPAGE_VAR_IMMICH_API_KEY', media)
            self.assertNotIn('IMMICH_DB_PASSWORD', homepage)

    def test_storage_rejects_traversal_overlap_and_existing_media(self):
        for update in [
            {'IMMICH_LIBRARY_ROOT': '/photos/../photos'},
            {'IMMICH_LIBRARY_ROOT': '/ohara/media/photos'},
            {'IMMICH_LIBRARY_ROOT': '/ohara'},
            {'IMMICH_DATABASE_ROOT': '/ohara/immich/library/db'},
            {'IMMICH_LIBRARY_ROOT': '/'},
            {'IMMICH_LIBRARY_ROOT': '/disk/photos', 'IMMICH_LIBRARY_MOUNT': '/other'},
        ]:
            with self.subTest(update=update), self.assertRaises(ValueError):
                immich.settings(self.c | update)

    def test_symlink_parent_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            link = Path(directory) / 'link'
            link.symlink_to('/tmp', target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'symlink'):
                immich.settings(self.c | {'IMMICH_LIBRARY_ROOT': str(link / 'photos')})

    def test_missing_mount_fails_before_creating_storage(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'unmounted'
            c = self.c | {'IMMICH_LIBRARY_ROOT': str(path / 'photos'), 'IMMICH_LIBRARY_MOUNT': str(path)}
            with self.assertRaisesRegex(ValueError, 'not mounted'):
                immich.storage(c)
            self.assertFalse(path.exists())

    def test_network_database_rejected(self):
        with patch('immich.runtime.run', return_value=json.dumps({'filesystems': [{'target': '/', 'fstype': 'nfs4'}]})):
            with self.assertRaisesRegex(ValueError, 'local Linux storage'):
                immich.storage(self.c)

    def test_wrong_mounted_device_rejected(self):
        with patch('immich.runtime.run', return_value=json.dumps({'filesystems': [{'target': '/other', 'fstype': 'ext4'}]})):
            with self.assertRaisesRegex(ValueError, 'different mount'):
                immich.storage(self.c)

    def test_missing_password_does_not_create_storage(self):
        with patch('immich.check'), patch('immich.password', side_effect=ValueError('missing password')), patch('immich.storage') as storage:
            with self.assertRaises(ValueError):
                immich.prepare(self.c, ROOT)
            storage.assert_not_called()

    def test_compose_environment_is_allowlisted_and_sudo_preserves_names(self):
        with patch.dict(os.environ, {'COMPOSE_FILE': '/evil', 'DB_PASSWORD': 'ambient-secret',
                'HOMEPAGE_AUTH_PASSWORD': 'unrelated-secret', 'IMMICH_DB_PASSWORD': 'ambient-immich'}), \
                patch('immich.password', return_value='onlyForDisposableTests1234'), \
                patch('immich.runtime.docker_prefix', return_value=['sudo', '-n', 'docker']), \
                patch('immich.runtime.run') as run:
            immich.compose(self.c, ROOT, ['up', '-d'])
            args, kwargs = run.call_args
            env = kwargs['env']
            self.assertNotIn('COMPOSE_FILE', env)
            self.assertNotIn('DB_PASSWORD', env)
            self.assertNotIn('HOMEPAGE_AUTH_PASSWORD', env)
            self.assertEqual(env['IMMICH_DB_PASSWORD'], 'onlyForDisposableTests1234')
            self.assertNotIn('onlyForDisposableTests1234', ' '.join(args[0]))
            self.assertIn('--preserve-env=', args[0][2])
            self.assertIn('/dev/null', args[0])

    def test_static_compose_needs_no_password_or_daemon(self):
        with patch('immich.password') as secret, patch('immich.runtime.docker_prefix') as daemon, patch('immich.runtime.run') as run:
            immich.compose(self.c, ROOT, ['config', '--format', 'json'], static=True)
            secret.assert_not_called()
            daemon.assert_not_called()
            self.assertEqual(run.call_args.kwargs['env']['IMMICH_DB_PASSWORD'], '')

    def test_short_password_requires_explicit_exception(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.env').write_text('IMMICH_DB_PASSWORD=TestOnly7\n')
            (root / '.env').chmod(0o600)
            with self.assertRaises(ValueError):
                immich.password(root)
            self.assertEqual(immich.password(root, allow_short=True), 'TestOnly7')
            (root / '.env').write_text('IMMICH_DB_PASSWORD=\n')
            with self.assertRaises(ValueError):
                immich.password(root, allow_short=True)

    def test_password_rejects_unsupported_characters_without_echo(self):
        with patch('immich.credentials.read', return_value={'IMMICH_DB_PASSWORD': 'sensitive$unsupported123'}):
            with self.assertRaises(ValueError) as caught:
                immich.password(ROOT)
            self.assertNotIn('sensitive', str(caught.exception))

    def test_prepare_preserves_existing_files_and_directory_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            library, database = Path(directory) / 'photos', Path(directory) / 'postgres'
            library.mkdir(mode=0o750)
            database.mkdir(mode=0o700)
            (library / 'original').write_bytes(b'preserve photo')
            (database / 'PG_VERSION').write_text('14')
            before = [p.stat() for p in (library, database)]
            c = self.c | {'IMMICH_LIBRARY_ROOT': str(library), 'IMMICH_DATABASE_ROOT': str(database)}
            with patch('immich.check'), patch('immich.password'), patch('immich.storage'):
                immich.prepare(c, ROOT)
            self.assertEqual((library / 'original').read_bytes(), b'preserve photo')
            self.assertEqual((database / 'PG_VERSION').read_text(), '14')
            for path, old in zip((library, database), before):
                self.assertEqual((path.stat().st_uid, path.stat().st_gid, path.stat().st_mode),
                                 (old.st_uid, old.st_gid, old.st_mode))

    def test_stop_does_not_require_real_password(self):
        with patch('immich.password') as secret, patch('immich.runtime.docker_prefix', return_value=['docker']), patch('immich.runtime.run'):
            immich.compose(self.c, ROOT, ['stop'], static=True)
            secret.assert_not_called()

    def test_model_rejects_public_ports_extra_services_and_secrets(self):
        # Real Compose parsing is covered separately by scripts/immich check --static.
        pins, values = immich.images(ROOT), immich.settings(self.c)
        model = {'name': 'ohara-immich', 'services': {
            'immich-server': {'image': pins['IMMICH_SERVER_IMAGE'],
                'ports': [{'host_ip': '127.0.0.1', 'published': '2283', 'target': 2283}],
                'environment': dict.fromkeys(['TZ', 'DB_HOSTNAME', 'DB_USERNAME', 'DB_DATABASE_NAME', 'DB_PASSWORD', 'REDIS_HOSTNAME', 'IMMICH_CONFIG_FILE'], ''),
                'volumes': [
                    {'source': values['IMMICH_LIBRARY_ROOT'], 'target': '/data', 'bind': {'create_host_path': False}},
                    {'source': str(ROOT / 'configs/immich/immich.json'), 'target': '/etc/immich/immich.json', 'read_only': True},
                    {'source': '/etc/localtime', 'target': '/etc/localtime', 'read_only': True}]},
            'redis': {'image': pins['IMMICH_CACHE_IMAGE']},
            'database': {'image': pins['IMMICH_DATABASE_IMAGE'],
                'environment': dict.fromkeys(['POSTGRES_PASSWORD', 'POSTGRES_USER', 'POSTGRES_DB', 'POSTGRES_INITDB_ARGS'], ''),
                'volumes': [{'source': values['IMMICH_DATABASE_ROOT'], 'target': '/var/lib/postgresql/data', 'bind': {'create_host_path': False}}]}}}
        immich.validate_model(model, self.c, ROOT)
        for change in ('public', 'extra', 'secret', 'mount', 'autocreate'):
            broken = copy.deepcopy(model)
            server = broken['services']['immich-server']
            if change == 'public':
                server['ports'][0]['host_ip'] = '0.0.0.0'
            elif change == 'extra':
                broken['services']['immich-machine-learning'] = {}
            elif change == 'secret':
                server['environment']['NAVIDROME_PASSWORD'] = 'unrelated'
            elif change == 'mount':
                server['volumes'][0]['target'] = '/new-data'
            else:
                server['volumes'][0]['bind']['create_host_path'] = True
            with self.subTest(change=change), self.assertRaises(ValueError):
                immich.validate_model(broken, self.c, ROOT)
